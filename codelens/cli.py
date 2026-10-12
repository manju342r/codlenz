"""CodeLens CLI: scan / analyze / ask."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import config
from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, chat_with_fallback, resolve_model
from .prompt_builder import build_ask_prompt, build_explain_prompt, enforce_bullets
from .retriever import retrieve
from .scanner import scan_repo
from .source import SourceError, is_git_url, repo_name_from_url, resolve_source
from .verifier import clean_ref, verify_refs

console = Console()


def _load_contents(root: Path, files: list[str], per_file: int) -> list[dict]:
    out = []
    for rel in files:
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")[:per_file]
            out.append({"file": rel, "text": text})
        except OSError:
            continue
    return out


def _pick_explain_files(index: dict) -> list[str]:
    """Small diverse set: project docs, manifests, entry points, then one code file per module."""
    files = index["files"]
    cap = index["limits"]["max_files_to_model"]
    prio: list[str] = []
    generated = {"codelens-analysis.md", "CHANGELOG.md"}

    def take(rel: str) -> None:
        if rel in files and rel not in prio and rel not in generated:
            prio.append(rel)

    for doc in ("README.md", "README.rst", "ARCHITECTURE.md", "ARCHITECTURE.rst"):
        take(doc)
    for m in index.get("manifests", [])[:2]:
        take(m)
    for e in index.get("entry_points", [])[:2]:
        take(e)
    seen: set[str] = set()
    for f in files:
        if len(prio) >= cap:
            break
        if not f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
            continue
        top = f.split("/")[0] if "/" in f else f.rsplit(".", 1)[0]
        if top in seen:
            continue
        take(f)
        seen.add(top)
    for f in files:
        if len(prio) >= cap:
            break
        if f not in prio and f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
            take(f)
    return prio[:cap]


def _scan_index(source: str, root: Path) -> dict:
    """Run the shared pipeline entry; temp clones report the real repo name."""
    index = scan_repo(root)
    if is_git_url(source):
        index["repo_name"] = repo_name_from_url(source)
    return index


def _show_refs(ok: list[dict], bad: list[dict]) -> None:
    for r in ok:
        ref = r["ref"]
        console.print(f"[green]✅ {ref['file']}:{ref['start']}–{ref['end']}[/green]")
    for r in bad:
        ref = r.get("ref", {})
        console.print(f"[red]❌ {ref.get('file', '?')}:{ref.get('start', '?')}–{ref.get('end', '?')} — {r['reason']}[/red]")


@click.group()
@click.version_option(config.APP_VERSION)
def main():
    """CodeLens — local-first codebase understanding with verified references."""


@main.command()
@click.argument("source")
def scan(source):
    """Scan a local directory or Git URL and show structure (no AI call)."""
    try:
        with resolve_source(source) as root:
            index = _scan_index(source, root)
    except SourceError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(2)
    table = Table(title=f"CodeLens scan: {index['repo_name']}")
    table.add_column("Aspect")
    table.add_column("Result")
    table.add_row("Languages", str(index["languages"]) or "none detected")
    table.add_row("Folders", ", ".join(index["folders"][:12]) or "—")
    table.add_row("Manifests", ", ".join(index["manifests"]) or "—")
    table.add_row("Likely entry points", ", ".join(index["entry_points"]) or "none found (candidates only)")
    table.add_row("Source files", str(index["file_count"]))
    table.add_row("Skipped", str(index["skipped"]))
    if index["truncated"]:
        table.add_row("Note", "⚠ partial analysis — file limit reached")
    console.print(table)


@main.command()
@click.argument("source")
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
def analyze(source, model, host):
    """Explain a local directory or Git URL using real source + open-weight model."""
    try:
        with resolve_source(source) as root:
            index = _scan_index(source, root)
            if index["file_count"] == 0:
                console.print("[red]Error: empty repository — no source files found.[/red]")
                sys.exit(2)
            try:
                model, availability_notice = resolve_model(model, host)
            except ModelError as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(3)
            if availability_notice:
                console.print(f"[yellow]{availability_notice}[/yellow]")
            chosen = _pick_explain_files(index)
            contents = _load_contents(Path(index["root"]), chosen, index["limits"]["max_chars_per_file"])
            system, user = build_explain_prompt(index, contents)
            with console.status(f"[cyan]Asking local model {model}...[/cyan]"):
                try:
                    data, used_model, fallback_notice = chat_with_fallback(model, system, user, host)
                except ModelError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(3)
            if fallback_notice:
                console.print(f"[yellow]{fallback_notice}[/yellow]")
            else:
                console.print(f"[dim]Answered by {used_model}.[/dim]")
            data["answer"] = enforce_bullets(data["answer"])
            ok, bad = verify_refs(index["root"], [clean_ref(r) for r in data.get("refs", [])])
            if is_git_url(source):
                out_path = Path.cwd() / f"{repo_name_from_url(source)}{config.ANALYSIS_SUFFIX}"
            else:
                out_path = Path(index["root"]) / config.ANALYSIS_FILENAME
            md = [f"# CodeLens analysis: {index['repo_name']}\n", data["answer"], "\n## Verified references\n"]
            for r in ok:
                ref = r["ref"]
                md.append(f"- ✅ `{ref['file']}:{ref['start']}–{ref['end']}` — `{ref['quote'][:100]}`")
            if bad:
                md.append("\n## Unverified references (do not trust)\n")
                for r in bad:
                    ref = r.get("ref", {})
                    md.append(f"- ❌ `{ref.get('file')}` — {r['reason']}")
            md.append("\n> Claims without a ✅ reference are INFERRED, not verified.\n")
            out_path.write_text("\n".join(md), encoding="utf-8")
            console.print(Panel(data["answer"], title="Architecture explanation"))
            _show_refs(ok, bad)
            if not ok and not bad:
                console.print("[yellow]Note: model gave no refs — treat claims as INFERRED.[/yellow]")
            console.print(f"[green]Saved → {out_path}[/green]")
    except SourceError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(2)


@main.command()
@click.argument("source")
@click.argument("question")
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
def ask(source, question, model, host):
    """Ask about a local directory or Git URL (retrieval + verified refs)."""
    try:
        with resolve_source(source) as root:
            index = _scan_index(source, root)
            chunks = retrieve(index, question)
            if not chunks:
                console.print("[yellow]No relevant evidence found — I will not invent an answer. Try different keywords.[/yellow]")
                sys.exit(0)
            try:
                model, availability_notice = resolve_model(model, host)
            except ModelError as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(3)
            if availability_notice:
                console.print(f"[yellow]{availability_notice}[/yellow]")
            system, user = build_ask_prompt(question, chunks)
            with console.status(f"[cyan]Asking local model {model}...[/cyan]"):
                try:
                    data, used_model, fallback_notice = chat_with_fallback(model, system, user, host)
                except ModelError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(3)
            if fallback_notice:
                console.print(f"[yellow]{fallback_notice}[/yellow]")
            else:
                console.print(f"[dim]Answered by {used_model}.[/dim]")
            ok, bad = verify_refs(index["root"], [clean_ref(r) for r in data.get("refs", [])])
            console.print(Panel(data["answer"], title=f"Q: {question}"))
            _show_refs(ok, bad)
            if ok and not bad:
                console.print("[green]VERIFIED: refs above match exact files/lines/quotes. Claims still need your judgment.[/green]")
            elif ok:
                console.print("[yellow]PARTIAL: some refs failed — only ✅ ones are evidence.[/yellow]")
            else:
                console.print("[yellow]UNSUPPORTED/INFERRED: no verified refs — do not treat as fact.[/yellow]")
    except SourceError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(2)


@main.command()
@click.option("--port", default=config.SERVE_PORT, show_default=True, help="Local serve port.")
def serve(port):
    """Start the local demo server (browser UI + JSON API)."""
    from .server import run

    console.print(f"[green]CodeLens demo at http://{config.SERVE_HOST}:{port}[/green]")
    try:
        run(port)
    except OSError as e:
        console.print(f"[red]Error: cannot bind {config.SERVE_HOST}:{port} ({e}). Try --port {port + 1}.[/red]")
        raise SystemExit(1)
