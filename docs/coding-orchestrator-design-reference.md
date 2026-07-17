# Coding Orchestrator Design Reference

## Status and Purpose

This document preserves the earlier architecture for a multi-Commission coding
orchestrator. It is future-layer material, not the design of the atomic Base
Coder. The active Base Coder boundary is defined in
[`base-coder-design-reference.md`](base-coder-design-reference.md).

The orchestrator described here composes planning, acting, review, fan-out,
checkpointing, and recovery around coding workers. It remains useful as a
design record for a later product, but none of these facilities belong inside
the first Base Coder implementation.

Historical terminology is left intact below. References to “Base Coder” in the
preserved body mean the former orchestrated system, not the atomic Commission
defined by the active design.

The repository implementation policy lives in [`../AGENTS.md`](../AGENTS.md).
Vibrantine-facing framework proposals discovered during the original design
are retained outside this repository for now; the recommendations most
specific to coordination should be reconsidered only after an atomic coder
provides implementation evidence.
Vibrantine's current authoring contract is preserved in
[`reference/vibrantine-authoring.md`](reference/vibrantine-authoring.md).

## 1. Design Principles

### Constrained Outcome Ownership

Base Coder owns the outcome requested by the user, not merely a literal list of
operations. It may inspect, plan, implement, and verify work directly necessary
to reach that outcome, while avoiding adjacent improvements that are merely
convenient or attractive.

Authority depends on request type. Explanation, review, diagnosis, and design
requests are read-only unless implementation is also requested. Change, fix,
and build requests authorize goal-connected workspace mutation and
verification. External effects such as deployment or publishing require a goal
or caller grant that includes those effects.

This is the middle ground between a brittle task executor and an autonomous
repository steward. The agent should finish implied necessary work without
inventing a larger mission.

### Managed Predictive Behavior

Vibrantine should bound independent decisions rather than prevent them. Base
Coder therefore separates hard envelopes from model discretion:

- Typed input and output define the contract.
- Capabilities and workspace scope define reachable effects.
- Budgets, cancellation, concurrency, and stopping policy bound execution.
- One writer and typed state bound mutation and coordination.
- Inside those bounds, model-directed Commissions may choose hypotheses, tools,
  sequencing, and useful intermediate steps.

Operating modes and plans are policy profiles, not scripts. The actor is
allowed to discover a better tactical route. Material changes to behavior,
scope, risk, or authority return to the coordinator.

### Evidence Before Confidence

Completion is a claim about the repository, not the actor's subjective sense of
progress. Material acceptance criteria are tracked with their source and a
status of `met`, `unmet`, `unverified`, or `not_applicable`. Completion requires
proportionate evidence, no known in-scope defect, and a coherent handoff.

Tests are one kind of evidence. They do not automatically prove the user's goal
was met, and lack of a suitable test does not make every task impossible to
verify. The system selects evidence according to behavior, risk, and available
tooling.

### Goal Disposition Is Not Execution Status

Vibrantine's `CommissionResult.status` describes execution of the Commission
contract. Base Coder's typed output separately describes the goal disposition:

- `completed`
- `no_change_needed`
- `partially_completed`
- `needs_input`
- `needs_approval`
- `blocked`

A coordinator may successfully return a trustworthy blocked outcome. Framework
failure is reserved for cases where cancellation, hard exhaustion, provider
failure, malformed output, overflow, or an internal fault prevents the intended
result.

### State Is Explicit

Commissions do not retain hidden memory between invocations. Transient state
lives in coordinator-local variables; durable state belongs to the caller and
is threaded back through typed input or a checkpoint reference. Heavy state
such as source trees, maps, logs, and artifacts passes by handle.

## 2. System Architecture

### Layers

Base Coder has three control layers:

```text
Outer Orchestrator
  session, workspace lease, grants, checkpoints, user interaction
      |
Coding Coordinator Commission
  goal state, planning, transitions, budgets, synthesis, exit
      |
Bounded Child Commissions and Deterministic Tools
  planning, acting, scouting, reviewing, adjudication, repository effects
```

