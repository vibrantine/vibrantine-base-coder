"""Shared runtime wiring for one-shot and evaluation entry points."""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)
from vibrantine import (
    CommissionResult,
    Model,
    PersistenceBackend,
    PersistenceMode,
    run_commission_sync,
)

from vibrantine_base_coder.commission import BaseCoder
from vibrantine_base_coder.models import CodingOutcome, CodingTask

type NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConfigurationError(ValueError):
    """A caller-owned runner or evaluation configuration is incomplete."""


class ModelProfile(BaseModel):
    """Serializable configuration for one OpenAI-compatible model target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NonBlankText
    id: NonBlankText
    base_url: NonBlankText | None = None
    base_url_env: NonBlankText | None = None
    api_key_env: NonBlankText | None = "OPENROUTER_API_KEY"
    params: dict[str, JsonValue] = Field(default_factory=dict)
    context_window: int | None = Field(default=None, gt=0)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)

    @field_validator("api_key_env", mode="before")
    @classmethod
    def blank_api_key_name_means_keyless(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def one_endpoint_source(self) -> "ModelProfile":
        if self.base_url is not None and self.base_url_env is not None:
            raise ValueError("set base_url or base_url_env, not both")
        return self

    def resolve(self, environ: Mapping[str, str] | None = None) -> Model:
        """Resolve endpoint and credential presence without retaining a key value."""
        values = os.environ if environ is None else environ
        address = self.base_url
        if self.base_url_env is not None:
            address = values.get(self.base_url_env)
            if address is None or not address.strip():
                raise ConfigurationError(
                    f"model {self.name!r} requires non-empty environment variable "
                    f"{self.base_url_env}"
                )
            address = address.strip()

        if self.api_key_env is not None and not values.get(self.api_key_env, "").strip():
            raise ConfigurationError(
                f"model {self.name!r} requires non-empty environment variable {self.api_key_env}"
            )

        if address is None:
            return Model(
                id=self.id,
                name=self.name,
                api_key_env=self.api_key_env,
                params=dict(self.params),
                context_window=self.context_window,
                input_usd_per_million=self.input_usd_per_million,
                output_usd_per_million=self.output_usd_per_million,
            )
        return Model(
            id=self.id,
            name=self.name,
            base_url=address,
            api_key_env=self.api_key_env,
            params=dict(self.params),
            context_window=self.context_window,
            input_usd_per_million=self.input_usd_per_million,
            output_usd_per_million=self.output_usd_per_million,
        )


@dataclass(frozen=True)
class RunRequest:
    """Everything needed to execute one Base Coder call."""

    workspace: Path
    task: CodingTask
    model: Model
    system_prompt: str | None = None
    max_iterations: int = 10
    max_llm_calls: int | None = 100
    time_limit_seconds: float | None = None
    backend: PersistenceBackend | None = None
    record: PersistenceMode | None = None
    on_llm_call: Callable[[dict[str, Any]], None] | None = None


type RunExecutor = Callable[[RunRequest], CommissionResult[CodingOutcome]]


def build_base_coder(
    *,
    workspace: Path,
    system_prompt: str | None = None,
    max_iterations: int = 10,
) -> BaseCoder:
    """Build a baseline coder or a per-run prompt subclass without global mutation."""
    if system_prompt is None:
        return BaseCoder(workspace=workspace, max_iterations=max_iterations)
    normalized = system_prompt.strip()
    if not normalized:
        raise ConfigurationError("system prompt must not be blank")

    class _PromptedBaseCoder(BaseCoder):
        system_prompt: ClassVar[str | None] = normalized

    return _PromptedBaseCoder(workspace=workspace, max_iterations=max_iterations)


def execute_run(request: RunRequest) -> CommissionResult[CodingOutcome]:
    """Execute one governed Base Coder run through Vibrantine's public entry point."""
    coder = build_base_coder(
        workspace=request.workspace,
        system_prompt=request.system_prompt,
        max_iterations=request.max_iterations,
    )
    return run_commission_sync(
        coder,
        request.task,
        models=[request.model],
        max_llm_calls=request.max_llm_calls,
        time_limit_seconds=request.time_limit_seconds,
        backend=request.backend,
        record=request.record,
        on_llm_call=request.on_llm_call,
    )
