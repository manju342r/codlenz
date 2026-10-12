"""Local demo server for CodeLens. Stdlib only. Binds 127.0.0.1, read-only analysis."""
from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelError, check_model, chat_json
from .prompt_builder import build_ask_prompt, build_explain_prompt
from .retriever import retrieve
from .scanner import scan_repo
from .verifier import verify_refs

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CodeLens — local demo</title>
<style>body{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}
input{width:100%;padding:.5rem;margin:.25rem 0}button{padding:.5rem 1rem;margin:.25rem .25rem .25rem 0;cursor:pointer}
pre{background:#f4f4f4;padding:1rem;white-space:pre-wrap;overflow:auto}.ok{color:green}.bad{color:red}.spin{color:#666}</style>
</head><body>
<h1>CodeLens — local demo</h1>
<p>Model: <b>qwen2.5:3b</b> via Ollama on localhost. Nothing leaves this machine.</p>
<label>Repository path <input id="path" value="/Users/manjunathchakri/Documents/projects/hacktober-kkh"></label>
<label>Question <input id="q" value="How does CodeLens verify source references?"></label>
<div><button onclick="go('scan')">1. Scan</button>
<button onclick="go('analyze')">2. Analyze</button>
<button onclick="go('ask')">3. Ask</button></div>
<pre id="out">Pick a step above.</pre>
<script>
async function go(action){
  const out=document.getElementById('out');
  out.innerHTML='<span class="spin">Working (model calls take ~15s)…</span>';
  const path=document.getElementById('path').value, q=document.getElementById('q').value;
  let url='/api/scan?path='+encodeURIComponent(path), opts={};
  if(action!=='scan'){url='/api/'+action;opts={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,q})}}
  try{
    const r=await fetch(url,opts), d=await r.json();
    out.textContent=typeof d==='string'?d:JSON.stringify(d,null,2);
  }catch(e){out.textContent='Request failed: '+e}
}
</script></body></html>"""


def _check_path(path: str) -> Path:
    p = Path(path or "").expanduser()
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    return p.resolve()


def _render_answer(data: dict, ok: list, bad: list) -> dict:
    return {
        "answer": data["answer"],
        "verified": [f"{r['ref']['file']}:{r['ref']['start']}-{r['ref']['end']}" for r in ok],
        "rejected": [f"{r.get('ref', {}).get('file', '?')}: {r['reason']}" for r in bad],
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

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
            self._send(_render_answer(data, ok, bad))
        except ModelError as e:
            self._send({"error": str(e)}, 502)

    def log_message(self, *args):
        pass  # quiet


def run(port: int = 8000) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CodeLens demo at http://127.0.0.1:{port} (Ctrl+C to stop)")
    srv.serve_forever()
