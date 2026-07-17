"""Repeatable model/prompt evaluation matrices over isolated repository fixtures."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from vibrantine import CommissionResult, FilesystemBackend, Model

from vibrantine_base_coder import BaseCoder
from vibrantine_base_coder.models import CodingOutcome, CodingTask
from vibrantine_base_coder.runtime import ModelProfile, RunRequest, execute_run

type NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type EvaluationExecutor = Callable[["EvaluationRequest"], CommissionResult[CodingOutcome]]

_MAX_ORACLE_OUTPUT_CHARS = 30_000


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptVariant(_ConfigModel):
    """One baseline, appended, or replacement system prompt."""

    name: NonBlankText
    append_file: Path | None = None
    replace_file: Path | None = None

    @model_validator(mode="after")
    def one_prompt_operation(self) -> "PromptVariant":
        if self.append_file is not None and self.replace_file is not None:
            raise ValueError("set append_file or replace_file, not both")
        return self


class OracleCheck(_ConfigModel):
    """One evaluator-owned command run after a Commission finishes."""

    name: NonBlankText
    command: list[NonBlankText] = Field(min_length=1)
    timeout_seconds: float = Field(default=60, gt=0)


class EvaluationSuite(_ConfigModel):
    """The serializable configuration for a full comparison matrix."""

    name: NonBlankText
    workspace: Path
    task: CodingTask
    models: list[ModelProfile] = Field(min_length=1)
    prompts: list[PromptVariant] = Field(
        default_factory=lambda: [PromptVariant(name="baseline")],
        min_length=1,
    )
    checks: list[OracleCheck] = Field(default_factory=list)
    repetitions: int = Field(default=1, ge=1)
    max_iterations: int = Field(default=10, ge=1)
    max_llm_calls: int | None = Field(default=100, ge=1)
    time_limit_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def unique_matrix_names(self) -> "EvaluationSuite":
        for label, names in (
            ("model", [profile.name for profile in self.models]),
            ("prompt", [prompt.name for prompt in self.prompts]),
            ("check", [check.name for check in self.checks]),
        ):
            if len(names) != len(set(names)):
                raise ValueError(f"{label} names must be unique")
        return self


@dataclass(frozen=True)
class EvaluationCase:
    model: ModelProfile
    prompt: PromptVariant
    effective_prompt: str
    prompt_sha256: str
    repetition: int


@dataclass(frozen=True)
class LoadedSuite:
    """A validated suite plus the evaluation root used for relative assets."""

    path: Path
    root: Path
    config: EvaluationSuite

    def asset(self, path: Path) -> Path:
        if path.is_absolute():
            raise ValueError(f"evaluation asset path must be relative: {path}")
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"evaluation asset escapes its root: {path}")
        return resolved

    def workspace(self) -> Path:
        workspace = self.asset(self.config.workspace)
        if not workspace.is_dir():
            raise ValueError(f"evaluation workspace does not exist: {workspace}")
        symlink = next((path for path in workspace.rglob("*") if path.is_symlink()), None)
        if symlink is not None:
            raise ValueError(f"evaluation workspace must not contain symlinks: {symlink}")
        return workspace

    def effective_prompt(self, variant: PromptVariant) -> str:
        baseline = BaseCoder.system_prompt
        assert baseline is not None
        if variant.replace_file is not None:
            return _read_nonblank(self.asset(variant.replace_file), "replacement prompt")
        if variant.append_file is not None:
            addition = _read_nonblank(self.asset(variant.append_file), "prompt addition")
            return f"{baseline.rstrip()}\n\n{addition}"
        return baseline

    def cases(self) -> list[EvaluationCase]:
        cases: list[EvaluationCase] = []
        for model in self.config.models:
            for prompt in self.config.prompts:
                effective = self.effective_prompt(prompt)
                digest = hashlib.sha256(effective.encode("utf-8")).hexdigest()
                for repetition in range(1, self.config.repetitions + 1):
                    cases.append(
                        EvaluationCase(
                            model=model,
                            prompt=prompt,
                            effective_prompt=effective,
                            prompt_sha256=digest,
                            repetition=repetition,
                        )
                    )
        return cases


@dataclass(frozen=True)
class EvaluationRequest:
    """One resolved matrix cell ready for execution."""

    workspace: Path
    task: CodingTask
    model: Model
    system_prompt: str
    max_iterations: int
    max_llm_calls: int | None
    time_limit_seconds: float | None
    trace_dir: Path | None = None
    llm_calls: list["ProviderCall"] = field(default_factory=list)


class ProviderCall(_ConfigModel):
    """One credential-free provider-call ledger row from Vibrantine."""

    run_id: str | None
    commission_name: str
    model: str
    model_name: str
    started_at: str
    ended_at: str
    in_tokens: int | None
    out_tokens: int | None
    cost_usd: float
    grant_usd: float | None
    run_calls_before: int
    run_spend_before_usd: float
    status: str


class OracleResult(_ConfigModel):
    name: NonBlankText
    command: list[str]
    status: Literal["passed", "failed", "timed_out"]
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = Field(ge=0)


class EvaluationRecord(_ConfigModel):
    run_id: NonBlankText
    model_name: NonBlankText
    model_id: NonBlankText
    prompt_name: NonBlankText
    prompt_sha256: NonBlankText
    task_sha256: NonBlankText
    fixture_sha256: NonBlankText
    repetition: int = Field(ge=1)
    status: Literal["passed", "failed"]
    duration_seconds: float = Field(ge=0)
    commission_result: CommissionResult[CodingOutcome] | None = None
    executor_error: str | None = None
    oracle_checks: list[OracleResult] = Field(default_factory=list)
    llm_calls: list[ProviderCall] = Field(default_factory=list)
    trace_directory: Path | None = None
    retained_workspace: Path | None = None


class EvaluationSummary(_ConfigModel):
    suite: NonBlankText
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    records: list[EvaluationRecord]


def load_suite(path: Path) -> LoadedSuite:
    """Load a TOML suite and establish its bounded evaluation asset root."""
    resolved = path.resolve()
    with resolved.open("rb") as stream:
        config = EvaluationSuite.model_validate(tomllib.load(stream))
    root = resolved.parent.parent if resolved.parent.name == "suites" else resolved.parent
    loaded = LoadedSuite(path=resolved, root=root.resolve(), config=config)
    loaded.workspace()
    loaded.cases()
    return loaded


def execute_evaluation(request: EvaluationRequest) -> CommissionResult[CodingOutcome]:
    """Adapt an evaluation matrix cell to the shared one-shot runtime."""

    def capture_call(row: dict[str, Any]) -> None:
        request.llm_calls.append(ProviderCall.model_validate(row))

    return execute_run(
        RunRequest(
            workspace=request.workspace,
            task=request.task,
            model=request.model,
            system_prompt=request.system_prompt,
            max_iterations=request.max_iterations,
            max_llm_calls=request.max_llm_calls,
            time_limit_seconds=request.time_limit_seconds,
            backend=(
                FilesystemBackend(request.trace_dir) if request.trace_dir is not None else None
            ),
            record="always" if request.trace_dir is not None else None,
            on_llm_call=capture_call,
        )
    )


def run_evaluation_suite(
    loaded: LoadedSuite,
    *,
    results_dir: Path,
    environ: Mapping[str, str] | None = None,
    executor: EvaluationExecutor = execute_evaluation,
    keep_workspaces: bool = False,
) -> EvaluationSummary:
    """Run every matrix cell sequentially in a fresh fixture copy."""
    values = os.environ if environ is None else environ
    resolved_models = {profile.name: profile.resolve(values) for profile in loaded.config.models}
    source_workspace = loaded.workspace()
    destination = results_dir.resolve()
    if destination == source_workspace or destination.is_relative_to(source_workspace):
        raise ValueError("results directory must be outside the evaluation fixture workspace")
    destination.mkdir(parents=True, exist_ok=False)
    secrets = _credential_values(loaded.config.models, values)
    records: list[EvaluationRecord] = []
    task_sha256 = hashlib.sha256(loaded.config.task.model_dump_json().encode("utf-8")).hexdigest()
    fixture_sha256 = _workspace_sha256(source_workspace)

    for index, case in enumerate(loaded.cases(), start=1):
        run_id = (
            f"{index:03d}-{_slug(case.model.name)}-{_slug(case.prompt.name)}-r{case.repetition}"
        )
        run_dir = destination / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        result: CommissionResult[CodingOutcome] | None = None
        executor_error: str | None = None
        oracle_results: list[OracleResult] = []
        llm_calls: list[ProviderCall] = []
        retained_workspace: Path | None = None
        trace_dir = run_dir / "trace"

        with tempfile.TemporaryDirectory(prefix=f"base-coder-{run_id}-") as temporary:
            workspace = Path(temporary) / "workspace"
            shutil.copytree(source_workspace, workspace)
            request = EvaluationRequest(
                workspace=workspace,
                task=loaded.config.task,
                model=resolved_models[case.model.name],
                system_prompt=case.effective_prompt,
                max_iterations=loaded.config.max_iterations,
                max_llm_calls=loaded.config.max_llm_calls,
                time_limit_seconds=loaded.config.time_limit_seconds,
                trace_dir=trace_dir,
                llm_calls=llm_calls,
            )
            try:
                result = executor(request)
            except Exception as exc:  # noqa: BLE001 - a failed cell must not abort its siblings
                executor_error = _redact(str(exc), secrets)

            oracle_results = [
                _run_oracle(check, workspace=workspace, secrets=secrets)
                for check in loaded.config.checks
            ]
            if keep_workspaces:
                retained_workspace = run_dir / "workspace"
                shutil.copytree(workspace, retained_workspace)

        if trace_dir.is_dir():
            _redact_tree(trace_dir, secrets)

        goal_met = (
            result is not None
            and result.status == "success"
            and result.output is not None
            and result.output.disposition in {"completed", "no_change_needed"}
        )
        oracles_passed = all(check.status == "passed" for check in oracle_results)
        status: Literal["passed", "failed"] = "passed" if goal_met and oracles_passed else "failed"
        record = EvaluationRecord(
            run_id=run_id,
            model_name=case.model.name,
            model_id=case.model.id,
            prompt_name=case.prompt.name,
            prompt_sha256=case.prompt_sha256,
            task_sha256=task_sha256,
            fixture_sha256=fixture_sha256,
            repetition=case.repetition,
            status=status,
            duration_seconds=time.monotonic() - started,
            commission_result=result,
            executor_error=executor_error,
            oracle_checks=oracle_results,
            llm_calls=llm_calls,
            trace_directory=Path("trace") if trace_dir.is_dir() else None,
            retained_workspace=retained_workspace,
        )
        records.append(record)
        _write_model_json(run_dir / "record.json", record, secrets)

    passed = sum(record.status == "passed" for record in records)
    summary = EvaluationSummary(
        suite=loaded.config.name,
        total=len(records),
        passed=passed,
        failed=len(records) - passed,
        records=records,
    )
    _write_model_json(destination / "summary.json", summary, secrets)
    return summary


def matrix_description(loaded: LoadedSuite) -> dict[str, object]:
    """Return a credential-free dry-run description of the planned matrix."""
    return {
        "suite": loaded.config.name,
        "workspace": str(loaded.config.workspace),
        "total": len(loaded.cases()),
        "models": [
            {
                "name": profile.name,
                "id": profile.id,
                "base_url_env": profile.base_url_env,
                "api_key_env": profile.api_key_env,
            }
            for profile in loaded.config.models
        ],
        "prompts": [
            {
                "name": prompt.name,
                "sha256": hashlib.sha256(
                    loaded.effective_prompt(prompt).encode("utf-8")
                ).hexdigest(),
            }
            for prompt in loaded.config.prompts
        ],
        "repetitions": loaded.config.repetitions,
        "checks": [check.name for check in loaded.config.checks],
    }


def _read_nonblank(path: Path, label: str) -> str:
    if not path.is_file():
        raise ValueError(f"{label} file does not exist: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{label} file is blank: {path}")
    return text


def _run_oracle(
    check: OracleCheck,
    *,
    workspace: Path,
    secrets: tuple[str, ...],
) -> OracleResult:
    command = [sys.executable if part == "{python}" else part for part in check.command]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=check.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return OracleResult(
            name=check.name,
            command=command,
            status="timed_out",
            exit_code=None,
            stdout=_redact(_bounded(_output_text(exc.stdout)), secrets),
            stderr=_redact(_bounded(_output_text(exc.stderr)), secrets),
            duration_seconds=time.monotonic() - started,
        )
    return OracleResult(
        name=check.name,
        command=command,
        status="passed" if completed.returncode == 0 else "failed",
        exit_code=completed.returncode,
        stdout=_redact(_bounded(completed.stdout), secrets),
        stderr=_redact(_bounded(completed.stderr), secrets),
        duration_seconds=time.monotonic() - started,
    )


def _output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _bounded(text: str) -> str:
    if len(text) <= _MAX_ORACLE_OUTPUT_CHARS:
        return text
    omitted = len(text) - _MAX_ORACLE_OUTPUT_CHARS
    return f"{text[:_MAX_ORACLE_OUTPUT_CHARS]}\n...[truncated {omitted} characters]"


def _credential_values(
    profiles: list[ModelProfile],
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(
        value
        for profile in profiles
        if profile.api_key_env is not None
        if (value := environ.get(profile.api_key_env, ""))
    )


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    return text


def _write_model_json(path: Path, model: BaseModel, secrets: tuple[str, ...]) -> None:
    serialized = model.model_dump_json(indent=2)
    path.write_text(_redact(serialized, secrets) + "\n", encoding="utf-8")


def _redact_tree(root: Path, secrets: tuple[str, ...]) -> None:
    for path in root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        path.write_text(_redact(text, secrets), encoding="utf-8")


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "case"


def _workspace_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
