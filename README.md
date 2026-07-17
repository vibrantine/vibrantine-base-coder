# Base Coder

Base Coder is the smallest trustworthy unit of coding work built on
[Vibrantine](docs/reference/vibrantine-readme.md).

Given one bounded task and one bound workspace, a Base Coder Commission inspects
the repository, makes scoped changes when authorized, runs relevant checks, and
returns a typed account of what happened. It may iterate through tools and model
turns, but it does not delegate to other coding agents.

```text
CodingTask -> BaseCoder -> CodingOutcome
                  |
                  +-> workspace-scoped deterministic tools
```

Atomic refers to the composition boundary, not a single model call. Broader
systems can decompose goals, run investigations, request independent review,
preserve sessions, or coordinate several Base Coder invocations without putting
those responsibilities inside the coder itself.

## Status

The project now has a runnable atomic `BaseCoder` using Vibrantine's default
LLM loop, a packaged runtime prompt, the standard seven-tool toolbox, and a
tested public task and outcome contract. A thin one-shot CLI and isolated
evaluation-matrix runner now exercise that same Commission without adding
coding logic or orchestration to it.

Local development uses the neighboring Vibrantine 0.6.0 checkout through an
editable `uv` source. The repository's `main` branch tracks the published
GitHub repository.

## Implemented Foundation

The implementation currently contains:

- one `BaseCoder` Commission using Vibrantine's default LLM loop;
- a small typed task and outcome contract;
- Vibrantine's standard list, glob, grep, read, edit, write, and shell tools;
- deterministic contract tests using scripted model responses;
- a one-task JSON CLI for OpenAI-compatible model profiles;
- model × prompt × repetition evaluations over fresh fixture workspaces;
- evaluator-owned oracle checks and credential-redacted run artifacts.

The remaining first-release work is to replace the example model identifiers,
run the localized-defect suite against pinned models, and expand the fixture
corpus only from observed gaps.

It will not contain subagents, planners, reviewers, fan-out, durable sessions,
repository maps, worktree coordination, or a custom coding orchestrator.

## One-Shot CLI

Create a `CodingTask` JSON file, then bind it to one workspace and model:

```bash
uv run base-coder C:/absolute/path/to/repository \
  --task task.json \
  --model provider/model-id \
  --base-url-env BASE_CODER_EVAL_BASE_URL \
  --api-key-env BASE_CODER_EVAL_API_KEY \
  --env-file evals/.env.local
```

The command prints the typed `CommissionResult` as JSON. It exits `0` for
`completed` or `no_change_needed`, `2` for an honest unfinished goal
disposition, and `1` for runner or framework failure.

## Evaluation Matrix

The tracked example runs two model slots, two prompt variants, and three
repetitions against the same localized-defect task. Inspect its 12 cells
without credentials or provider calls:

```bash
uv run base-coder-eval evals/suites/localized-defect.toml --dry-run
```

See [`evals/README.md`](evals/README.md) for environment setup, live execution,
result artifacts, and suite authoring.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv build
```

## Documents

- [`BRIEF.md`](BRIEF.md): the first measurable efficacy bar.
- [`AGENTS.md`](AGENTS.md): repository implementation policy.
- [`docs/base-coder-design-reference.md`](docs/base-coder-design-reference.md):
  the active atomic design and rationale.
- [`docs/coding-orchestrator-design-reference.md`](docs/coding-orchestrator-design-reference.md):
  the preserved earlier multi-Commission design, deferred above Base Coder.
- [`docs/reference/vibrantine-authoring.md`](docs/reference/vibrantine-authoring.md):
  the copied Vibrantine Commission authoring contract.

## Guiding Test

Base Coder succeeds when one Commission can complete one coherent repository
task and hand back enough evidence for its caller to trust or correctly reject
the result. Additional architecture must earn its place by improving that
outcome in evaluation.
