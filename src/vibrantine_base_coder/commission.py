"""The atomic Base Coder Commission."""

import json
from pathlib import Path
from typing import ClassVar

from vibrantine import DEFAULT_MAX_ITERATIONS, CallContext, Commission
from vibrantine.tools import (
    EditTool,
    GlobTool,
    GrepTool,
    ListDirTool,
    ReadTool,
    ShellTool,
    WriteTool,
)

from vibrantine_base_coder.models import CodingOutcome, CodingTask

_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8").strip()


class BaseCoder(Commission[CodingTask, CodingOutcome]):
    """Complete one bounded coding task in one caller-bound workspace."""

    name: ClassVar[str] = "base_coder"
    description: ClassVar[str] = (
        "Complete one bounded coding task in a local repository. Inspects the "
        "workspace, makes scoped text changes, runs relevant checks, and returns "
        "a typed outcome with changed paths, verification, and unresolved risk."
    )
    input_type: ClassVar[type] = CodingTask
    output_type: ClassVar[type] = CodingOutcome
    system_prompt: ClassVar[str | None] = _PROMPT
    toolbox = (
        ListDirTool(),
        GlobTool(),
        GrepTool(),
        ReadTool(),
        EditTool(),
        WriteTool(),
        ShellTool(),
    )

    def __init__(
        self,
        *,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        supplied = Path(workspace)
        if not supplied.is_absolute():
            raise ValueError(f"workspace must be absolute; got {supplied!s}")
        if not supplied.exists():
            raise ValueError(f"workspace does not exist: {supplied!s}")
        if not supplied.is_dir():
            raise ValueError(f"workspace is not a directory: {supplied!s}")

        self.workspace = supplied.resolve()
        super().__init__(model=model, max_iterations=max_iterations)

    def build_user_message(self, input: CodingTask, ctx: CallContext) -> str:
        """Place trusted workspace context beside the caller's typed task."""
        return json.dumps(
            {
                "workspace_root": str(self.workspace),
                "task": input.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
