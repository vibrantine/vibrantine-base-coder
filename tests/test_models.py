"""Contract tests for Base Coder's first public boundary."""

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

import vibrantine_base_coder
from vibrantine_base_coder import (
    CodingOutcome,
    CodingTask,
    VerificationRecord,
)


def test_public_surface_is_locked_exactly() -> None:
    assert set(vibrantine_base_coder.__all__) == {
        "BaseCoder",
        "CodingOutcome",
        "CodingTask",
        "GoalDisposition",
        "VerificationRecord",
        "VerificationStatus",
    }
    for name in vibrantine_base_coder.__all__:
        assert getattr(vibrantine_base_coder, name, None) is not None


def test_task_has_small_empty_defaults_and_strips_text() -> None:
    task = CodingTask(goal="  repair the parser  ")

    assert task.goal == "repair the parser"
    assert task.acceptance_criteria == []
    assert task.constraints == []


@pytest.mark.parametrize("value", ["", "   "])
def test_task_rejects_a_blank_goal(value: str) -> None:
    with pytest.raises(ValidationError):
        CodingTask(goal=value)


def test_task_rejects_blank_criteria_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CodingTask(goal="repair", acceptance_criteria=["passes", " "])

    with pytest.raises(ValidationError):
        CodingTask.model_validate({"goal": "repair", "plan": ["edit first"]})


@pytest.mark.parametrize(
    "disposition",
    [
        "completed",
        "no_change_needed",
        "partially_completed",
        "needs_input",
        "needs_approval",
        "blocked",
    ],
)
def test_every_goal_disposition_is_an_output_value(disposition: str) -> None:
    outcome = CodingOutcome.model_validate(
        {"disposition": disposition, "summary": "Evidence supports this disposition."}
    )

    assert outcome.disposition == disposition


@pytest.mark.parametrize("status", ["passed", "failed", "unavailable", "inconclusive"])
def test_every_verification_status_is_a_record_value(status: str) -> None:
    record = VerificationRecord.model_validate(
        {
            "check": "pytest tests/test_parser.py",
            "scope": "parser regression",
            "status": status,
            "summary": "Observed result.",
        }
    )

    assert record.status == status


def test_outcome_accepts_unique_workspace_relative_changed_paths() -> None:
    outcome = CodingOutcome(
        disposition="completed",
        summary="Repaired and verified.",
        changed_paths=[Path("src/parser.py"), Path("tests/test_parser.py")],
    )

    assert outcome.changed_paths == [Path("src/parser.py"), Path("tests/test_parser.py")]


@pytest.mark.parametrize(
    "path",
    [Path("/outside.py"), Path("../outside.py"), Path("src/../../outside.py"), Path(".")],
)
def test_outcome_rejects_a_changed_path_outside_a_specific_workspace_item(path: Path) -> None:
    with pytest.raises(ValidationError):
        CodingOutcome(disposition="completed", summary="Done.", changed_paths=[path])


def test_outcome_rejects_duplicate_changed_paths() -> None:
    with pytest.raises(ValidationError):
        CodingOutcome(
            disposition="completed",
            summary="Done.",
            changed_paths=[Path("src/parser.py"), Path("src/parser.py")],
        )


def test_no_change_disposition_cannot_claim_changed_paths() -> None:
    with pytest.raises(ValidationError, match="no_change_needed cannot report changed paths"):
        CodingOutcome(
            disposition="no_change_needed",
            summary="The behavior already matches the request.",
            changed_paths=[Path("src/parser.py")],
        )


def test_contract_models_are_frozen() -> None:
    task = CodingTask(goal="repair")

    with pytest.raises(ValidationError):
        task.goal = "replace"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "model",
    [CodingTask, VerificationRecord, CodingOutcome],
)
def test_every_model_field_has_an_llm_facing_description(model: type[BaseModel]) -> None:
    assert all(field.description for field in model.model_fields.values())
