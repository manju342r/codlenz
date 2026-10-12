"""CodeLens CLI: scan / analyze / ask."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .scanner import scan_repo
from .retriever import retrieve
from .prompt_builder import build_explain_prompt, build_ask_prompt
from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, check_model, chat_json
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
@click.argument("path", type=click.Path(exists=True, file_okay=False))
def scan(path):
    """Scan a repository and show structure (no AI call)."""
    try:
        index = scan_repo(path)
    except (FileNotFoundError, NotADirectoryError) as e:
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
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
def analyze(path, model, host):
    """Generate architectural explanation using real source + open-weight model."""
    try:
        index = scan_repo(path)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(2)
    if index["file_count"] == 0:
        console.print("[red]Error: empty repository — no source files found.[/red]")
        sys.exit(2)
    try:
        check_model(model, host)
    except ModelError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(3)
    chosen = _pick_explain_files(index)
    root = Path(index["root"])
    contents = _load_contents(root, chosen, index["limits"]["max_chars_per_file"])
    system, user = build_explain_prompt(index, contents)
    with console.status(f"[cyan]Asking local model {model}...[/cyan]"):
        try:
            data = chat_json(model, system, user, host)
        except ModelError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(3)
    ok, bad = verify_refs(index["root"], data.get("refs", []))
    out_path = root / "codelens-analysis.md"
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


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.argument("question")
@click.option("--model", default=DEFAULT_MODEL, show_default=True)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
def ask(path, question, model, host):
    """Ask a question about the codebase (keyword retrieval + verified refs)."""
    try:
        index = scan_repo(path)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(2)
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
