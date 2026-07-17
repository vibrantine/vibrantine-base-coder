"""Thin one-shot command-line runner for Base Coder."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from vibrantine import DEFAULT_MODEL

from vibrantine_base_coder.models import CodingTask
from vibrantine_base_coder.runtime import (
    ConfigurationError,
    ModelProfile,
    RunExecutor,
    RunRequest,
    execute_run,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="base-coder",
        description="Run one atomic Base Coder task in one workspace.",
    )
    parser.add_argument("workspace", type=Path, help="repository workspace to modify")
    parser.add_argument("--task", type=Path, required=True, help="CodingTask JSON file")
    parser.add_argument("--model", default=DEFAULT_MODEL.id, help="wire model id")
    endpoint = parser.add_mutually_exclusive_group()
    endpoint.add_argument("--base-url", help="OpenAI-compatible API base URL")
    endpoint.add_argument("--base-url-env", help="environment variable containing the base URL")
    credential = parser.add_mutually_exclusive_group()
    credential.add_argument(
        "--api-key-env",
        default="OPENROUTER_API_KEY",
        help="environment variable containing the API key",
    )
    credential.add_argument(
        "--no-api-key",
        action="store_const",
        const=None,
        dest="api_key_env",
        help="use a keyless local endpoint",
    )
    parser.add_argument("--env-file", type=Path, help="optional dotenv file to load")
    parser.add_argument("--prompt-file", type=Path, help="complete system-prompt override")
    parser.add_argument("--max-iterations", type=_positive_int, default=10)
    parser.add_argument("--max-llm-calls", type=_positive_int, default=100)
    parser.add_argument("--time-limit-seconds", type=_positive_float)
    return parser


def _read_task(path: Path) -> CodingTask:
    return CodingTask.model_validate_json(path.read_text(encoding="utf-8"))


def _read_prompt(path: Path | None) -> str | None:
    return None if path is None else path.read_text(encoding="utf-8")


def _exit_code(status: str, disposition: str | None) -> int:
    if status != "success":
        return 1
    if disposition in {"completed", "no_change_needed"}:
        return 0
    return 2


def main(argv: list[str] | None = None, *, executor: RunExecutor = execute_run) -> int:
    """Parse one task, execute it, and write the typed result envelope as JSON."""
    args = _parser().parse_args(argv)
    try:
        if args.env_file is not None:
            env_path = args.env_file.resolve()
            if not env_path.is_file():
                raise ConfigurationError(f"environment file does not exist: {env_path}")
            load_dotenv(env_path, override=False)

        workspace = args.workspace.resolve()
        if not workspace.is_dir():
            raise ConfigurationError(f"workspace does not exist or is not a directory: {workspace}")
        profile = ModelProfile(
            name=str(args.model),
            id=str(args.model),
            base_url=args.base_url,
            base_url_env=args.base_url_env,
            api_key_env=args.api_key_env,
        )
        request = RunRequest(
            workspace=workspace,
            task=_read_task(args.task),
            model=profile.resolve(os.environ),
            system_prompt=_read_prompt(args.prompt_file),
            max_iterations=args.max_iterations,
            max_llm_calls=args.max_llm_calls,
            time_limit_seconds=args.time_limit_seconds,
        )
        result = executor(request)
    except (ConfigurationError, OSError, ValidationError, ValueError) as exc:
        print(f"base-coder: {exc}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))
    disposition = result.output.disposition if result.output is not None else None
    return _exit_code(result.status, disposition)


if __name__ == "__main__":  # pragma: no cover - console-script convenience
    raise SystemExit(main())
