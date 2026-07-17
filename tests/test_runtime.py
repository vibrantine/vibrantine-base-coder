"""Shared runtime configuration tests for CLI and evaluation entry points."""

from pathlib import Path

import pytest
from vibrantine import FilesystemBackend
from vibrantine.testing import ScriptedLLM, llm_response, scripted_model

from vibrantine_base_coder import BaseCoder
from vibrantine_base_coder.models import CodingTask
from vibrantine_base_coder.runtime import (
    ConfigurationError,
    ModelProfile,
    RunRequest,
    build_base_coder,
    execute_run,
)


def test_model_profile_resolves_an_openai_compatible_endpoint_from_environment() -> None:
    profile = ModelProfile(
        name="candidate",
        id="provider/model-a",
        base_url_env="CANDIDATE_BASE_URL",
        api_key_env="CANDIDATE_API_KEY",
        params={"temperature": 0.2},
    )

    model = profile.resolve(
        {
            "CANDIDATE_BASE_URL": "https://example.test/v1",
            "CANDIDATE_API_KEY": "test-only-secret",
        }
    )

    assert model.name == "candidate"
    assert model.id == "provider/model-a"
    assert model.base_url == "https://example.test/v1"
    assert model.api_key_env == "CANDIDATE_API_KEY"
    assert model.params == {"temperature": 0.2}


def test_model_profile_names_missing_environment_without_exposing_values() -> None:
    profile = ModelProfile(
        name="candidate",
        id="provider/model-a",
        base_url_env="CANDIDATE_BASE_URL",
        api_key_env="CANDIDATE_API_KEY",
    )

    with pytest.raises(ConfigurationError, match="CANDIDATE_BASE_URL"):
        profile.resolve({})
    with pytest.raises(ConfigurationError, match="CANDIDATE_API_KEY"):
        profile.resolve({"CANDIDATE_BASE_URL": "https://example.test/v1"})


def test_model_profile_can_explicitly_target_a_keyless_local_endpoint() -> None:
    profile = ModelProfile.model_validate(
        {
            "name": "local",
            "id": "local-model",
            "base_url": "http://localhost:11434/v1",
            "api_key_env": "",
        }
    )

    model = profile.resolve({})

    assert model.api_key_env is None


def test_prompt_variant_uses_an_isolated_subclass_without_mutating_default(tmp_path: Path) -> None:
    original_prompt = BaseCoder.system_prompt

    baseline = build_base_coder(workspace=tmp_path)
    variant = build_base_coder(workspace=tmp_path, system_prompt="Variant prompt")

    assert baseline.system_prompt == original_prompt
    assert variant.system_prompt == "Variant prompt"
    assert type(variant) is not BaseCoder
    assert BaseCoder.system_prompt == original_prompt


def test_run_request_can_capture_provider_calls_and_persist_a_trace(tmp_path: Path) -> None:
    scripted = ScriptedLLM(
        [
            llm_response(
                tool_calls=[
                    (
                        "done",
                        "conclude",
                        {
                            "disposition": "no_change_needed",
                            "summary": "No change was required.",
                            "changed_paths": [],
                            "verification": [],
                            "unresolved_issues": [],
                            "residual_risks": [],
                        },
                    )
                ]
            )
        ]
    )
    calls: list[dict[str, object]] = []
    trace_dir = tmp_path / "trace"

    result = execute_run(
        RunRequest(
            workspace=tmp_path,
            task=CodingTask(goal="Inspect without changing anything."),
            model=scripted_model(scripted),
            backend=FilesystemBackend(trace_dir),
            record="always",
            on_llm_call=calls.append,
        )
    )

    assert result.status == "success"
    assert len(calls) == 1
    assert calls[0]["status"] == "completed"
    assert len(list(trace_dir.glob("*.json"))) == 1
