# Base Coder Repository Instructions

## Mission

Build the smallest trustworthy atomic coding Commission on Vibrantine.

Base Coder receives one bounded coding task, operates inside one bound
workspace, and returns a typed, evidence-backed outcome. It may use a bounded
model/tool loop, but it does not delegate to another coding Commission or own
product-level orchestration.

The active design is
[`docs/base-coder-design-reference.md`](docs/base-coder-design-reference.md).
The concise efficacy contract is [`BRIEF.md`](BRIEF.md). The former multi-agent
design is retained only as future-layer context in
[`docs/coding-orchestrator-design-reference.md`](docs/coding-orchestrator-design-reference.md).

## Boundary

Keep the first Base Coder implementation atomic:

- One BaseCoder Commission owns one coherent coding task.
- Vibrantine's default LLM loop provides inspection, editing, verification, and
  conclusion turns.
- The toolbox contains deterministic workspace tools, not child coding
  Commissions.
- The caller owns task decomposition, subagents, parallelism, durable sessions,
  checkpoints, user interaction, approvals, and cross-call coordination.
- Goal disposition belongs in Base Coder's typed output and remains separate
  from `CommissionResult.status`.

Do not add planners, reviewers, scouts, risk adjudicators, repository maps,
worker pools, custom orchestration loops, or persistence layers without
evaluation evidence that the atomic contract cannot meet the BRIEF.

## Construction and Authority

Bind the workspace and tool authority when constructing Base Coder. Task input
describes the goal, acceptance criteria, and constraints; it does not grant a
workspace or additional effects. The workspace is trusted run context included
in the model's opening message.

Use Vibrantine's standard tools directly in the first implementation. Its file
tools accept absolute paths, and `ShellTool` accepts a model-selected working
directory. The caller must therefore provide the actual filesystem, process,
network, and approval sandbox. Do not claim that the workspace constructor,
prompt instructions, capability names, or command parsing provide
operating-system containment.

Use the smallest toolbox that meets the efficacy bar. The initial toolbox is
exactly `ListDirTool`, `GlobTool`, `GrepTool`, `ReadTool`, `EditTool`,
`WriteTool`, and `ShellTool`. Add stronger effects or local tool adapters only
with a concrete observed need and proportionate tests.

## Implementation Approach

Prefer an ordinary `Commission[CodingTask, CodingOutcome]` using Vibrantine's
default `_run`. A custom Commission loop requires a demonstrated contract or
efficacy failure, not anticipated future orchestration.

Keep the public contract small and typed. Every Pydantic field needs a useful
description. Inject model names and deterministic tools through construction.
Invoke Commissions through Vibrantine's public run entry points so cost,
provenance, cancellation, limits, overflow, and persistence behavior remain
consistent.

The packaged runtime prompt belongs beside the package source. `AGENTS.md` is
repository-development policy, not the runtime system prompt.

## Workspace Changes

Assume pre-existing changes belong to the user. Before modifying files:

- inspect repository instructions and relevant source;
- record current revision and status when Git metadata is available;
- confirm an edited file still matches the inspected version;
- avoid unrelated formatting or generated-file churn.

Use one logical writer. Preserve encoding and line endings where practical.
Change generated artifacts through their project mechanism. Never use broad
workspace resets as recovery, and reverse only changes attributable to the
current task.

Keep implementation scoped to the requested outcome. Do not fold framework
refactors or future orchestrator work into Base Coder unless a failing focused
test proves the dependency.

## Verification

Define useful evidence before changing behavior. Start with the cheapest check
capable of disproving the claim, then broaden according to risk and blast
radius:

1. Inspect affected source and the final diff or equivalent state.
2. Run focused behavioral tests.
3. Run relevant formatting, linting, and type checks.
4. Run subsystem or full-suite checks only when warranted.
5. Review the result against the task and acceptance criteria.

Use test-first implementation when a stable automated test can express changed
behavior at reasonable cost. Do not weaken, delete, skip, or rewrite meaningful
coverage merely to obtain a pass. Classify unavailable or failing checks
honestly and do not generalize a focused pass to the whole project.

Contract tests use Vibrantine's scripted model seam and temporary workspaces.
Efficacy tests use pinned models and deterministic repository fixtures. A model
transcript is diagnostic evidence, not proof of repository correctness.

## Current Repository State

This repository now contains the runnable default-loop `BaseCoder`, its packaged
prompt, the exact standard seven-tool toolbox, the tested typed task and outcome
contract, a thin one-shot CLI, and an isolated evaluation-matrix runner. Live
evaluations belong under `evals/`, remain separate from deterministic `pytest`
tests, and must use external credentials plus evaluator-owned oracle checks.
The neighboring `../vibrantine` checkout is the current local framework
dependency; its public API and tests are authoritative over copied documentation
when they differ.

The Git repository was initialized as new history on `main`. Continue with the
next incomplete step in the active design reference and preserve the strict
contract tests as the public boundary grows. Never commit `.env.local` or place
credential values in suite configuration, output records, logs, or fixtures.

## Handoff

Report the result first, followed by changed paths, verification actually run,
material residual risk, and remaining work. A partial or blocked result states
the stopping reason and exact next action. Keep claims concise and supported by
repository evidence.
