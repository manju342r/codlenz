"""Input source resolution: local directory or remote Git URL, one pipeline.

Both sources resolve to a local directory that feeds the existing scanner.
Nothing here executes or installs code from scanned repositories.
"""
from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from . import config

CLONE_TIMEOUT = config.CLONE_TIMEOUT

# scp-like SSH syntax: git@github.com:user/repo(.git)
_SSH_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[A-Za-z0-9._\-/]+(?:\.git)?/?$")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class SourceError(RuntimeError):
    pass


def _is_ssh_syntax(s: str) -> bool:
    return bool(_SSH_RE.match(s))


def _is_https_or_ssh_url(s: str) -> bool:
    try:
        u = urlparse(s)
    except ValueError:
        return False
    return u.scheme in ("https", "ssh") and bool(u.netloc) and bool(u.path.strip("/"))


def is_git_url(s: str) -> bool:
    """True for supported remote URL shapes (https://, ssh://, scp-like git@)."""
    s = (s or "").strip()
    return _is_ssh_syntax(s) or _is_https_or_ssh_url(s)


def looks_like_url(s: str) -> bool:
    """True for anything URL-shaped, including unsupported/malformed ones."""
    s = (s or "").strip()
    if "://" in s or _SSH_RE.match(s.split()[0] if s else ""):
        return True
    try:
        return bool(urlparse(s).scheme)
    except ValueError:
        return False


def _has_embedded_credentials(s: str) -> bool:
    try:
        u = urlparse(s)
    except ValueError:
        return False
    return bool(u.username or u.password)


def repo_name_from_url(url: str) -> str:
    s = url.strip().rstrip("/")
    if "@" in s and ":" in s and "://" not in s:
        path = s.split(":", 1)[1]
    else:
        path = urlparse(s).path
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    name = _SAFE_NAME_RE.sub("-", name).strip("-") or "repo"
    return name


def _scrub(text: str) -> str:
    # strip anything credential-shaped (user:pass@) before display
    return re.sub(r"(://)[^/\s@]+@", r"\1***@", text)


def _explain_clone_failure(stderr: str, url: str) -> str:
    err = _scrub(stderr.strip())
    last = err.splitlines()[-1] if err else ""
    name = repo_name_from_url(url)
    low = err.lower()
    if "repository not found" in low:
        return f"Repository not found or not accessible: {url} (private repos need working Git credentials)."
    if "permission denied (publickey)" in err.lower():
        return "SSH authentication failed. Check your SSH key / ssh-agent, then retry."
    if "could not resolve" in err.lower() or "network is unreachable" in err.lower():
        return f"Network error while cloning {url}. Check your connection and retry."
    if "authentication failed" in err.lower():
        return "Git authentication failed. CodeLens uses your existing Git credentials; it never takes tokens directly."
    detail = last or "unknown error"
    return f"Could not clone {url}: {name} ({detail})"


@contextlib.contextmanager
def _clone(url: str):
    git = shutil.which("git")
    if not git:
        raise SourceError("Git is not installed. Install Git to scan remote repositories.")
    with tempfile.TemporaryDirectory(prefix=config.TEMP_PREFIX) as td:
        try:
            proc = subprocess.run(
                [git, "clone", "--depth", str(config.CLONE_DEPTH), url, td],
                capture_output=True, text=True, timeout=CLONE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise SourceError(f"Clone timed out after {CLONE_TIMEOUT}s: {url}")
        except OSError as e:
            raise SourceError(f"Could not run Git: {e}")
        if proc.returncode != 0:
            raise SourceError(_explain_clone_failure(proc.stderr, url))
        yield Path(td).resolve()


@contextlib.contextmanager
def resolve_source(raw: str):
    """Yield a local directory for a path or Git URL input.

    Local directories pass through untouched. Remote URLs are shallow-cloned
    into a temp dir that lives for the whole block and is always cleaned up.
    """
    s = (raw or "").strip()
    if is_git_url(s):
        if _has_embedded_credentials(s):
            raise SourceError("Refusing URL with embedded credentials. Use your Git credential helper instead.")
        with _clone(s) as tmp:
            yield tmp
        return
    if looks_like_url(s):
        raise SourceError(
            f"Unsupported or malformed Git URL: {s}. "
            "Use https://host/user/repo(.git) or git@host:user/repo(.git)."
        )
    p = Path(s).expanduser() if s else Path("")
    if s and p.is_dir():
        yield p.resolve()
        return
    raise SourceError(f"No such directory: {raw}. Pass a local directory or a Git URL.")