The outer orchestrator owns durable sessions and maximum authority. It starts,
cancels, resumes, or supersedes coding runs; handles genuine human escalation;
and renders progress and outcomes. It does not micromanage tool calls.

The coding coordinator is a custom Commission whose `_run` owns the adaptive
state machine. It dispatches children through Vibrantine's public entry points,
passes narrowed contexts, sums child cost, checks cancellation, checkpoints
stable state, and returns a complete result envelope.

Model-facing leaf roles are basic Commissions where practical. They ride
Vibrantine's default tool loop and conclude through typed output. Deterministic
repository operations remain tools because they contain no LLM call.

### Progressive Deliberation

The coordinator chooses the lightest process justified by current evidence:

- **Direct:** orient, act, verify, decide.
- **Deliberate:** add an explicit rolling plan and bounded action slices.
- **Coordinated:** add independent read-only scouts and explicit review.
- **Guarded overlay:** add risk-specific critique, adjudication, and stronger
  verification regardless of execution depth.

Risk is an overlay because a small authentication edit may be high risk while a
broad documentation change may be low risk. Guarded treatment applies to
security, credentials, persistent data, compatibility, destructive operations,
and external systems.

The coordinator may escalate when scope expands, assumptions fail, criteria are
ambiguous, verification exposes wider effects, or parallel investigation can
reduce uncertainty. It may remove unnecessary ceremony after uncertainty is
resolved, but it cannot discard applicable safeguards.

### Adaptive Coding Loop

The conceptual states are:

```text
orient -> plan -> act -> verify -> review -> decide -> exit
```

They are not a mandatory sequence. A direct run may skip explicit plan and
independent review. New evidence may return any path to orientation or planning.

Orientation gathers only enough context to choose the next responsible action.
It normalizes the goal, identifies initial criteria, reads local instructions,
inspects relevant code and tests, detects existing changes, and selects an
execution depth and safeguards. It should not scan the entire repository by
default.

The plan uses rolling-wave detail: a coarse goal roadmap plus one concrete
active slice. The active slice names its intended outcome, likely scope,
constraints, risks, expected verification, and invalidating conditions. Later
steps remain coarse until evidence makes detail useful.

The actor pursues one coherent, reviewable slice. It may inspect, edit, and run
focused checks while choosing tactics freely. It returns a typed report of
changes, findings, evidence, unresolved issues, and its recommended transition.
The coordinator treats that recommendation as advice, updates state, and
chooses whether to inspect, continue, verify, review, replan, suspend, or exit.

Repeated episodes that produce no new evidence, repository change, viable
hypothesis, criterion update, or clearer blocker must trigger replanning and
eventually a controlled stop.

### Repository Orientation Map

An optional repository map accelerates repeated orientation but never replaces
direct inspection. It has three retrieval layers:

- A compact digest of stack, commands, entry points, and major subsystems.
- Module entries describing purpose, boundaries, dependencies, and tests.
- On-demand file entries containing path, role, symbols, relationships, and a
  content fingerprint.

Structure, symbols, imports, test relationships, and fingerprints should be
derived deterministically where practical. Model summaries are additive and
cannot override extracted facts. The caller owns the map, refreshes changed
entries incrementally, and supplies only the compact digest by default. Current
source and tool results are always authoritative.

The first implementation may use ordinary search without a map. A full indexer
is justified only when evaluations show repeated discovery is a material cost.

## 3. Typed Contracts and State

Exact Pydantic fields remain to be implemented, but the contracts should cover
the following stable concepts.

### Request and Goal

```text
CodingRequest
  goal
  workspace_handle
  constraints
  autonomy_profile
  budget_policy
  optional_checkpoint_ref

GoalSpec
  objective
  acceptance_criteria
  constraints
  consequential_assumptions
  approval_requirements
```

Criteria retain whether they came from the user, repository contracts, or a
conservative inference. Material inferred criteria and assumptions remain
visible rather than silently becoming requirements.

### Plan and Action

```text
Plan
  goal_summary
  relevant_criteria
  assumptions, constraints, risks
  roadmap_steps
  active_step
  verification_strategy
  revision

PlanStep
  id
  intended_outcome
  dependencies
  likely_scope
  expected_evidence
  invalidating_conditions
  status

ActionReport
  findings
  mutations
  checks
  unresolved_issues
  recommended_transition
```

