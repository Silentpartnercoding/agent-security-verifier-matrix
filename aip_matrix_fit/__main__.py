"""Command-line entry point for AIP-MATRIX-FIT-002."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluator import EvaluationError, evaluate_all


ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.json"


def _source_argument(value: str) -> tuple[str, Path]:
    source_id, separator, path = value.partition("=")
    if not separator or not source_id or not path:
        raise argparse.ArgumentTypeError("source must use ID=PATH")
    return source_id, Path(path)


def _source_files_from_directory(directory: Path) -> dict[str, Path]:
    manifest = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    pins = manifest.get("sources")
    if not isinstance(pins, list):
        raise EvaluationError("sources must be a list")
    source_files: dict[str, Path] = {}
    for pin in pins:
        source_id = pin.get("id") if isinstance(pin, dict) else None
        if not isinstance(source_id, str):
            raise EvaluationError("every source pin must have a string id")
        source_files[source_id] = directory / source_id
    return source_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the corrected AIP-MATRIX-FIT-002 cases")
    parser.add_argument(
        "--output",
        type=Path,
        help="write the deterministic JSON report to this path instead of stdout",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        type=_source_argument,
        metavar="ID=PATH",
        help="verify locally supplied bytes for a pinned source; repeat for every source",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="verify every pinned source from files named by source ID in this directory",
    )
    parser.add_argument(
        "--require-source-verification",
        action="store_true",
        help="fail unless all pinned source bytes were supplied and passed",
    )
    args = parser.parse_args()
    try:
        source_files = (
            _source_files_from_directory(args.source_dir) if args.source_dir else {}
        )
    except (OSError, json.JSONDecodeError, EvaluationError) as error:
        parser.error(str(error))
    for source_id, path in args.source:
        if source_id in source_files:
            parser.error(f"duplicate --source id: {source_id}")
        source_files[source_id] = path
    try:
        report = evaluate_all(source_files)
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
