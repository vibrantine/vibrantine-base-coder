"""Tests for the thin one-shot command-line runner."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from vibrantine import CommissionResult, CostMetrics, Provenance

from vibrantine_base_coder.cli import main
from vibrantine_base_coder.models import CodingOutcome
from vibrantine_base_coder.runtime import RunRequest


def _successful_result() -> CommissionResult[CodingOutcome]:
    return CommissionResult[CodingOutcome](
        status="success",
        output=CodingOutcome(
            disposition="completed",
            summary="Completed by the fake runner.",
        ),
        provenance=Provenance(
            source="test",
            fetched_at=datetime.now(UTC),
            confidence="grounded",
        ),
        cost=CostMetrics(estimated_usd=0.0),
    )


def test_cli_loads_a_typed_task_and_prints_the_result_as_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "goal": "Change the fixture.",
                "acceptance_criteria": ["The fixture tests pass."],
                "constraints": ["Keep the public API stable."],
            }
        ),
        encoding="utf-8",
    )
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Evaluation prompt", encoding="utf-8")
    monkeypatch.setenv("TEST_API_KEY", "test-only-secret")
    seen: list[RunRequest] = []

    def execute(request: RunRequest) -> CommissionResult[CodingOutcome]:
        seen.append(request)
        return _successful_result()

    exit_code = main(
        [
            str(workspace),
            "--task",
            str(task_path),
            "--model",
            "provider/model-a",
            "--base-url",
            "https://example.test/v1",
            "--api-key-env",
            "TEST_API_KEY",
            "--prompt-file",
            str(prompt_path),
        ],
        executor=execute,
    )

    assert exit_code == 0
    assert len(seen) == 1
    assert seen[0].workspace == workspace.resolve()
    assert seen[0].task.goal == "Change the fixture."
    assert seen[0].model.id == "provider/model-a"
    assert seen[0].system_prompt == "Evaluation prompt"
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["output"]["disposition"] == "completed"


def test_cli_returns_two_when_the_commission_finishes_without_meeting_the_goal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    task_path = tmp_path / "task.json"
    task_path.write_text('{"goal":"Need a decision."}', encoding="utf-8")
    monkeypatch.setenv("TEST_API_KEY", "test-only-secret")

    def execute(request: RunRequest) -> CommissionResult[CodingOutcome]:
        result = _successful_result()
        return result.model_copy(
            update={
                "output": CodingOutcome(
                    disposition="needs_input",
                    summary="A user-owned choice is missing.",
                    unresolved_issues=["Choose the target behavior."],
                )
            }
        )

    exit_code = main(
        [
            str(workspace),
            "--task",
            str(task_path),
            "--model",
            "provider/model-a",
            "--base-url",
            "https://example.test/v1",
            "--api-key-env",
            "TEST_API_KEY",
        ],
        executor=execute,
    )

    assert exit_code == 2
