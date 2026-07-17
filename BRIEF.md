# Base Coder

## Purpose

Base Coder is one atomic Vibrantine Commission that completes one bounded coding
task inside one bound workspace. It inspects, changes, verifies, and concludes
through the standard model/tool loop. It does not delegate coding work.

## Efficacy Bar

A release candidate must satisfy all deterministic contract tests and the
reviewed pinned-model fixture suite.

The contract tests establish that Base Coder:

- exposes no child Commission or orchestration tool;
- receives the constructor-bound workspace in its opening context and exposes
  the exact intended standard Vibrantine toolbox;
- preserves unrelated pre-existing workspace changes;
- can read, edit or write, run a focused check, inspect the result, and return a
  typed outcome through the real Vibrantine loop;
- distinguishes goal disposition from Commission execution status;
- reports changed paths, verification failures, unresolved issues, and residual
  risk without inventing a pass;
- respects cancellation, iteration, time, spend, and tool-exposure bounds
  supplied by Vibrantine and the caller.

Workspace containment is a caller precondition for the first release. The
standard Vibrantine tools accept absolute paths and `ShellTool` is an escape
hatch; evaluation must therefore run inside a caller-provided sandbox and
confirm that no out-of-scope mutation occurred. Base Coder must not claim that
its prompt or toolbox provides operating-system isolation.

The pinned-model suite contains at least these deterministic repository tasks:

1. Repair a localized defect and pass its focused regression test.
2. Implement a small feature spanning more than one file and pass its focused
   checks.
3. Correctly determine that a reported problem requires no change.
4. Complete a task without altering unrelated dirty files.
5. Return an honest unfinished disposition when required information or
   verification is unavailable.

Every fixture must end with the expected repository state, no out-of-scope
mutation, and a disposition supported by the reported verification. Cost,
model-turn count, transcript, and tool use are recorded for diagnosis and
comparison; they do not substitute for repository correctness.

## Non-Goals

The first release does not decompose broad goals, call subagents, coordinate
parallel work, maintain durable sessions, interact with users, manage approvals,
or integrate multiple coding results. Those belong to callers that compose Base
Coder.

## Next Step

Construct the smallest default-loop Commission over Vibrantine's standard tools
and exercise its complete scripted read, edit, verify, and conclude path.
