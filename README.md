# CodeLens

**Understand unfamiliar codebases with a local open-weight AI model and verified source evidence.**

CodeLens is a local-first CLI that helps developers understand unfamiliar code. It scans a repository, explains its architecture with a locally running open-weight model (Qwen 2.5 3B via Ollama), and answers questions — with every source reference independently checked by Python, not trusted blindly.

Built for Hacktoberfest Hack Day (MLH × NIAT-KKH): *build small, make it work, make it interesting.*

## Problem

Entering an unfamiliar codebase, developers struggle with: what the project does, how it's organized, which files matter, where the app starts, and where a feature lives.

## Features

- `codelens scan` — structure overview (languages, manifests, likely entry points). No AI call.
- `codelens analyze` — architectural explanation from **actual source content**, saved to `codelens-analysis.md`.
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
ollama pull qwen2.5:3b
ollama list   # confirm qwen2.5:3b is present
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
codelens scan /path/to/repo
codelens analyze /path/to/repo
codelens ask /path/to/repo "Where is authentication implemented?"
codelens ask /path/to/repo "How does source verification work?"
```

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

## License

MIT — see [LICENSE](LICENSE).
