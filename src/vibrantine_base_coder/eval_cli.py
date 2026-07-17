"""Command-line application for Base Coder evaluation suites."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from vibrantine_base_coder.evaluation import (
    load_suite,
    matrix_description,
    run_evaluation_suite,
)
from vibrantine_base_coder.runtime import ConfigurationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="base-coder-eval",
        description="Run a model × prompt × repetition evaluation matrix.",
    )
    parser.add_argument("suite", type=Path, help="evaluation suite TOML file")
    parser.add_argument("--env-file", type=Path, help="dotenv file; defaults to evals/.env.local")
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="output directory; defaults to evals/results",
    )
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="describe the matrix without credentials",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        loaded = load_suite(args.suite)
        if args.dry_run:
            print(json.dumps(matrix_description(loaded), indent=2))
            return 0

        env_path = (
            args.env_file.resolve() if args.env_file is not None else loaded.root / ".env.local"
        )
        if args.env_file is not None and not env_path.is_file():
            raise ConfigurationError(f"environment file does not exist: {env_path}")
        if env_path.is_file():
            load_dotenv(env_path, override=False)

        results_dir = (
            args.results_dir.resolve()
            if args.results_dir is not None
            else loaded.root
            / "results"
            / f"{loaded.config.name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}"
        )
        summary = run_evaluation_suite(
            loaded,
            results_dir=results_dir,
            keep_workspaces=args.keep_workspaces,
        )
    except (ConfigurationError, OSError, ValidationError, ValueError) as exc:
        print(f"base-coder-eval: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "suite": summary.suite,
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "results_dir": str(results_dir),
            },
            indent=2,
        )
    )
    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":  # pragma: no cover - console-script convenience
    raise SystemExit(main())