Plan steps use `pending`, `active`, `completed`, `blocked`, or `superseded`.
Completion requires coordinator-accepted evidence, not only an actor claim.
Plan revisions state what changed and which evidence caused the revision.

### Evidence, Review, and Blocking

```text
VerificationRecord
  kind
  command_or_tool
  scope
  status
  concise_result
  affected_criteria
  repository_fingerprint
  output_reference

ReviewDecision
  verdict
  criterion_assessments
  findings
  residual_risks
  missing_evidence
  confidence

BlockerRecord
  category
  evidence
  attempts
  alternatives
  resume_condition
  affected_criteria
```

Verification status is `passed`, `failed`, `unavailable`, or `inconclusive`.
Review verdict is `accept`, `revise`, or `inconclusive`. Findings must identify
specific evidence, behavior, paths, or criteria rather than preferences.

### Workspace State

Before mutation, the coordinator records a lightweight baseline: repository
root, current revision when available, existing status and diff summary,
relevant file fingerprints, and generated-file conventions.

Every intentional mutation records path, operation (`create`, `modify`, `move`,
`delete`, or `generate`), before and after fingerprints, active step, reason,
and producing action. The ledger supports stale-read checks, final review,
precise recovery, map refresh, and reporting.

### Durable Coding State

`CodingState` includes schema and checkpoint versions, session identifiers,
goal and criteria, current mode and phase, plan revisions, repository and map
fingerprints, findings and rejected hypotheses, mutation and verification
records, adjudications, blockers, budget state, and recommended transition.

`CodingOutcome` includes goal disposition, summary, criterion assessments,
changed paths, verification evidence, residual risk, unresolved work, next
action, and final checkpoint reference.

The caller owns a `CodingStateStore`. The coordinator writes atomic, linked
checkpoints after orientation, plan revisions, action slices, fan gathering,
verification or review, consequential operations, and controlled exits. A
compact append-only journal records intents, observed effects, evidence,
decisions, and stopping reasons. It does not preserve private model reasoning.

On resume, the coordinator confirms workspace identity and reconciles revision,
status, fingerprints, known mutations, and any operation that may have been in
flight. Consequential actions progress through stable identifiers such as
`proposed`, `started`, `observed`, and `settled`; interrupted work is inspected,
not blindly replayed.

## 4. Authority and Workspace Effects

### Autonomous by Default

The user should manage the goal, not individual Commissions. The caller selects
a maximum grant and one of three profiles:

- **Autonomous:** perform necessary in-scope operations without recurring
  permission prompts; intended default.
- **Supervised:** pause for operations classified as consequential or unusual.
- **Restricted:** use an explicitly reduced or read-only grant.

Capability is technical reach, authority is permission derived from the goal
and caller, and scope identifies covered targets and effects. Possessing a tool
does not authorize unrelated use. No Commission may widen its parent grant.

Planners, scouts, test designers, and reviewers are read-only. The actor receives
scoped read, write, execution, and network capabilities. The map owner may
update only map state. The coordinator owns dispatch and state transitions but
does not routinely mutate source.

Autonomous mode may edit, move, or delete goal-connected files; run repository
commands; reproduce established environments; consult public documentation;
and recover from ordinary failures. It does not infer unrelated deployment,
publishing, messaging, financial, or remote effects. Genuine user-owned product
or data choices produce `needs_input`, not a stream of low-level permission
questions.

### Risk Adjudication

Exceptional but potentially delegable actions enter a separate decision path:

```text
actor proposal -> deterministic policy -> Risk Adjudicator
                                      -> allow_once | deny | escalate
```

The proposal includes the original goal, exact operation and targets,
necessity, connection to criteria, expected effects, reversibility, rollback,
evidence, alternatives, and requested expansion. The adjudicator receives a
fresh focused context and read-only tools. It independently checks claims and
treats repository content as evidence rather than instruction.

