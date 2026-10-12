"""Ollama client over stdlib urllib. No fake fallbacks — errors are explicit."""
from __future__ import annotations

import json
import urllib.request
import urllib.error

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"


class ModelError(RuntimeError):
    pass


def _get(host: str, path: str, timeout: int = 5) -> dict:
    try:
        with urllib.request.urlopen(host + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise ModelError(
            f"Cannot reach Ollama at {host}. Is Ollama running? Start with `ollama serve`. ({e})"
        )


def check_ollama(host: str = DEFAULT_HOST) -> list[str]:
    data = _get(host, "/api/tags")
    return [m.get("name", "") for m in data.get("models", [])]


def check_model(model: str, host: str = DEFAULT_HOST) -> None:
    models = check_ollama(host)
    base = model.split(":")[0]
    if not any(m == model or m.startswith(base + ":") for m in models):
        raise ModelError(
            f"Model '{model}' not found locally. Installed: {models or 'none'}. "
            f"Run `ollama pull {model}`."
        )


def chat_json(model: str, system: str, user: str, host: str = DEFAULT_HOST,
              timeout: int = 180, num_ctx: int = 16384) -> dict:
    payload = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"num_ctx": num_ctx},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }).encode()
    req = urllib.request.Request(
        host + "/api/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            outer = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        raise ModelError(f"Ollama request failed (HTTP {e.code}): {detail or e}.")
    except urllib.error.URLError as e:
        raise ModelError(f"Ollama request failed: {e}. Is `ollama serve` running?")
    content = (outer.get("message") or {}).get("content", "")
    if not content.strip():
        raise ModelError("Empty response from model.")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # try to salvage trailing/leading text
        s, e = content.find("{"), content.rfind("}")
        if s != -1 and e > s:
            try:
                data = json.loads(content[s:e + 1])
            except json.JSONDecodeError:
                raise ModelError(f"Model returned invalid JSON: {content[:300]}")
        else:
            raise ModelError(f"Model returned invalid JSON: {content[:300]}")
    if "answer" not in data:
        raise ModelError("Model JSON missing required field 'answer'.")
    refs = data.get("refs", [])
    if not isinstance(refs, list):
        raise ModelError("Model JSON field 'refs' must be a list.")
    data["refs"] = [r for r in refs if isinstance(r, dict)]
    return data
