"""Command-line interface for a version-pinned verifier-matrix experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluator import EvaluationError, evaluate_experiment


def _source_argument(value: str) -> tuple[str, Path]:
    source_id, separator, path = value.partition("=")
    if not separator or not source_id or not path:
        raise argparse.ArgumentTypeError("source must use ID=PATH")
    return source_id, Path(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a pinned verifier-matrix experiment")
    parser.add_argument("experiment_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        type=_source_argument,
        metavar="ID=PATH",
    )
    parser.add_argument("--require-source-verification", action="store_true")
    args = parser.parse_args()
    source_files: dict[str, Path] = {}
    for source_id, path in args.source:
        if source_id in source_files:
            parser.error(f"duplicate --source id: {source_id}")
        source_files[source_id] = path
    try:
        report = evaluate_experiment(args.experiment_dir, source_files)
    except EvaluationError as error:
        parser.error(str(error))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    verification_status = report["source_byte_verification"]["status"]
    verification_ok = verification_status != "failed"
    if args.require_source_verification:
        verification_ok = verification_status == "passed"
    return 0 if report["all_conform"] and verification_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
