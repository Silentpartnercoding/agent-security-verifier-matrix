"""One-command offline verification for the frozen audit package."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected}, got {actual}")


def verify_evidence(root):
    root = Path(root)
    pins_path = root / "SOURCE-PINS.json"
    pins = json.loads(pins_path.read_text())
    clean = pins["clean_room_reader"]
    frozen = pins["frozen_audit_artifacts"]

    paths = {
        root / "artifacts" / "clean-room-history.bundle": clean["history_bundle_sha256"],
        root / "clean-room" / "reader.py": clean["reader_sha256"],
        root / "inputs" / "SHA256SUMS": clean["input_manifest_sha256"],
        root / "clean-room" / "predictions.jsonl": clean["predictions_sha256"],
        root / "clean-room" / "counts.json": clean["counts_sha256"],
        root / "artifacts" / "lars-run.jsonl": frozen["lars_run_sha256"],
        root / "artifacts" / "upstream-oracle-audit.json": frozen["oracle_audit_sha256"],
        root / "artifacts" / "comparison-rows.json": frozen["comparison_rows_sha256"],
        root / "audit" / "replay_mutations.py": frozen["mutation_runner_sha256"],
        root / "artifacts" / "mutation-replay.json": frozen["mutation_replay_sha256"],
        root / "artifacts" / "mutation-results.json": frozen["mutation_results_sha256"],
        root / "artifacts" / "mutation-results-more.json": frozen["mutation_results_more_sha256"],
        root / "artifacts" / "lars-cannot-tell-adjudication.json": frozen["lars_cannot_tell_adjudication_sha256"],
    }
    for path, expected in paths.items():
        require_digest(path, expected)

    oracle = json.loads((root / "artifacts" / "upstream-oracle-audit.json").read_text())
    upstream = pins["upstream_oracle"]
    oracle_claims = {
        "sourceCommit": upstream["commit"],
        "sourceTag": upstream["tag"],
        "corpusMemberCount": upstream["corpus_member_count"],
        "selectedMemberCount": upstream["selected_member_count"],
        "selectedRawMemberDigest": upstream["selected_raw_member_digest"],
        "corpusDigest": upstream["full_corpus_digest"],
    }
    for key, expected in oracle_claims.items():
        if oracle.get(key) != expected:
            raise ValueError(f"oracle provenance mismatch for {key}")

    bundle = root / "artifacts" / "clean-room-history.bundle"
    freeze = clean["freeze_commit"]
    with tempfile.TemporaryDirectory(prefix="clean-room-bundle-") as tmp:
        clone = Path(tmp) / "clean-room"
        subprocess.run(["git", "clone", "--quiet", str(bundle), str(clone)], check=True)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=clone, check=True, capture_output=True, text=True
        ).stdout.strip()
        if head != freeze:
            raise ValueError(f"clean-room bundle HEAD is {head}, expected {freeze}")
        for name in ("reader.py", "predictions.jsonl", "counts.json"):
            if (clone / name).read_bytes() != (root / "clean-room" / name).read_bytes():
                raise ValueError(f"packaged clean-room {name} differs from frozen commit")


def verify_clean_freeze(root):
    root = Path(root)
    clean = root / "clean-room"
    frozen_record = (clean / "VERIFICATION.json").read_bytes()
    frozen_ledger = (clean / "ARTIFACT-SHA256SUMS").read_bytes()
    try:
        run([sys.executable, "-E", "-S", "-B", "verify_freeze.py"], clean)
        regenerated_record = (clean / "VERIFICATION.json").read_bytes()
        regenerated_ledger = (clean / "ARTIFACT-SHA256SUMS").read_bytes()
    finally:
        (clean / "VERIFICATION.json").write_bytes(frozen_record)
        (clean / "ARTIFACT-SHA256SUMS").write_bytes(frozen_ledger)
    if regenerated_record != frozen_record:
        raise ValueError("clean-room verification record was regenerated with different evidence")
    if regenerated_ledger != frozen_ledger:
        raise ValueError("clean-room hash ledger was regenerated with different evidence")


def main():
    verify_evidence(ROOT)
    verify_clean_freeze(ROOT)
    run(
        [sys.executable, "-E", "-S", "-B", "-m", "unittest", "-v",
         "audit/test_summarize.py", "audit/test_provenance.py"],
        ROOT,
    )
    run(
        [sys.executable, "-E", "-S", "-B", "-m", "audit.build_comparison",
         "--check", ROOT / "artifacts" / "comparison-rows.json"],
        ROOT,
    )
    run(
        [sys.executable, "-E", "-S", "-B", "-m", "audit.summarize",
         "--check", ROOT / "artifacts" / "audit-summary.json"],
        ROOT,
    )
    summary = json.loads((ROOT / "artifacts" / "audit-summary.json").read_text())
    print(f"verified {summary['case_count']} cases; clean rejects={summary['clean_counts']['reject']}; "
          f"clean/oracle oppositions={len(summary['clean_opposite_oracle'])}")


if __name__ == "__main__":
    main()
