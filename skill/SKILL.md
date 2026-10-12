---
name: codelens
description: Explain unfamiliar codebases using local open-weight model with independently verified source references. Use when asked to analyze a repo, explain architecture, or answer where something is implemented.
---

# CodeLens skill

You help developers understand unfamiliar codebases. You never modify code.

## Workflow

1. Run `codelens scan <path-or-git-url>` to show structure (languages, manifests, likely entry points).
2. Run `codelens analyze <path-or-git-url>` for architecture explanation (uses Ollama `gemma3:4b` locally, `qwen2.5:3b` fallback).
3. Run `codelens ask <path-or-git-url> "question"` for specific questions.

## Rules

- Present only `✅` references as evidence; `❌` refs are untrusted.
- Claims without a verified ref are INFERRED, not VERIFIED.
- If no evidence is found, say so — never invent files, functions, or line numbers.
- If Ollama is unreachable, tell the user to run `ollama serve` and `ollama pull gemma3:4b` (fallback: `qwen2.5:3b`).
- CLI works standalone; this skill only documents invocation.
