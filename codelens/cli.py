"""CodeLens CLI: scan / analyze / ask."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, check_model, chat_json
from .prompt_builder import build_ask_prompt, build_explain_prompt
from .retriever import retrieve
from .scanner import scan_repo
from .source import SourceError, is_git_url, repo_name_from_url, resolve_source
from .verifier import verify_refs

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
    files = index["files"]
    prio: list[str] = []
    for m in index.get("manifests", [])[:3]:
        if m in files:
            prio.append(m)
    for e in index.get("entry_points", [])[:2]:
        if e in files and e not in prio:
            prio.append(e)
    for f in files:
        if len(prio) >= index["limits"]["max_files_to_model"]:
            break
        if f not in prio and f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
            prio.append(f)
    return prio


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
@click.version_option("0.1.0")
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
                check_model(model, host)
            except ModelError as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(3)
            chosen = _pick_explain_files(index)
            contents = _load_contents(Path(index["root"]), chosen, index["limits"]["max_chars_per_file"])
            system, user = build_explain_prompt(index, contents)
            with console.status(f"[cyan]Asking local model {model}...[/cyan]"):
                try:
                    data = chat_json(model, system, user, host)
                except ModelError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(3)
            ok, bad = verify_refs(index["root"], data.get("refs", []))
            if is_git_url(source):
                out_path = Path.cwd() / f"{repo_name_from_url(source)}-codelens-analysis.md"
            else:
                out_path = Path(index["root"]) / "codelens-analysis.md"
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
                check_model(model, host)
            except ModelError as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(3)
            system, user = build_ask_prompt(question, chunks)
            with console.status(f"[cyan]Asking local model {model}...[/cyan]"):
                try:
                    data = chat_json(model, system, user, host)
                except ModelError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    sys.exit(3)
            ok, bad = verify_refs(index["root"], data.get("refs", []))
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
@click.option("--port", default=8000, show_default=True, help="Local port (127.0.0.1 only).")
def serve(port):
    """Start the local demo server (browser UI + JSON API)."""
    from .server import run

    console.print(f"[green]CodeLens demo at http://127.0.0.1:{port}[/green]")
    try:
        run(port)
    except OSError as e:
        console.print(f"[red]Error: cannot bind 127.0.0.1:{port} ({e}). Try --port 8001.[/red]")
        raise SystemExit(1)
