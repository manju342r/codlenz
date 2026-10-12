# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Split static files (HTML/CSS/JS) served by the existing stdlib `http.server` demo server. Zero web dependencies — no frameworks, no build step, no CDN. User chose split files over the single inline `PAGE` string.

## Users

Primary: hackathon judges at Hacktoberfest Hack Day (MLH × NIAT-KKH) watching a 2-minute live demo — they need to grasp what CodeLens does and why verified references matter within seconds.

Secondary: developers using the page as a real tool to scan, explain, and question unfamiliar codebases — they need task efficiency on repeat visits.

## Product Purpose

CodeLens helps developers understand unfamiliar codebases through explanations backed by independently verified source references, using a local open-weight model (Qwen 2.5 3B via Ollama). Nothing leaves the machine. The web page is the demoable face of a CLI product: it must make the scan → analyze → ask workflow legible live, and make ✅ verified vs ❌ rejected references instantly readable. Success for judges: the trust story lands in under two minutes. Success for developers: the page answers "where is this implemented, and can I trust that answer" faster than the terminal.

## Positioning

A neighboring code-explainer cannot truthfully copy this: every model-cited reference is independently re-checked by Python (file exists, line range valid, quote matches exactly) before it is shown as evidence, and failed references are displayed as rejected rather than hidden. Local-only inference with no accounts, keys, or cloud is a product guarantee, not a deployment detail.

## Operating Context

Live demo ritual: presenter runs `codelens serve`, opens `http://127.0.0.1:8000`, and walks scan → analyze → ask on a real repository while narrating. Model calls take ~13–17s each; the page must carry that wait honestly. Developer workflow: paste a repo path, scan structure, read the architectural explanation, ask targeted questions, judge answers by their ✅/❌ references. Evaluation happens on localhost against real repositories, including CodeLens analyzing itself.

## Capabilities and Constraints

Confirmed functionality: repo scan (languages, manifests, likely entry points — instant, no AI); architectural analysis from actual source content (saved to `codelens-analysis.md`); keyword-retrieval Q&A returning answer plus verified/rejected reference lists.

Constraints: stdlib-only server (`codelens/server.py`), binds 127.0.0.1, read-only analysis; MIT-licensed public repo; no paid APIs, embeddings, or vector databases; small-model output varies run to run, so the UI must present both ✅ and ❌ outcomes as first-class results, never hide failures.

Undecided: whether analyze output persists server-side between sessions; exact question history behavior.

## Brand Commitments

Name CodeLens is established (repo, README, CLI, skill). No logo, palette, voice, or other identity assets exist. The terminal UI uses ✅/❌ markers and Rich panels — the web page should preserve that verified/rejected vocabulary.

## Evidence on Hand

Working CLI (`scan`, `analyze`, `ask`, `serve`); live demo server on port 8000; real `analyze`/`ask` transcripts against this repo (see `examples/self-analysis-sample.md`); README with architecture and limitations. No testimonials, benchmarks, or brand assets — future work must not fabricate any.

## Product Principles

1. Evidence over assertion: show the reference and its verification state, never ask for trust.
2. Local-first is the feature: offline-capable, no accounts, nothing leaves the machine — the UI should say so plainly.
3. Honest about uncertainty: INFERRED and UNSUPPORTED are valid, visible outcomes, not error states to decorate away.
4. Demo-speed legibility: a first-time viewer understands the workflow within one screen, without reading docs.