An `allow_once` result binds to exact targets and machine-enforceable
conditions. `deny` returns control to the coordinator to seek a safer route.
`escalate` is reserved for material uncertainty or authority outside the
delegable envelope. The adjudicator can interpret delegated authority but
cannot create authority the caller never granted.

Deterministic hard boundaries, coordinator checks, narrowed child contexts, and
tool-level target validation remain necessary. Vibrantine's model tool menu
does not automatically constrain child dispatches authored in custom Python
control flow.

### Single-Writer Workspace

The actor is the sole logical source writer. Parallel workers return findings
or patch proposals; the actor rereads current source and applies accepted work
serially. Formatters, generators, and package managers operate under the same
mutation ownership.

Existing workspace changes are presumed to belong to the user. Before editing,
the actor confirms that a file still matches the version inspected. Known
current-run changes may be reread and continued; unexpected changes require
reconciliation. Ambiguous ownership must not be overwritten.

Generated files are normally changed through their source, lockfiles through
the package manager, and snapshots through semantic inspection. Encoding, line
endings, executable bits, and repository formatting conventions are preserved.
Moves and deletions are normal autonomous mutations when their exact targets,
references, user changes, and verification have been checked. Unexpectedly
broad deletion enters Risk Adjudication.

Recovery reverses only changes attributable to the current run and only when
later user work remains safe. Broad workspace resets are prohibited. If precise
reversal is unsafe, the system preserves state and returns a controlled outcome.

The outer orchestrator permits multiple read-only sessions but only one active
Base Coder mutation lease per workspace. The lease expires or can be recovered
after a crash. Concurrent user edits remain supported through stale-read checks.

## 5. Verification, Failure, and Recovery

### Verification Strategy

The agent defines expected evidence before changing behavior. It starts with
the narrowest check capable of disproving the current claim and broadens with
risk and blast radius:

1. Inspect affected source and the resulting diff.
2. Run focused behavioral tests.
3. Run relevant formatting, linting, and type checks.
4. Run subsystem tests or builds.
5. Run broader or integration checks when warranted.
6. Perform semantic review against the goal and criteria.

Direct work uses focused evidence. Deliberate work verifies every slice and the
integrated result. Coordinated work verifies integration boundaries and may use
independent review. Guarded work adds domain-specific security, migration,
compatibility, rollback, or data-integrity evidence.

### Test-First Intent

Every behavioral change declares how it will be verified before implementation.
When a stable automated test can express the behavior at reasonable cost, the
agent should establish or identify it first and confirm pre-change sensitivity
when practical and safe. It then implements the change, confirms the focused
result, and runs proportionate regression checks.

Strict red-green implementation is most useful for reproducible defects,
deterministic business behavior, public contracts, boundaries, validation,
parsing, security, and transformation logic. It is not required for pure
refactors with existing coverage, documentation, configuration, generated
artifacts, exploratory diagnosis, or behavior better established by compilation
or external contracts.

Tests must not be weakened, skipped, deleted, or rewritten merely to obtain a
pass. Snapshot updates require inspection. An optional read-only Test Designer
may propose goal-derived cases for broad or guarded work; the actor remains the
only writer.

### Semantic Review

The coordinator always performs a lightweight final review. A fresh read-only
Reviewer Commission is added for broad, guarded, architecturally consequential,
semantically subtle, heavily replanned, or ambiguous work. It receives the
goal, criteria, diff, relevant source, verification records, assumptions, and
risks rather than the actor's complete reasoning transcript.

`revise` returns to action and focused reverification. `inconclusive` gathers
missing evidence or qualifies the outcome. Review loops are bounded; repeated
disagreement without new evidence stops or returns a user-owned tradeoff.

### Failure Model

The system distinguishes:

- **Action issue:** a command, hypothesis, edit, or check failed; this is
  evidence for the loop.
- **Goal blocker:** no safe in-scope route currently exists; this becomes a
  controlled goal disposition.
- **Execution failure:** the Commission cannot produce a trustworthy intended
  result; this uses the framework envelope.

Verification failures normally return to planning or action. Child failures are
errors as values: the parent records cost and error, uses valid sibling output,
retries only when worthwhile, and propagates failure only when it cannot build
a trustworthy parent outcome.

