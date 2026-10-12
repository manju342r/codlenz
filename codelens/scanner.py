"""Repository scanner: pathlib-based, stdlib only, shared by scan/explain/ask."""
from __future__ import annotations

import json
from pathlib import Path

from . import config

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist",
    "build", "coverage", "vendor", ".tox", ".mypy_cache", ".pytest_cache",
    "target", ".idea", ".vscode",
}

SKIP_SUFFIXES = {".lock", ".min.js", ".min.css", ".map", ".pyc", ".pyo", ".o", ".so", ".dll", ".exe"}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz",
    ".mp4", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".eot", ".bin", ".dat",
    ".db", ".sqlite", ".onnx", ".pt", ".bin",
}

EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin",
    ".sh": "Shell", ".toml": "TOML", ".yaml": "YAML", ".yml": "YAML",
    ".json": "JSON", ".md": "Markdown", ".html": "HTML", ".css": "CSS",
}

MANIFESTS = {
    "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml",
    "go.mod", "pom.xml", "composer.json", "Gemfile", "setup.py",
    "setup.cfg", "Dockerfile", "docker-compose.yml", "Makefile",
}

ENTRY_CANDIDATES = [
    "main.py", "app.py", "__main__.py", "manage.py", "cli.py",
    "src/main.py", "src/app.py", "src/index.js", "src/index.ts",
    "src/main.ts", "src/main.js", "index.js", "index.ts",
    "cmd/main.go", "main.go", "src/main.rs", "Main.java",
]

DEFAULTS = {
    "max_files": config.SCAN_MAX_FILES,
    "max_file_size": config.SCAN_MAX_FILE_SIZE,
    "max_files_to_model": config.SCAN_MAX_FILES_TO_MODEL,
    "max_chars_per_file": config.SCAN_MAX_CHARS_PER_FILE,
    "max_total_chars": config.SCAN_MAX_TOTAL_CHARS,
}


def _is_skipped(path: Path) -> bool:
    name = path.name
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    if name.endswith(".lock") and name != "Cargo.lock":
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def scan_repo(root: str | Path, **overrides) -> dict:
    cfg = {**DEFAULTS, **overrides}
    root_p = Path(root).resolve()
    if not root_p.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    if not root_p.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    files: list[str] = []
    skipped = 0
    truncated = False
    languages: dict[str, int] = {}
    manifests: list[str] = []
    folders: set[str] = set()

    all_entries = sorted(root_p.rglob("*"))
    for p in all_entries:
        # skip anything inside ignored dirs
        try:
            rel = p.relative_to(root_p)
        except ValueError:
            continue
        if any(part in IGNORE_DIRS for part in rel.parts):
            if p.is_file():
                skipped += 1
            continue
        if p.is_dir():
            if len(rel.parts) == 1:
                folders.add(rel.parts[0])
            continue
        # file
        if _is_skipped(p):
            skipped += 1
            continue
        try:
            if p.stat().st_size > cfg["max_file_size"]:
                skipped += 1
                continue
        except OSError:
            skipped += 1
            continue
        rel_s = rel.as_posix()
        if p.name in MANIFESTS:
            manifests.append(rel_s)
        lang = EXT_LANG.get(p.suffix.lower())
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
        # only count source-ish files toward the file list
        if p.suffix.lower() in EXT_LANG or p.name in MANIFESTS or p.name.lower() in {"dockerfile", "makefile"}:
            files.append(rel_s)
        if len(files) >= cfg["max_files"]:
            truncated = True
            break

    entry_points = [e for e in ENTRY_CANDIDATES if (root_p / e).exists()]
    # also surface top-level .py / entry-ish files
    for f in files:
        low = f.lower()
        if low in ("app.py", "main.py", "cli.py", "server.py", "index.js") and f not in entry_points:
            entry_points.append(f)

    return {
        "root": str(root_p),
        "repo_name": root_p.name,
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        "folders": sorted(folders),
        "manifests": sorted(manifests),
        "entry_points": entry_points,
        "files": sorted(files),
        "file_count": len(files),
        "skipped": skipped,
        "truncated": truncated,
        "limits": cfg,
    }


def save_index(index: dict, dest: str | Path) -> Path:
    dest_p = Path(dest)
    dest_p.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return dest_p
