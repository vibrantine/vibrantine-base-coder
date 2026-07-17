# Base Coder Design Reference

## Status and Purpose

Base Coder is the smallest trustworthy unit of coding work built on
Vibrantine. It accepts one bounded coding task, works inside one bound
workspace, and returns a typed account of the result.

This document defines the intended first implementation. It deliberately
excludes decomposition across workers, subagent coordination, durable sessions,
and other product-level orchestration. The previous design for those concerns
is preserved in
[`coding-orchestrator-design-reference.md`](coding-orchestrator-design-reference.md).

The Python package, typed task and outcome contract, default-loop `BaseCoder`,
packaged prompt, standard toolbox wiring, thin CLI, and evaluation matrix runner
now exist. Contract changes must
preserve the boundary and non-goals below and update their lock tests.
Vibrantine's current authoring contract is preserved in
[`reference/vibrantine-authoring.md`](reference/vibrantine-authoring.md).

## 1. Definition

Base Coder is one ordinary, model-directed Commission with deterministic coding
tools in its toolbox:

```text
caller or future orchestrator
          |
          v
BaseCoder Commission
  inspect -> change -> verify -> conclude
          |
          v
standard Vibrantine deterministic tools
```

Atomic describes the composition boundary, not the number of model turns. Base
Coder may use Vibrantine's bounded model/tool loop to inspect a repository,
revise a hypothesis, make edits, run checks, and inspect the result. It remains
atomic because it does not dispatch another coding Commission or divide
ownership of the task.

The caller supplies a coherent coding task. A broader system may decompose a
product goal into several such tasks, run independent investigation, request
review, preserve sessions, or coordinate multiple Base Coder calls. Those are
uses of Base Coder, not features inside it.

## 2. Design Principles

### One Useful Boundary

Base Coder should prove that Vibrantine's basic Commission abstraction can hold
a real coding worker. Prefer the framework's default LLM loop. Add custom Python
control flow only if a focused test or evaluation demonstrates that the default
loop cannot meet the efficacy bar.

### Outcome, Not Choreography

The Commission owns the bounded task outcome. It may perform incidental
inspection and verification required to complete that task, but it does not
invent adjacent cleanup or a larger roadmap.

The prompt describes responsibilities and stopping conditions rather than a
rigid step script. The model chooses useful tactical actions inside the tool,
workspace, iteration, time, and spend bounds established by the caller.

### Evidence Before Completion

A successful model turn is not proof that a coding task succeeded. Base Coder's
typed output distinguishes the goal disposition from
`CommissionResult.status` and reports the checks that materially support its
claim.

### Capability at Construction

The workspace and toolbox are capabilities, not untrusted task data. They are
bound when the Base Coder instance is constructed. The task input describes
what to accomplish; it does not grant itself access to a different workspace or
additional effects.

### No Hidden Product Layer

Base Coder has no durable memory, session manager, user interaction loop,
repository index, worker pool, or approval service. It operates on the state
visible in the supplied workspace and returns one result. Callers own everything
between invocations.

## 3. Contract

### Construction

The intended construction shape is:

```python
coder = BaseCoder(
    workspace=workspace_root,
    model="coding-model",
    max_iterations=...,
)
```

`workspace` is resolved once and included as trusted context in the opening
message. The first implementation uses Vibrantine's standard tools, which take
absolute paths; the workspace setting guides the task but does not itself
enforce containment. Model, iteration, time, spend, persistence, cancellation,
and tool-exposure ceilings continue to use Vibrantine's existing run and
Commission mechanisms.

A caller that wants a read-only coder narrows the model-visible menu through
Vibrantine capabilities or the run-wide tool ceiling. Authority is represented
by the effective toolbox and surrounding process sandbox, not by prose fields
the model can reinterpret.

### Task Input

The initial typed input should remain small:

```text
CodingTask
  goal: str
  acceptance_criteria: list[str]
  constraints: list[str]
```