Retry requires evidence that conditions can change, such as a transient timeout,
rate limit, corrected request, released lock, or restored dependency. The system
does not repeat deterministic failures with unchanged input, denied actions,
ambiguous mutations, uncertain external effects, or work that would consume the
protected reserve.

After a failed mutation, the actor inspects actual effects before continuing,
repairing, reversing, or retrying. A command failure does not prove that nothing
changed, and a timed-out non-idempotent action must not be replayed without
reconciliation.

Cancellation starts no new work, safely stops read-only children, inspects
possibly completed effects, writes the best available checkpoint, and exits as
`cancelled`. Unexpected exceptions become structured `internal` failures with
provenance and accumulated cost. Invariant failures stop mutation immediately.

## 6. Budget, Fan-Out, and Concurrency

### Elastic Budgeting

Budget is a ceiling and allocation mechanism, not a target. Depending on the
caller and backend, limits may cover monetary cost, elapsed time, action rounds,
LLM iterations, fan-out, output or context size, and no-progress episodes.

After orientation, the coordinator protects enough capacity for important
verification, final review, and a coherent resumable handoff. A heuristic of
roughly 15–25 percent may initialize this reserve, adjusted for risk and turn
cost rather than fixed universally. Actor work may spend only above the reserve
and should not start when expected cost threatens it.

Allocation is elastic. Orientation and planning stop once enough evidence
exists. Scouts receive small grants only when implementation and verification
remain viable. The actor receives the largest flexible share. Recovery competes
with action budget, not the minimum handoff reserve.

Every child receives an explicit sub-budget. The coordinator sums child cost
and accounts conservatively for concurrent calls in flight. Vibrantine can
overshoot a monetary ceiling because exact output cost is unknown until a turn
finishes, so trees remain shallow and work stops before the hard limit.

Checkpointing after every stable slice makes a controlled
`partially_completed` outcome cheaper than reconstructing state near exhaustion.
Remaining budget never creates an obligation to continue.

### Controlled Fan-Out

Fan-out is optional read-only parallelism, expressed as
`fan -> gather -> decide`. It is used only when at least two questions are
independent, bounded, evidence-producing, and likely to save meaningful time or
reduce uncertainty after accounting for dispatch and synthesis cost.

Each worker receives a focused question, relation to the goal, allowed scope,
expected evidence, exclusions, tools, sub-budget, and stopping condition. It
returns a typed conclusion with source evidence, confidence, unresolved issues,
risks, and recommendations. Siblings do not communicate.

The initial policy allows two or three concurrent workers, fan depth one, and a
single coordinator gather point. Workers cannot spawn workers. A failed worker
does not fail the fan when remaining evidence is useful. Review fan-out uses
distinct lenses rather than repeated generic prompts.

Parallel implementation is deferred. Proposed patches remain typed values until
the actor applies them. Isolated worktrees and integration policy should be
considered only if evaluations show a material benefit.

Fan effectiveness is evaluated through wall-clock time, total cost, unique and
duplicated findings, accepted findings, replanning avoided, and defects found.
Task classes that do not benefit should remain serial.

## 7. Lifecycle, Progress, and Handoff

### Progress and Interaction

Typed progress events form the complete machine-readable stream. The outer
orchestrator decides which events become CLI, UI, log, or conversational
updates. Events carry session and run identifiers, sequence, timestamp, concise
payload, and relevant action or criterion references. Checkpoints, not progress
events, are authoritative for recovery.

User-facing updates occur at meaningful milestones: scope discovery, material
plan revision, completed action slices, confidence-changing verification,
important fan or adjudication results, blockers, final review, or sustained
work without another visible milestone. Updates state current status, important
evidence, and the next action without dumping logs or private reasoning.

Autonomous mode interrupts only for missing information or a decision genuinely
owned by the user. A question explains the decision, why it cannot be inferred,
options and tradeoffs, a recommendation when supportable, and the safe paused
state. New user instructions may add to, redirect, or replace the active goal;
obsolete work stops at the next safe boundary and effects are reconciled.

### Handoff

