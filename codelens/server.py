"""Local demo server for CodeLens. Stdlib only. Binds 127.0.0.1, read-only analysis."""
from __future__ import annotations

import html
import json
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, check_model, chat_json
from .prompt_builder import build_ask_prompt, build_explain_prompt
from .retriever import retrieve
from .scanner import scan_repo
from .verifier import verify_refs

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

def _check_path(path: str) -> Path:
    p = Path(path or "").expanduser()
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    return p.resolve()


def _coord(ref: dict) -> str:
    return f"{ref.get('file', '?')}:{ref.get('start', '?')}-{ref.get('end', '?')}"


def _excerpt(repo_root: str, ref: dict, max_lines: int = 15) -> str:
    try:
        root = Path(repo_root).resolve()
        target = (root / str(ref.get("file", ""))).resolve()
        target.relative_to(root)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        s, e = int(ref["start"]), int(ref["end"])
        return "\n".join(l[:200] for l in lines[s - 1:min(e, s + max_lines - 1)])
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

    def _send(self, obj: object, status: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(status)
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
        try:
            return json.loads(self.rfile.read(n).decode("utf-8", errors="replace"))
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
        if url.path == "/api/scan":
            try:
                root = _check_path(parse_qs(url.query).get("path", [""])[0])
                index = scan_repo(root)
                index.pop("limits", None)
                self._send(index)
            except (ValueError, FileNotFoundError, NotADirectoryError) as e:
                self._send({"error": html.escape(str(e))}, 400)
            return
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path not in ("/api/analyze", "/api/ask"):
            self._send({"error": "not found"}, 404)
            return
        body = self._body()
        try:
            root = _check_path(body.get("path", ""))
            index = scan_repo(root)
        except (ValueError, FileNotFoundError, NotADirectoryError) as e:
            self._send({"error": str(e)}, 400)
            return
        model = body.get("model", DEFAULT_MODEL)
        try:
            check_model(model, DEFAULT_HOST)
        except ModelError as e:
            self._send({"error": str(e)}, 503)
            return
        try:
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
                            encoding="utf-8", errors="replace")[:4000]})
                    except OSError:
                        continue
                system, user = build_explain_prompt(index, contents)
                data = chat_json(model, system, user, DEFAULT_HOST)
            else:
                question = (body.get("q") or body.get("question") or "").strip()
                if not question:
                    self._send({"error": "missing 'q' (question)"}, 400)
                    return
                chunks = retrieve(index, question)
                if not chunks:
                    self._send({"answer": "No relevant evidence found — will not invent an answer.",
                                "verified": [], "rejected": []})
                    return
                system, user = build_ask_prompt(question, chunks)
                data = chat_json(model, system, user, DEFAULT_HOST)
            ok, bad = verify_refs(index["root"], data.get("refs", []))
            self._send(_render_answer(index["root"], data, ok, bad))
        except ModelError as e:
            self._send({"error": str(e)}, 502)

    def log_message(self, *args):
        pass  # quiet


def run(port: int = 8000) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CodeLens demo at http://127.0.0.1:{port} (Ctrl+C to stop)")
    srv.serve_forever()
