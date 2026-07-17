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

The project has a bootstrapped Python package and a tested first public
contract: `CodingTask`, `CodingOutcome`, `VerificationRecord`, and their closed
status vocabularies. No runnable Base Coder Commission exists yet.

Local development uses the neighboring Vibrantine 0.6.0 checkout through an
editable `uv` source. The repository has been initialized on `main` with no
prior history.

## First Scope

The first implementation will contain:

- one `BaseCoder` Commission using Vibrantine's default LLM loop;
- a small typed task and outcome contract;
- Vibrantine's standard list, glob, grep, read, edit, write, and shell tools;
- deterministic contract tests using scripted model responses;
- pinned-model evaluations against small repository fixtures;
- a thin runner for one task invocation.

It will not contain subagents, planners, reviewers, fan-out, durable sessions,
repository maps, worktree coordination, or a custom coding orchestrator.

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