Every final response renders from `CodingOutcome` and leads with the result.
Completed work reports important changes, paths, verification scope, and
residual risk. No-change outcomes provide evidence. Partial, blocked, cancelled,
or failed outcomes state completed work, known effects, stopping reason,
remaining criteria, checkpoint, and exact resume condition.

Verification reporting names the checks that materially support the claim and
whether they passed, failed, were unavailable, or remained inconclusive. A
focused pass is never generalized to the full suite. Important result counts or
failure lines are relayed when raw tool output is not visible; large logs remain
referenced.

Communication remains concise, direct, calm, and evidence-based. It surfaces
material assumptions and risks without exposing private reasoning or concealing
unfinished work.

### Data Handling

Checkpoints and run records may contain sensitive source, diffs, commands, and
model transcripts. Storage should support configurable retention, credential
redaction, references to large artifacts, schema migration, and
workspace-local or caller-selected roots. Source is not persisted merely
because it entered model context.

## 8. Vibrantine Composition

This section records the provisional implementation shape. Exact Pydantic
schemas, models, persistence adapters, and package layout remain to be designed
and tested.

### Commission Roles

```text
CodingCoordinatorCommission (custom)
  PlannerCommission          (basic, read-only)
  ActorCommission            (basic, sole writer)
  ReviewerCommission         (basic, read-only)
  optional ScoutCommission   (basic, read-only)
  optional TestDesigner      (basic, read-only)
  RiskAdjudicatorCommission  (basic, read-only)
```

The coordinator owns deterministic sequencing, rounds, fan gathering, budget
allocation, checkpoints, and result construction. Planner, actor, reviewer, and
optional specialists own bounded model judgment. Children are injected through
the coordinator constructor with working defaults and model overrides rather
than discovered through global state.

Every child call uses `dispatch(child, typed_input, child_ctx)`. Context is
narrowed to role requirements, cancellation is checked at natural boundaries,
and child cost is summed exactly once. The coordinator returns provenance and
cost on every path and converts unexpected exceptions to structured errors.

The actor may itself be a basic Commission using Vibrantine's default model
loop over a carefully bounded toolbox. Likely deterministic tools include file
listing, search, reading, structured patch application, command execution,
status and diff inspection, and repository-map queries. Tool contracts must
validate workspace boundaries and return bounded, resumable output.

The Risk Adjudicator is invoked by coordinator policy rather than exposed as a
general actor tool. Its decision is checked and bound before the proposed effect
is enabled. Scouts, reviewers, and test designers never receive mutation tools.

### Testing the System

Contract tests use injected scripted model responses and temporary workspaces.
They cover typed messages and outputs, capability menus, cost rollup,
cancellation, persistence calls, budget and iteration behavior, malformed model
responses, tool-result bounds, and every result path.

Coordinator tests exercise direct, deliberate, coordinated, and guarded flows;
plan revision; partial fan failure; stale reads; mutation reconciliation;
adjudication binding; protected reserves; no-progress stopping; checkpoints;
resume drift; and cancellation around mutation.

Evals judge efficacy rather than framework mechanics. They should include
localized fixes, ambiguous diagnosis, cross-module changes, existing dirty
workspaces, test-first regressions, unrelated pre-existing failures, guarded
actions, budget-limited partial outcomes, and adversarial repository content.
Models used in evals are pinned, artifacts are deterministic where possible,
and transcripts are retained for human review.

## 9. Deferred Decisions

The following choices require implementation evidence rather than more abstract
policy:

- Exact Pydantic schemas and package boundaries.
- Whether checkpoints are emitted through progress events, an injected state
  store, or both.
- State-store format, atomicity, retention, and schema migration.
- Repository-map storage and deterministic parser choices.
- Model selection and fallback policy by role.
- Concrete action-round, retry, reserve, and fan thresholds.
- Capability representation for dynamic child-Commission authority.
- Integration with proposed Vibrantine budget scopes and tree-wide concurrency.
- Whether parallel implementation ever justifies isolated worktrees.
- The BRIEF efficacy bar and benchmark corpus for the first release.

These should be resolved through the smallest working coordinator and focused
evaluations. New framework abstractions should be extracted only after a second
real consumer demonstrates repeated structure.
