"""Independent source verification. Model claims are never trusted blindly."""
from __future__ import annotations

import re
from pathlib import Path

# Evidence chunks are sent line-numbered ("  12| code"); models often copy the
# gutter into quotes. Strip it before checking — the gutter is our artifact.
GUTTER_RE = re.compile(r"(?m)^\s*\d+\|\s?")


def clean_ref(ref: dict) -> dict:
    """Return a copy of ref with numbering gutters removed from its quote.

    Also unwraps template copying: models often return the schema example
    shape verbatim (angle brackets, backticks, quotes around the path).
    """
    cleaned = dict(ref)
    if isinstance(cleaned.get("quote"), str):
        cleaned["quote"] = GUTTER_RE.sub("", cleaned["quote"])
    if isinstance(cleaned.get("file"), str):
        f = cleaned["file"].strip()
        for wrap in ("<>", "``", "''", '""'):
            if len(f) >= 2 and f.startswith(wrap[0]) and f.endswith(wrap[1]):
                f = f[1:-1].strip()
        cleaned["file"] = f
    return cleaned


def verify_ref(repo_root: str | Path, ref: dict) -> dict:
    root = Path(repo_root).resolve()
    file = str(ref.get("file", ""))
    start = ref.get("start")
    end = ref.get("end")
    quote = str(ref.get("quote", ""))
    fail = lambda reason: {"ref": ref, "ok": False, "reason": reason}

    if not file or not isinstance(start, int) or not isinstance(end, int) or not quote:
        return fail("malformed ref (need file/start:int/end:int/quote)")
    if start < 1 or end < start:
        return fail(f"invalid line range {start}-{end}")
    # block absolute paths and traversal; resolve and contain
    target = (root / file)
    try:
        resolved = target.resolve()
        resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        return fail("path escapes repository or is invalid")
    if not resolved.is_file():
        return fail("file does not exist")
    try:
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return fail("file not readable")
    if end > len(lines):
        return fail(f"line range {start}-{end} exceeds file length {len(lines)}")
    selected = "\n".join(lines[start - 1:end])
    if quote not in selected:
        return fail("quote not found in referenced lines")
    return {"ref": ref, "ok": True, "reason": "verified"}


def verify_refs(repo_root: str | Path, refs: list[dict]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for r in refs:
        res = verify_ref(repo_root, r)
        (ok if res["ok"] else bad).append(res)
    return ok, bad
