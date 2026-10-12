"""Local demo server for CodeLens. Stdlib only. Loopback-only, read-only analysis."""
from __future__ import annotations

import html
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import config

from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, chat_with_fallback, resolve_model
from .prompt_builder import build_ask_prompt, build_explain_prompt, enforce_bullets
from .retriever import retrieve
from .scanner import scan_repo
from .source import SourceError, repo_name_from_url, resolve_repository_source
from .verifier import clean_ref, verify_refs

STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_BODY_BYTES = config.MAX_BODY_BYTES
# Bodies beyond this are rejected without draining (client sees a reset).
# Anything smaller is fully drained so the client gets our clean 413.
DISCARD_BUDGET = config.DISCARD_BUDGET
# Worst case is a model call (client timeout) plus overhead.
SOCKET_TIMEOUT = config.SOCKET_TIMEOUT


def _cors_origin() -> str | None:
    return config.CORS_ORIGIN


def _repo_allowlist() -> list[Path] | None:
    roots = [Path(p).expanduser().resolve() for p in config.repo_allowlist()]
    return roots or None


def _enforce_allowlist(resolved: Path) -> None:
    allowlist = _repo_allowlist()
    if allowlist is not None and not any(
        resolved == root or root in resolved.parents for root in allowlist
    ):
        raise ValueError("Path is outside the allowed repository roots.")


def _check_path(path: str) -> Path:
    p = Path(path or "").expanduser()
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    resolved = p.resolve()
    _enforce_allowlist(resolved)
    return resolved


def _coord(ref: dict) -> str:
    return f"{ref.get('file', '?')}:{ref.get('start', '?')}-{ref.get('end', '?')}"


def _excerpt(repo_root: str, ref: dict, max_lines: int = config.EXCERPT_MAX_LINES) -> str:
    try:
        root = Path(repo_root).resolve()
        target = (root / str(ref.get("file", ""))).resolve()
        target.relative_to(root)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        s, e = int(ref["start"]), int(ref["end"])
        return "\n".join(l[:config.EXCERPT_LINE_CHARS] for l in lines[s - 1:min(e, s + max_lines - 1)])
    except (ValueError, OSError, KeyError, IndexError):
        return ""


def _render_answer(repo_root: str, data: dict, ok: list, bad: list) -> dict:
    coords = [_coord(r["ref"]) for r in ok]
    return {
        "answer": data["answer"],
        "verified": coords,
        "excerpts": {c: _excerpt(repo_root, r["ref"]) for c, r in zip(coords, ok)},
        "rejected": [{"coord": _coord(r.get("ref", {})), "reason": r["reason"]} for r in bad],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeLens/0.1.0"
    timeout = SOCKET_TIMEOUT

    def _cors_headers(self) -> None:
        origin = _cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, obj: object, status: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        if n > DISCARD_BUDGET:
            raise ValueError(f"Request body too large (limit {MAX_BODY_BYTES} bytes).")
        raw = self.rfile.read(n)
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError(f"Request body too large (limit {MAX_BODY_BYTES} bytes).")
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {}

    def _serve_static(self, rel: str):
        try:
            target = (STATIC_DIR / rel).resolve()
            target.relative_to(STATIC_DIR.resolve())
        except (ValueError, OSError):
            self._send({"error": "not found"}, 404)
            return
        if not target.is_file():
            self._send({"error": "not found"}, 404)
            return
        ctype, _ = mimetypes.guess_type(str(target))
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._serve_static("index.html")
            return
        if url.path.startswith("/static/"):
            self._serve_static(url.path[len("/static/"):])
            return
        if url.path in ("/styles.css", "/app.js"):
            self._serve_static(url.path.lstrip("/"))
            return
        if url.path == "/api/scan":
            try:
                raw = parse_qs(url.query).get("path", [""])[0]
                with resolve_repository_source(raw) as (root, is_temp):
                    if not is_temp:
                        _enforce_allowlist(root)
                    index = scan_repo(root)
                    if is_temp:
                        index["repo_name"] = repo_name_from_url(raw)
                index.pop("limits", None)
                self._send(index)
            except (ValueError, SourceError) as e:
                self._send({"error": html.escape(str(e))}, 400)
            return
        self._send({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        if url.path not in ("/api/analyze", "/api/ask"):
            self._send({"error": "not found"}, 404)
            return
        try:
            body = self._body()
        except ValueError as e:
            self._send({"error": str(e)}, 413)
            return
        try:
            model, availability_notice = resolve_model(body.get("model", DEFAULT_MODEL), DEFAULT_HOST)
        except ModelError as e:
            self._send({"error": str(e)}, 503)
            return
        # One resolution only: the temp clone (if any) outlives scan + model work.
        try:
            with resolve_repository_source(body.get("path", "")) as (root, is_temp):
                if not is_temp:
                    _enforce_allowlist(root)
                index = scan_repo(root)
                if is_temp:
                    index["repo_name"] = repo_name_from_url(body.get("path", ""))
                if url.path == "/api/analyze":
                    files = [m for m in index.get("manifests", [])[:3] if m in index["files"]]
                    for f in index["files"]:
                        if len(files) >= 8:
                            break
                        if f.endswith((".py", ".js", ".ts", ".go", ".rs")) and f not in files:
                            files.append(f)
                    contents = []
                    for rel in files:
                        try:
                            contents.append({"file": rel, "text": (root / rel).read_text(
                                encoding="utf-8", errors="replace")[:config.SCAN_MAX_CHARS_PER_FILE]})
                        except OSError:
                            continue
                    system, user = build_explain_prompt(index, contents)
                    data, used_model, fallback_notice = chat_with_fallback(model, system, user, DEFAULT_HOST)
                    data["answer"] = enforce_bullets(data["answer"])
                else:
                    question = (body.get("q") or body.get("question") or "").strip()
                    if not question:
                        self._send({"error": "missing 'q' (question)"}, 400)
                        return
                    chunks = retrieve(index, question)
                    if not chunks:
                        self._send({"answer": "No relevant evidence found — will not invent an answer.",
                                    "verified": [], "rejected": [], "model": model})
                        return
                    system, user = build_ask_prompt(question, chunks)
                    data, used_model, fallback_notice = chat_with_fallback(model, system, user, DEFAULT_HOST)
            ok, bad = verify_refs(index["root"], [clean_ref(r) for r in data.get("refs", [])])
            resp = _render_answer(index["root"], data, ok, bad)
            resp["model"] = used_model
            for note in (availability_notice, fallback_notice):
                if note:
                    resp.setdefault("notices", []).append(note)
            self._send(resp)
        except (ValueError, SourceError) as e:
            self._send({"error": str(e)}, 400)
        except ModelError as e:
            self._send({"error": str(e)}, 502)

    def log_message(self, *args):
        pass  # quiet


def run(port: int = config.SERVE_PORT) -> None:
    srv = ThreadingHTTPServer((config.SERVE_HOST, port), Handler)
    print(f"CodeLens demo at http://{config.SERVE_HOST}:{port} (Ctrl+C to stop)")
    srv.serve_forever()
