"""Tests for repeatable, isolated Base Coder evaluation matrices."""

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from vibrantine import CommissionResult, CostMetrics, Provenance

from vibrantine_base_coder.evaluation import (
    EvaluationRequest,
    load_suite,
    matrix_description,
    run_evaluation_suite,
)
from vibrantine_base_coder.models import CodingOutcome

REPOSITORY_ROOT = Path(__file__).parents[1]


def _successful_result() -> CommissionResult[CodingOutcome]:
    return CommissionResult[CodingOutcome](
        status="success",
        output=CodingOutcome(
            disposition="completed",
            summary="Changed the isolated fixture.",
            changed_paths=[Path("value.txt")],
        ),
        provenance=Provenance(
            source="test",
            fetched_at=datetime.now(UTC),
            confidence="grounded",
        ),
        cost=CostMetrics(estimated_usd=0.0),
    )


def _write_suite(root: Path) -> Path:
    fixtures = root / "fixtures" / "sample"
    fixtures.mkdir(parents=True)
    (fixtures / "value.txt").write_text("original\n", encoding="utf-8")
    prompts = root / "prompts"
    prompts.mkdir()
    (prompts / "extra.md").write_text("Double-check the exact value.", encoding="utf-8")
    suites = root / "suites"
    suites.mkdir()
    suite_path = suites / "sample.toml"
    suite_path.write_text(
        r"""name = "sample"
workspace = "fixtures/sample"
repetitions = 2

[task]
goal = "Change value.txt to changed."
acceptance_criteria = ["value.txt contains changed."]

[[models]]
name = "model-a"
id = "provider/model-a"
base_url_env = "EVAL_BASE_URL"
api_key_env = "EVAL_API_KEY"

[[models]]
name = "model-b"
id = "provider/model-b"
base_url_env = "EVAL_BASE_URL"
api_key_env = "EVAL_API_KEY"

[[prompts]]
name = "baseline"

[[prompts]]
name = "extra-check"
append_file = "prompts/extra.md"

[[checks]]
name = "value changed"
command = [
    "{python}",
    "-c",
    "from pathlib import Path; assert Path('value.txt').read_text() == 'changed\\n'",
]
timeout_seconds = 10
""",
        encoding="utf-8",
    )
    return suite_path


def test_suite_builds_the_full_model_prompt_repetition_matrix(tmp_path: Path) -> None:
    loaded = load_suite(_write_suite(tmp_path))

    cases = loaded.cases()

    assert len(cases) == 8
    assert {(case.model.name, case.prompt.name, case.repetition) for case in cases} == {
        (model, prompt, repetition)
        for model in ("model-a", "model-b")
        for prompt in ("baseline", "extra-check")
        for repetition in (1, 2)
    }
    assert cases[0].effective_prompt
    assert cases[0].prompt_sha256 != cases[2].prompt_sha256
    description = matrix_description(loaded)
    prompts = cast(list[object], description["prompts"])
    assert len(prompts) == 2


def test_evaluation_runs_each_case_in_a_fresh_workspace_and_records_oracles(
    tmp_path: Path,
) -> None:
    loaded = load_suite(_write_suite(tmp_path))
    results_dir = tmp_path / "results"
    seen_workspaces: list[Path] = []
    seen_models: list[str] = []

    def execute(request: EvaluationRequest) -> CommissionResult[CodingOutcome]:
        seen_workspaces.append(request.workspace)
        seen_models.append(request.model.id)
        target = request.workspace / "value.txt"
        assert target.read_text(encoding="utf-8") == "original\n"
        target.write_text("changed\n", encoding="utf-8")
        return _successful_result()

    summary = run_evaluation_suite(
        loaded,
        results_dir=results_dir,
        environ={
            "EVAL_BASE_URL": "https://example.test/v1",
            "EVAL_API_KEY": "test-only-secret",
        },
        executor=execute,
    )

    assert summary.total == 8
    assert summary.passed == 8
    assert summary.failed == 0
    assert len(set(seen_workspaces)) == 8
    assert set(seen_models) == {"provider/model-a", "provider/model-b"}
    assert (tmp_path / "fixtures" / "sample" / "value.txt").read_text(encoding="utf-8") == (
        "original\n"
    )
    assert all(record.oracle_checks[0].exit_code == 0 for record in summary.records)
    assert all(record.status == "passed" for record in summary.records)
    assert len({record.task_sha256 for record in summary.records}) == 1
    assert len({record.fixture_sha256 for record in summary.records}) == 1
    assert (results_dir / "summary.json").is_file()
    assert len(list(results_dir.glob("*/record.json"))) == 8


def test_failed_oracle_marks_the_run_failed_even_when_commission_claims_completion(
    tmp_path: Path,
) -> None:
    loaded = load_suite(_write_suite(tmp_path))

    summary = run_evaluation_suite(
        loaded,
        results_dir=tmp_path / "results",
        environ={
            "EVAL_BASE_URL": "https://example.test/v1",
            "EVAL_API_KEY": "test-only-secret",
        },
        executor=lambda request: _successful_result(),
    )

    assert summary.passed == 0
    assert summary.failed == 8
    assert all(record.oracle_checks[0].exit_code != 0 for record in summary.records)
    assert sys.executable in summary.records[0].oracle_checks[0].command[0]


def test_evaluation_redacts_credential_values_from_errors_and_artifacts(tmp_path: Path) -> None:
    loaded = load_suite(_write_suite(tmp_path))
    secret = "test-only-secret"
    results_dir = tmp_path / "results"

    def fail(request: EvaluationRequest) -> CommissionResult[CodingOutcome]:
        raise RuntimeError(f"provider rejected {secret}")

    summary = run_evaluation_suite(
        loaded,
        results_dir=results_dir,
        environ={"EVAL_BASE_URL": "https://example.test/v1", "EVAL_API_KEY": secret},
        executor=fail,
    )

    assert summary.records[0].executor_error == "provider rejected [REDACTED]"
    assert secret not in (results_dir / "summary.json").read_text(encoding="utf-8")


def test_tracked_localized_defect_suite_has_twelve_cells_and_a_sensitive_oracle(
    tmp_path: Path,
) -> None:
    loaded = load_suite(REPOSITORY_ROOT / "evals" / "suites" / "localized-defect.toml")
    fixture = loaded.workspace()
    workspace = tmp_path / "workspace"
    shutil.copytree(fixture, workspace)

    before = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    calculator = workspace / "calculator.py"
    calculator.write_text(
        calculator.read_text(encoding="utf-8").replace(
            "return left - right", "return left + right"
        ),
        encoding="utf-8",
    )
    after = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )

    assert len(loaded.cases()) == 12
    assert before.returncode != 0
    assert after.returncode == 0
