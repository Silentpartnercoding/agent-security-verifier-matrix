"""CLI for AUDIT-REFUSAL-COMPLETENESS-001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiment import ExperimentError, run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen independent refusal-record completeness experiment"
    )
    parser.add_argument("--experiment", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = run_experiment(args.experiment)
    except (ExperimentError, OSError, RuntimeError) as error:
        parser.error(str(error))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["all_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
