# CodeLens

**Understand unfamiliar codebases with a local open-weight AI model and verified source evidence.**

CodeLens is a local-first CLI that helps developers understand unfamiliar code. It scans a repository, explains its architecture with a locally running open-weight model (Gemma 3 4B via Ollama, Qwen 2.5 3B fallback), and answers questions — with every source reference independently checked by Python, not trusted blindly.

Built for Hacktoberfest Hack Day (MLH × NIAT-KKH): *build small, make it work, make it interesting.*

## Problem

Entering an unfamiliar codebase, developers struggle with: what the project does, how it's organized, which files matter, where the app starts, and where a feature lives.

## Features

- `codelens scan` — structure overview (languages, manifests, likely entry points). No AI call.
- `codelens analyze` — 8-section technical briefing (overview, stack, architecture, components, flow, AI/memory, findings, summary) from **actual source content**, saved to `codelens-analysis.md`.
- `codelens ask` — keyword retrieval (no vectors/embeddings) + grounded answer.
- **Source verification (core differentiator):** every model-cited `{file, start, end, quote}` is resolved safely inside the repo, line-checked, and quote-matched. `✅` = evidence, `❌` = rejected. Claims without ✅ refs are labeled INFERRED/UNSUPPORTED.
- Path-traversal protection, context budgets, explicit errors — never fake fallbacks.

## How it works

```
repo path → scanner.py (pathlib index: langs, manifests, entry candidates)
  → retriever.py (filename/def/import/content scoring, top 4–6 chunks)
  → prompt_builder.py (evidence-only prompt, JSON schema contract)
  → model_client.py (Ollama /api/chat, format=json, num_ctx=16384)
  → verifier.py (resolve + contain + exist + line range + quote match)
  → Rich terminal output (✅/❌) + codelens-analysis.md
```

The open-weight model (Qwen 2.5 3B, Q4_K_M, local) does all repo reasoning. No paid APIs, no cloud, no embeddings.

## Architecture

```
codelens/
  scanner.py        shared repo index (scan/explain/ask all use it)
  retriever.py      keyword scoring, no vector DB
  prompt_builder.py small-model-friendly prompts, untrusted-data framing
  model_client.py   stdlib urllib Ollama client, strict JSON validation
  verifier.py       independent ref checker (file/range/quote + traversal guard)
  cli.py            Click + Rich: scan / analyze / ask
skill/SKILL.md      agent-invocation notes (CLI works standalone)
prompts/            prompt text mirrors
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally

## Ollama & model setup

```bash
ollama serve
ollama pull gemma3:4b     # primary model
ollama pull qwen2.5:3b    # fallback model
ollama list   # confirm both are present
```

## Installation

```bash
git clone <your-fork-url> && cd hacktober-kkh
pip install -r requirements.txt   # click, rich
# run without installing:
PYTHONPATH=. python -c "from codelens.cli import main; main()" scan .
# or install editable:
pip install -e .
```

## Usage

```bash
# Local directory
codelens scan /path/to/repo
codelens analyze /path/to/repo
codelens ask /path/to/repo "Where is authentication implemented?"

# GitHub repository directly (cloned temporarily, never modified)
codelens scan https://github.com/username/repository
codelens analyze https://github.com/username/repository
codelens ask https://github.com/username/repository "Where is escaping implemented?"
```

## Remote repositories

`scan`, `analyze`, and `ask` accept a local directory **or** a Git URL — both feed the same pipeline.

- Supported: `https://host/user/repo` (`.git` suffix and trailing slash optional), `ssh://git@host/user/repo.git`, and scp-like `git@host:user/repo.git`.
- Remote repos are shallow-cloned (`--depth 1`) into a temp dir that is deleted after the command, on success or failure. Your own local repositories are never touched.
- Requires the Git CLI installed. Private repos work only through your existing Git credentials (SSH agent, credential helper) — CodeLens never takes tokens, and URLs with embedded credentials are refused.
- For remote `analyze`, the report is saved as `./<repo>-codelens-analysis.md` in your current directory (the temp clone is deleted, so in-place saving would vanish).
- Limitations: shallow clone, no submodules, 120s clone timeout. The demo server accepts the same paths and Git URLs; hosted deployments should set `CODELENS_REPO_ALLOWLIST` (ephemeral clones bypass it by design).

## Example output (real run, CodeLens analyzing itself)

```
Q: How does CodeLens verify source references?
CodeLens verifies source references by using the `verify_ref` function in
the `codelens/verifier.py` file...
✅ codelens/verifier.py:4–35
❌ codelens/__init__.py:28–43 — line range 28-43 exceeds file length 2
PARTIAL: some refs failed — only ✅ ones are evidence.
```

Note the `❌`: the model hallucinated a ref and Python caught it. That is the feature working.

## Limitations

- Small local models sometimes return bad refs — the verifier catches them, but answers can be thin.
- Keyword retrieval (not semantic): questions must share vocabulary with the code.
- Entry points are *likely candidates* from naming conventions, not certainty.
- `skill/SKILL.md` documents invocation; formal Agent Skills Open Standard compliance is not audited here.
- Analysis quality depends on the local model; 3B models suit small/medium repos.

## Deployment

Two targets: an installable CLI (PyPI) and a hosted web demo (static page + backend host).

### CLI install

```bash
pipx install codelens        # isolated install (pipx)
pip install codelens          # or plain pip
codelens --help
```

Requires Python ≥3.10, Git (for URL scanning), and Ollama with `gemma3:4b`
(`qwen2.5:3b` fallback). No API keys, no env vars required for local use.

### Hosted web demo

The page in `codelens/static/` is plain static files — host anywhere (Vercel included).
Point it at a backend with `?backend=https://your-host` (persisted in localStorage);
without a reachable backend it offers a canned demo sample. The Python server
(`codelens serve`) is the backend: it needs an always-on host with Ollama,
because Vercel serverless cannot run it (no persistent process, 10–60s limits
vs 15–180s model calls, no localhost Ollama).

```bash
cp .env.example .env   # then set values
CORS_ORIGIN=https://your-page.vercel.app \
CODELENS_REPO_ALLOWLIST=/srv/repos \
codelens serve --port 8000
```

| Variable | Purpose | Default |
|---|---|---|
| `CORS_ORIGIN` | Exact page origin allowed to call the API | same-origin only |
| `CODELENS_REPO_ALLOWLIST` | Comma-separated repo roots the API may scan | any local path |
| `OLLAMA_HOST` | Ollama base URL (server-side only) | `http://localhost:11434` |

Rules for the hosted backend: never accept raw visitor paths without the allowlist,
never expose Ollama publicly, keep prompts and verification unchanged.

### Deployment checklist

- [ ] `pip install` clean-venv smoke test + `codelens --help/scan`
- [ ] `.env` set on the backend host (never committed)
- [ ] `CODELENS_REPO_ALLOWLIST` points at a pre-cloned corpus, not `/`
- [ ] `CORS_ORIGIN` exactly matches the page origin
- [ ] Backend reachable from the page (`?backend=`), canned fallback confirmed
- [ ] No secrets in repo (`git log --all -S 'sk-'` or equivalent sweep)
- [ ] PyPI name `codelens` re-checked at publish time; publish only on approval
- [ ] Vercel deploy only the static page; never the Python server

## License

MIT — see [LICENSE](LICENSE).
