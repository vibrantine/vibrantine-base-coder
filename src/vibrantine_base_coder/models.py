"""Typed task and outcome boundary for one atomic coding call."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

type NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type GoalDisposition = Literal[
    "completed",
    "no_change_needed",
    "partially_completed",
    "needs_input",
    "needs_approval",
    "blocked",
]
type VerificationStatus = Literal["passed", "failed", "unavailable", "inconclusive"]


class _ContractModel(BaseModel):
    """Strict frozen base for values crossing the Base Coder boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CodingTask(_ContractModel):
    """One coherent coding goal supplied to an atomic Base Coder call."""

    goal: NonBlankText = Field(description="The bounded coding outcome to achieve.")
    acceptance_criteria: list[NonBlankText] = Field(
        default_factory=list,
        description="Observable conditions that materially define success.",
    )
    constraints: list[NonBlankText] = Field(
        default_factory=list,
        description="Task-specific limits or requirements the coder must preserve.",
    )


class VerificationRecord(_ContractModel):
    """Compact evidence from one material check or inspection."""

    check: NonBlankText = Field(
        description="The command, tool, or inspection that produced this evidence.",
    )
    scope: NonBlankText = Field(description="The behavior or repository area checked.")
    status: VerificationStatus = Field(description="The observed status of this check.")
    summary: NonBlankText = Field(description="A concise factual result from the check.")


class CodingOutcome(_ContractModel):
    """The goal disposition and evidence returned by one Base Coder call."""

    disposition: GoalDisposition = Field(
        description="The coding goal's domain outcome, separate from Commission execution status.",
    )
    summary: NonBlankText = Field(description="A concise account of the resulting workspace state.")
    changed_paths: list[Path] = Field(
        default_factory=list,
        description="Workspace-relative paths intentionally changed by this coding call.",
    )
    verification: list[VerificationRecord] = Field(
        default_factory=list,
        description="Material checks that support or qualify the stated disposition.",
    )
    unresolved_issues: list[NonBlankText] = Field(
        default_factory=list,
        description="Known in-scope work or questions that remain unresolved.",
    )
    residual_risks: list[NonBlankText] = Field(
        default_factory=list,
        description="Material uncertainty or risk that remains after the coding call.",
    )

    @field_validator("changed_paths")
    @classmethod
    def changed_paths_are_relative(cls, paths: list[Path]) -> list[Path]:
        """Keep outcome receipts independent of the caller's absolute workspace path."""
        seen: set[Path] = set()
        for path in paths:
            if path.is_absolute() or path.drive or path.root or ".." in path.parts:
                raise ValueError(f"changed path must stay relative to the workspace: {path!s}")
            if path == Path("."):
                raise ValueError(
                    "changed path must identify a file or directory, not the workspace"
                )
            if path in seen:
                raise ValueError(f"changed path appears more than once: {path!s}")
            seen.add(path)
        return paths

    @model_validator(mode="after")
    def no_change_has_no_changed_paths(self) -> Self:
        """Make the no-change disposition structurally honest."""
        if self.disposition == "no_change_needed" and self.changed_paths:
            raise ValueError("no_change_needed cannot report changed paths")
        return self
