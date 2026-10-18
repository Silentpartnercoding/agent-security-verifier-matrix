"""Join the pinned oracle, Lars run, and clean-room predictions by stable IDs."""

import argparse
import json
from pathlib import Path


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _unique_index(rows, key, label):
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError(f"duplicate {label} {key}: {value}")
        result[value] = row
    return result


def build_rows(root):
    root = Path(root)
    artifacts = root / "artifacts"
    oracle = json.loads((artifacts / "upstream-oracle-audit.json").read_text())
    oracle_by_case = _unique_index(oracle["members"], "caseFile", "oracle")
    oracle_by_id = _unique_index(oracle["members"], "id", "oracle")
    lars_by_id = _unique_index(_jsonl(artifacts / "lars-run.jsonl"), "id", "Lars")
    clean_by_case = _unique_index(
        _jsonl(root / "clean-room" / "predictions.jsonl"), "case_id", "clean-room"
    )
    if set(lars_by_id) != set(oracle_by_id):
        raise ValueError("Lars identifiers do not exactly match the selected oracle population")
    expected_cases = {Path(name).stem for name in oracle_by_case}
    if set(clean_by_case) != expected_cases:
        raise ValueError("clean-room case identifiers do not exactly match the selected oracle population")

    rows = []
    for member in oracle["members"]:
        case_id = Path(member["caseFile"]).stem
        identifier = member["id"]
        lars = lars_by_id[identifier]
        clean = clean_by_case[case_id]
        rows.append({
            "case_id": case_id,
            "id": identifier,
            "oracle": member["expected"]["verdict"],
            "oracle_rejects": member["expected"]["rejects"],
            "lars": lars["verdict"],
            "lars_ground": lars["ground"],
            "lars_grounds": lars["grounds"],
            "clean": clean["verdict"],
            "clean_grounds": clean["grounds"],
            "clean_reason": clean["reason"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    rows = build_rows(args.root)
    if args.check:
        if rows != json.loads(args.check.read_text()):
            raise SystemExit("frozen comparison rows do not match the three source artifacts")
    else:
        print(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", end="")


if __name__ == "__main__":
    main()
