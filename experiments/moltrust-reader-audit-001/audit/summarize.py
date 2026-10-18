"""Reduce frozen raw outputs to the claims reported by this experiment."""

import argparse
import json
from collections import Counter
from pathlib import Path


def _read_json(path):
    return json.loads(path.read_text())


def summarize(root):
    root = Path(root)
    artifacts = root / "artifacts"
    rows = _read_json(artifacts / "comparison-rows.json")
    mutation_rows = _read_json(artifacts / "mutation-results.json")
    mutation_rows += _read_json(artifacts / "mutation-results-more.json")

    matrix = Counter(f"{row['oracle']}/{row['lars']}/{row['clean']}" for row in rows)
    clean_counts = Counter(row["clean"] for row in rows)
    for verdict in ("accept", "cannot-tell", "reject"):
        clean_counts.setdefault(verdict, 0)
    clean_opposites = sorted(
        row["case_id"]
        for row in rows
        if row["clean"] in ("accept", "reject") and row["clean"] != row["oracle"]
    )
    lars_opposites = sorted(
        row["case_id"]
        for row in rows
        if row["lars"] in ("accept", "reject") and row["lars"] != row["oracle"]
    )
    clean_reject_lars_open = sorted(
        row["case_id"]
        for row in rows
        if row["clean"] == "reject" and row["lars"] == "cannot-tell"
    )

    mutations = {
        row["case"]: {
            "exit": row["exit"],
            "output_lines": row["output_lines"],
        }
        for row in mutation_rows
    }
    return {
        "case_count": len(rows),
        "clean_counts": dict(sorted(clean_counts.items())),
        "clean_opposite_oracle": clean_opposites,
        "clean_reject_lars_cannot_tell": clean_reject_lars_open,
        "lars_opposite_oracle": lars_opposites,
        "mutations": dict(sorted(mutations.items())),
        "verdict_matrix": dict(sorted(matrix.items())),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    if args.check:
        expected = _read_json(args.check)
        if result != expected:
            raise SystemExit("frozen audit summary does not match raw artifacts")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
