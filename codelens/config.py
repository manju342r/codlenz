"""Single home for tunable settings. Plain values, no secrets.

Every default can be overridden with the env var named beside it.
Nothing here is a secret, so committing this file is safe.
"""
from __future__ import annotations

import os


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- Model (Ollama, local-first) ---
OLLAMA_HOST = _str("OLLAMA_HOST", "http://localhost:11434")
PRIMARY_MODEL = _str("CODELENS_MODEL", "gemma3:4b")
FALLBACK_MODEL = _str("CODELENS_FALLBACK_MODEL", "qwen2.5:3b")
MODEL_TIMEOUT = _int("CODELENS_MODEL_TIMEOUT", 180)
MODEL_TAGS_TIMEOUT = _int("CODELENS_MODEL_TAGS_TIMEOUT", 5)
MODEL_NUM_CTX = _int("CODELENS_MODEL_NUM_CTX", 16384)

# --- Serving ---
SERVE_HOST = _str("CODELENS_HOST", "127.0.0.1")
SERVE_PORT = _int("CODELENS_PORT", 8000)
SOCKET_TIMEOUT = _int("CODELENS_SOCKET_TIMEOUT", 240)
MAX_BODY_BYTES = _int("CODELENS_MAX_BODY_BYTES", 1_000_000)
DISCARD_BUDGET = _int("CODELENS_DISCARD_BUDGET", 8 * 1024 * 1024)
CORS_ORIGIN = os.environ.get("CORS_ORIGIN") or None


def repo_allowlist() -> list[str]:
    raw = os.environ.get("CODELENS_REPO_ALLOWLIST", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


# --- Remote sources ---
CLONE_TIMEOUT = _int("CODELENS_CLONE_TIMEOUT", 120)
CLONE_DEPTH = _int("CODELENS_CLONE_DEPTH", 1)
TEMP_PREFIX = "codelens-"

# --- Scanning / retrieval / evidence ---
SCAN_MAX_FILES = _int("CODELENS_SCAN_MAX_FILES", 500)
SCAN_MAX_FILE_SIZE = _int("CODELENS_SCAN_MAX_FILE_SIZE", 100_000)
SCAN_MAX_FILES_TO_MODEL = _int("CODELENS_SCAN_MAX_FILES_TO_MODEL", 8)
SCAN_MAX_CHARS_PER_FILE = _int("CODELENS_SCAN_MAX_CHARS_PER_FILE", 4000)
SCAN_MAX_TOTAL_CHARS = _int("CODELENS_SCAN_MAX_TOTAL_CHARS", 20000)
RETRIEVE_TOP_K = _int("CODELENS_RETRIEVE_TOP_K", 5)
RETRIEVE_MAX_CHARS = _int("CODELENS_RETRIEVE_MAX_CHARS", 4000)
EVIDENCE_MAX_LINES = _int("CODELENS_EVIDENCE_MAX_LINES", 140)
EXCERPT_MAX_LINES = _int("CODELENS_EXCERPT_MAX_LINES", 15)
EXCERPT_LINE_CHARS = _int("CODELENS_EXCERPT_LINE_CHARS", 200)

# --- Output files ---
ANALYSIS_FILENAME = "codelens-analysis.md"
ANALYSIS_SUFFIX = "-codelens-analysis.md"

# --- Misc ---
APP_VERSION = "0.1.0"
