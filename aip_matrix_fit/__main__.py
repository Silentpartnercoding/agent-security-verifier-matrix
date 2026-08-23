"""Command-line entry point for AIP-MATRIX-FIT-001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluator import evaluate_all


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen AIP-MATRIX-FIT-001 cases")
    parser.add_argument(
        "--output",
        type=Path,
        help="write the deterministic JSON report to this path instead of stdout",
    )
    args = parser.parse_args()
    report = evaluate_all()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["all_conform"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