Only `goal` must be required. Criteria and constraints let a caller make
important expectations explicit without introducing a plan or orchestration
schema.

The workspace does not belong in `CodingTask`: placing it there would let a
single preconstructed toolbox serve arbitrary paths and would confuse task data
with granted capability.

### Typed Outcome

The output should cover the smallest useful receipt:

```text
CodingOutcome
  disposition
  summary
  changed_paths
  verification
  unresolved_issues
  residual_risks
```

Goal dispositions are independent of Vibrantine execution status:

- `completed`: the bounded goal is met and materially verified.
- `no_change_needed`: inspection established that no workspace change is
  required.
- `partially_completed`: useful in-scope work was completed, but a material
  criterion remains unmet or unverified.
- `needs_input`: a user-owned choice or missing fact prevents a responsible
  result.
- `needs_approval`: the necessary next effect was not in the supplied grant.
- `blocked`: no viable in-scope route was found under current conditions.

Each verification record should state the command or inspection, its scope,
whether it passed, failed, was unavailable, or remained inconclusive, and a
short result. It is a compact receipt, not a transcript.

`CommissionResult.status="success"` means Base Coder returned this intended
typed outcome. A typed `blocked` or `needs_input` disposition can therefore be
a successful Commission execution. Provider failures, cancellation, malformed
output, framework exhaustion, or internal errors remain envelope failures.

## 4. Workspace Tools

### First Toolbox

The first implementation uses Vibrantine's existing tools directly:

```python
toolbox = (
    ListDirTool(),
    GlobTool(),
    GrepTool(),
    ReadTool(),
    EditTool(),
    WriteTool(),
    ShellTool(),
)
```

Together they cover repository discovery, text search, bounded reading,
exact-string editing, file creation or replacement, Git inspection, and normal
test, build, formatting, and type-checking commands.

Dedicated delete, move, fetch, repository-map, Git-hosting, browser, and
sub-Commission tools are excluded initially. They may be proposed later with a
specific efficacy case and proportionate safety behavior.

### Workspace Scope

Vibrantine's current standard file tools accept absolute paths and do not bind a
workspace root. Base Coder includes its constructor-bound workspace in the
opening task message, but prompt context is not security enforcement.

The caller must run the first Base Coder inside a filesystem and process sandbox
that constrains actual effects. Workspace-bound tool adapters are a deferred
Vibrantine candidate, to be recommended only if evaluation or a second consumer
demonstrates that caller containment is insufficient or repeatedly duplicated.

### Shell Boundary

Vibrantine's `ShellTool` accepts a model-selected `cwd`. Base Coder instructs the
model to use the bound workspace, but a shell command can still name absolute
paths, network clients, or parent directories.

The caller must therefore run Base Coder inside an appropriate filesystem,
network, process, and approval sandbox. The Commission documents this boundary
instead of claiming that command-string inspection provides isolation.

### Existing Work

Base Coder treats pre-existing workspace changes as belonging to the user. It
inspects status and relevant diffs before mutation when the workspace supports
them, rereads a file before editing it, avoids unrelated formatting churn, and
does not use broad reset operations as recovery.

The first implementation relies on direct inspection rather than a persistent
mutation ledger. A future orchestrator may add durable baselines, leases, and
cross-call reconciliation above this atomic unit.

## 5. Execution Behavior

Base Coder rides Vibrantine's default model loop. Its packaged system prompt
should establish these responsibilities:

1. Read repository-local instructions relevant to the task.
2. Inspect only enough context to choose a responsible next action.
3. Preserve unrelated work and remain inside the bound workspace.
4. Make the smallest coherent change that addresses the goal.
5. Run the cheapest relevant check capable of disproving completion.
6. Inspect affected source and the final diff or equivalent state.
7. Conclude with the typed outcome, including failures and uncertainty.

These are behavioral obligations, not separately dispatched phases. The model
may interleave inspection, editing, and verification as evidence changes.

