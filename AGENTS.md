# AGENTS.md — CodeLens (hacktober-kkh)

## Run
- Commands: `codelens scan|analyze|ask|serve`. After `pip install -e .`, `codelens` is on PATH.
- Use `pip3` — bare `pip` is not on PATH on this machine. System python is 3.14 (requires >=3.10).
- No-install fallback: `PYTHONPATH=. python -c "from codelens.cli import main; main()" <cmd>`.
- Entry: `codelens/cli.py` (`main()` Click group). No other entrypoints.

## Model (local only)
- Ollama at `localhost:11434`, model `qwen2.5:3b`. Check with `ollama list`; pull with `ollama pull qwen2.5:3b`.
- `model_client.chat_json` sets `num_ctx=16384` — required. Ollama's runner defaults to 4096 ctx and large prompts fail with HTTP 500 without the override. Don't remove it.
- Never add paid/cloud LLM APIs, embeddings, or vector DBs — local-only is the product's core claim.

## Architecture (read before changing)
- `scanner.py` produces the shared repo index; `scan`/`analyze`/`ask`/`serve` must all reuse it. Never add per-command scanning.
- `retriever.py` is keyword scoring only (filename/def/import/content). Keep it that way.
- `verifier.py` is the trust boundary: model refs are guilty until proven innocent. Display ✅ only from `verify_refs`; never render a model-cited file:line as fact.
- `server.py` is stdlib-only (`http.server`), binds 127.0.0.1, read-only analysis. Keep zero web dependencies.

## Frontend
- The demo page is `static/` (index.html, styles.css, app.js), served by `server.py`. For any UI polish, load the `impeccable` skill first and follow it.
- Visual authority: `DESIGN.md` + `.impeccable/design.json` (generated from the built CSS — update both if tokens change). Product context: `PRODUCT.md`. Surface contract: `.impeccable/surfaces/static-index-html.md`.

## Verify (no test suite exists)
- No pytest/unittest config — verify with live runs: invalid-path scan (expect exit 2), `analyze` + `ask` against this repo itself, and the 7-case verifier matrix (`valid` accepted; bad-quote/traversal/bad-range/beyond-EOF/missing-file/absolute rejected).
- `codelens-analysis.md` output is gitignored; the committed sample lives in `examples/`.

## Packaging gotchas (both broke `pip install -e .` before)
- `pyproject.toml` pins `packages.find.include = ["codelens*"]` because `skill/` and `prompts/` are data dirs — don't add `__init__.py` there or treat them as packages.
- `prompts/*.md` are documentation mirrors; the prompts the model actually receives live in `prompt_builder.py`. Update both.

## Ship
- Public GitHub push needs explicit user approval. Never push unasked.
