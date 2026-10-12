"""Ollama client over stdlib urllib. No fake fallbacks — errors are explicit."""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "gemma3:4b"
FALLBACK_MODEL = "qwen2.5:3b"


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


def _installed(model: str, models: list[str]) -> bool:
    base = model.split(":")[0]
    return any(m == model or m.startswith(base + ":") for m in models)


def _alternate(model: str) -> str:
    return FALLBACK_MODEL if model == DEFAULT_MODEL else DEFAULT_MODEL


def resolve_model(model: str, host: str = DEFAULT_HOST) -> tuple[str, str | None]:
    """Pick the model to use: requested if installed, else the alternate.

    Returns (model_to_use, notice). notice is None when the requested model
    is used, otherwise a human-readable explanation of the switch.
    Raises ModelError only when neither is installed.
    """
    models = check_ollama(host)
    if _installed(model, models):
        return model, None
    alt = _alternate(model)
    if _installed(alt, models):
        return alt, (
            f"Model '{model}' not found locally — using fallback '{alt}' instead. "
            f"Run `ollama pull {model}` to use it."
        )
    raise ModelError(
        f"Neither '{model}' nor fallback '{alt}' found locally. "
        f"Installed: {models or 'none'}. Run `ollama pull {model}`."
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


def chat_with_fallback(model: str, system: str, user: str,
                       host: str = DEFAULT_HOST, **kwargs) -> tuple[dict, str, str | None]:
    """Chat with one retry on the alternate model after a generation failure.

    Returns (data, used_model, notice). notice is None when the requested
    model answered; otherwise it names the failure and the model that did.
    The switch is always reported — never silent.
    """
    try:
        return chat_json(model, system, user, host, **kwargs), model, None
    except ModelError as first_err:
        alt = _alternate(model)
        try:
            models = check_ollama(host)
        except ModelError:
            raise first_err
        if not _installed(alt, models):
            raise first_err
        data = chat_json(alt, system, user, host, **kwargs)
        return data, alt, f"'{model}' failed ({first_err}) — answered by fallback '{alt}'."