For a behavioral change, the model should identify or create a stable focused
test before implementation when practical. Pure documentation, configuration,
generated output, and straightforward refactors may be verified by more
appropriate evidence. Tests must not be weakened or skipped merely to obtain a
pass.

Base Coder does not ask the user questions during its run. When a material
choice cannot be inferred, it returns `needs_input` with the missing decision
and the safe current state. An interactive caller may then gather the answer
and invoke Base Coder again.

## 6. Verification and Testing

### Deterministic Contract Tests

Use Vibrantine's scripted model seam and temporary workspaces to cover:

- construction and exact tool exposure;
- typed opening input and typed conclusion;
- workspace path acceptance and escape rejection;
- a read, edit, focused-check, inspect, and conclude sequence;
- no-change, partial, needs-input, and blocked outcomes;
- non-zero check results remaining visible to the next model turn;
- cancellation and iteration or budget exhaustion through the framework;
- preservation of unrelated dirty files;
- honest reporting of changed paths and verification.

The tests exercise the real Vibrantine loop and deterministic tools without an
API key. They test the contract around model behavior, not the intelligence of
a scripted response queue.

### Efficacy Evaluations

Pinned-model evaluations use small, deterministic repository fixtures. The
first corpus covers:

- a localized defect with a focused regression test;
- a small feature spanning a few files;
- a correct no-change diagnosis;
- a dirty workspace containing unrelated edits;
- a task whose missing information or unavailable verification requires an
  honest unfinished outcome.

Evaluation considers repository correctness, unrelated mutations,
verification quality, disposition honesty, cost, model turns, and transcript
evidence. The release bar lives in [`../BRIEF.md`](../BRIEF.md).

## 7. Package Shape

The package remains intentionally compact:

```text
src/vibrantine_base_coder/
  __init__.py
  cli.py
  commission.py
  eval_cli.py
  evaluation.py
  models.py
  py.typed
  prompts/system.md
tests/
evals/
  fixtures/
  prompts/
  suites/
```

The Commission imports the standard Vibrantine tools directly; there is no
local `tools/` package.

There is no coordinator module, planner, reviewer, state store, repository-map
service, or application framework. A thin example or CLI may bind a workspace,
register a model, invoke one task, and render the outcome, but it contains no
additional coding logic.

## 8. Deferred Above the Atomic Boundary

The following concerns are intentionally deferred to callers or a future
coding-orchestrator project:

- decomposing broad goals into tasks;
- subagents and parallel investigation;
- independent planner, reviewer, test-designer, or risk-adjudicator roles;
- multi-worker write coordination and isolated worktrees;
- durable sessions, journals, checkpoints, and resume;
- repository maps and cross-run caches;
- workspace leases and concurrent-user reconciliation;
- interactive approval and user-question flows;
- aggregate budgets and concurrency across several coding calls;
- deployment, publishing, messaging, and other external workflows.

These are not rejected ideas. They are deliberately placed one layer higher so
Base Coder remains a reusable component rather than becoming its own product
orchestrator.

## 9. Implementation Sequence

1. **Completed:** bootstrap the Python package and bind the neighboring
   Vibrantine checkout for local development.
2. **Completed:** add the typed task, outcome, verification, and disposition
   models with contract tests.
3. **Completed:** wire the exact standard Vibrantine toolbox and test its
   exposure, capability narrowing, and opening workspace context.
4. **Completed:** implement `BaseCoder` as a basic Commission over Vibrantine's
   standard tools.
5. **Completed:** exercise the complete read, edit, shell-check, and conclude
   loop with scripted model responses.
6. **Completed:** add the thin runner and an isolated model × prompt × repetition
   evaluator with a localized-defect fixture and independent oracle.
7. Run the fixture against pinned model profiles and revise the prompt or
   contract only from observed failures against the BRIEF.

The first milestone is not orchestration. It is one bounded task completed by
one Commission with a trustworthy receipt.
