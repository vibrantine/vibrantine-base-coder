# Base Coder Evaluations

This directory contains live, potentially costly model evaluations. They are
separate from deterministic unit tests and do not run under `pytest`.

Each suite defines a model × prompt × repetition matrix. Every matrix cell
receives the same typed task and a fresh copy of the fixture workspace. After
the Commission finishes, evaluator-owned oracle commands check the resulting
workspace independently of the model's own report.

Fresh copies prevent cross-run contamination; they are not an operating-system
sandbox. Run live suites inside a caller-provided sandbox that restricts the
process to the intended evaluation workspace and network targets.

## Configure

Copy `.env.example` to `.env.local` and set the credential for your
OpenAI-compatible endpoint. `.env.local` is ignored by Git. Existing process
environment variables take precedence over values in the file.

Model entries name environment variables rather than containing credentials:

```toml
[[models]]
name = "candidate-a"
id = "provider/model-a"
base_url_env = "BASE_CODER_EVAL_BASE_URL"
api_key_env = "BASE_CODER_EVAL_API_KEY"
```

Use `api_key_env = ""` for a keyless local OpenAI-compatible endpoint.

## Inspect and Run

Inspect the complete matrix without loading credentials or calling a model:

```bash
uv run base-coder-eval evals/suites/localized-defect.toml --dry-run
```

Run it back-to-back, automatically loading `evals/.env.local`:

```bash
uv run base-coder-eval evals/suites/localized-defect.toml
```

Each invocation creates a timestamped directory under `evals/results/`.
Per-run records include model identity, prompt/task/fixture hashes, the typed
Commission result, provider-call ledger, independent oracle output, and a
Vibrantine trace containing the model/tool transcript. Use `--keep-workspaces`
when the post-run fixture state should also be retained for inspection.

Prompt variants are either the packaged baseline, an appended instruction
file, or a complete replacement:

```toml
[[prompts]]
name = "baseline"

[[prompts]]
name = "verification-emphasis"
append_file = "prompts/verification-emphasis.md"
```

Paths in suite files are relative to this `evals/` directory and may not
escape it.
