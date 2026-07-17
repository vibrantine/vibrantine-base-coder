"""Contract tests for the first atomic BaseCoder Commission."""

import json
import sys
from pathlib import Path

import pytest
from vibrantine import CapabilitySet, run_commission_sync
from vibrantine.testing import AlwaysCancelled, ScriptedLLM, llm_response, scripted_model
from vibrantine.tools import (
    EditTool,
    GlobTool,
    GrepTool,
    ListDirTool,
    ReadTool,
    ShellTool,
    WriteTool,
)

from vibrantine_base_coder import BaseCoder, CodingTask


def _conclusion(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "disposition": "completed",
        "summary": "The bounded task is complete.",
        "changed_paths": [],
        "verification": [],
        "unresolved_issues": [],
        "residual_risks": [],
    }
    result.update(overrides)
    return result


def test_base_coder_is_a_basic_default_loop_commission(tmp_path: Path) -> None:
    coder = BaseCoder(workspace=tmp_path)

    assert "_run" not in BaseCoder.__dict__
    assert coder.workspace == tmp_path.resolve()
    assert BaseCoder.system_prompt is not None
    normalized_prompt = " ".join(BaseCoder.system_prompt.split())
    assert "one bounded coding task" in normalized_prompt
    assert "Do not delegate" in normalized_prompt


def test_base_coder_exposes_exactly_the_standard_seven_toolbox(tmp_path: Path) -> None:
    coder = BaseCoder(workspace=tmp_path)

    assert tuple(type(tool) for tool in coder.toolbox) == (
        ListDirTool,
        GlobTool,
        GrepTool,
        ReadTool,
        EditTool,
        WriteTool,
        ShellTool,
    )
    assert tuple(tool.name for tool in coder.toolbox) == (
        "list_dir",
        "glob",
        "grep",
        "read",
        "edit",
        "write",
        "shell",
    )


def test_base_coder_requires_an_absolute_existing_directory(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("not a workspace", encoding="utf-8")

    with pytest.raises(ValueError, match="absolute"):
        BaseCoder(workspace=Path("relative"))
    with pytest.raises(ValueError, match="does not exist"):
        BaseCoder(workspace=tmp_path / "missing")
    with pytest.raises(ValueError, match="not a directory"):
        BaseCoder(workspace=file)


def test_opening_message_contains_bound_workspace_and_typed_task(tmp_path: Path) -> None:
    scripted = ScriptedLLM([llm_response(tool_calls=[("done", "conclude", _conclusion())])])
    coder = BaseCoder(workspace=tmp_path)
    task = CodingTask(
        goal="Inspect the fixture without changing it.",
        acceptance_criteria=["Report the observed state."],
        constraints=["Do not modify files."],
    )

    result = run_commission_sync(coder, task, models=[scripted_model(scripted)])

    assert result.status == "success", result.error
    first_messages = scripted.calls[0]["messages"]
    opening = next(message for message in first_messages if message["role"] == "user")
    payload = json.loads(opening["content"])
    assert payload == {
        "workspace_root": str(tmp_path.resolve()),
        "task": task.model_dump(mode="json"),
    }


def test_caller_can_narrow_the_model_visible_toolbox(tmp_path: Path) -> None:
    scripted = ScriptedLLM([llm_response(tool_calls=[("done", "conclude", _conclusion())])])

    result = run_commission_sync(
        BaseCoder(workspace=tmp_path),
        CodingTask(goal="Inspect without mutation."),
        models=[scripted_model(scripted)],
        capabilities=CapabilitySet(tools=frozenset({"list_dir", "read"})),
    )

    assert result.status == "success", result.error
    tool_names = {tool["function"]["name"] for tool in scripted.calls[0]["tools"]}
    assert tool_names == {"list_dir", "read", "conclude"}


def test_scripted_read_edit_check_and_conclude_run(tmp_path: Path) -> None:
    target = tmp_path / "message.txt"
    target.write_text("old value\n", encoding="utf-8")
    code = "from pathlib import Path; assert Path('message.txt').read_text() == 'new value\\n'"
    check_command = f'"{sys.executable}" -c "{code}"'
    scripted = ScriptedLLM(
        [
            llm_response(
                tool_calls=[("read-1", "read", {"path": str(target), "offset": 0, "limit": 100})]
            ),
            llm_response(
                tool_calls=[
                    (
                        "edit-1",
                        "edit",
                        {
                            "path": str(target),
                            "old_string": "old value",
                            "new_string": "new value",
                            "replace_all": False,
                        },
                    )
                ]
            ),
            llm_response(
                tool_calls=[
                    (
                        "check-1",
                        "shell",
                        {
                            "command": check_command,
                            "cwd": str(tmp_path),
                            "timeout_seconds": 30,
                            "max_output_chars": 30000,
                        },
                    )
                ]
            ),
            llm_response(
                tool_calls=[
                    (
                        "done",
                        "conclude",
                        _conclusion(
                            summary="Updated the fixture and verified its exact contents.",
                            changed_paths=["message.txt"],
                            verification=[
                                {
                                    "check": check_command,
                                    "scope": "message.txt contents",
                                    "status": "passed",
                                    "summary": "The Python assertion exited with code 0.",
                                }
                            ],
                        ),
                    )
                ]
            ),
        ]
    )

    result = run_commission_sync(
        BaseCoder(workspace=tmp_path),
        CodingTask(
            goal="Change the fixture from old value to new value.",
            acceptance_criteria=["message.txt contains new value followed by a newline."],
        ),
        models=[scripted_model(scripted)],
    )

    assert result.status == "success", result.error
    assert result.output is not None
    assert result.output.disposition == "completed"
    assert result.output.changed_paths == [Path("message.txt")]
    assert result.output.verification[0].status == "passed"
    assert target.read_text(encoding="utf-8") == "new value\n"
    assert len(scripted.calls) == 4
    final_tool_messages = [
        message for message in scripted.calls[-1]["messages"] if message["role"] == "tool"
    ]
    assert any('"exit_code":0' in message["content"] for message in final_tool_messages)


def test_base_coder_uses_framework_cancellation_before_calling_a_model(tmp_path: Path) -> None:
    scripted = ScriptedLLM([llm_response(tool_calls=[("done", "conclude", _conclusion())])])

    result = run_commission_sync(
        BaseCoder(workspace=tmp_path),
        CodingTask(goal="Do nothing."),
        models=[scripted_model(scripted)],
        cancel=AlwaysCancelled(),
    )

    assert result.status == "failure"
    assert result.error is not None
    assert result.error.kind == "cancelled"
    assert scripted.calls == []
