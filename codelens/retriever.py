"""Keyword retriever: no vectors, no embeddings. Filenames, defs, imports, content."""
from __future__ import annotations

import re
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
DEF_RE = re.compile(r"^\s*(def|class|function|func|const|let|var|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text)}


def retrieve(index: dict, question: str, top_k: int = 5, max_chars: int = 4000) -> list[dict]:
    root = Path(index["root"])
    qtoks = _tokens(question)
    if not qtoks:
        return []
    scored: list[tuple[float, dict]] = []
    for rel in index.get("files", []):
        if rel.endswith((".json", ".lock", ".md")) and not any(
            k in rel.lower() for k in qtoks
        ):
            # deprioritize manifests unless named
            pass
        score = 0.0
        fname = Path(rel).name.lower()
        reasons: list[str] = []
        # 1. filename match (highest)
        for q in qtoks:
            if q in fname:
                score += 5.0
                reasons.append(f"filename:{q}")
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > max_chars * 3:
            text = text[: max_chars * 3]
        low = text.lower()
        # 2. def/class name match (high)
        for m in DEF_RE.finditer(text):
            name = m.group(2).lower()
            if name in qtoks:
                score += 4.0
                reasons.append(f"def:{m.group(2)}")
        # 3. import match (medium)
        for q in qtoks:
            if f"import {q}" in low or f"from {q}" in low or f'require("{q}' in low:
                score += 2.0
                reasons.append(f"import:{q}")
        # 4. content keyword matches (supporting)
        hits = sum(1 for q in qtoks if q in low)
        score += min(hits * 0.5, 3.0)
        if hits:
            reasons.append(f"content:{hits}/{len(qtoks)}")
        if score > 0:
            scored.append((score, {"file": rel, "score": round(score, 2),
                                   "why": ", ".join(reasons[:4]),
                                   "text": text[:max_chars]}))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]
