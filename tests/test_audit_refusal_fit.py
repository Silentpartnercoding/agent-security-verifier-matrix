from __future__ import annotations

import json
import hashlib
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from audit_refusal_fit import check_records, emit_records, run_experiment


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "audit-refusal-completeness-001"


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


class RefusalEmitterTests(unittest.TestCase):
    def test_emitter_records_allow_deny_and_uncanonicalizable_refusal(self) -> None:
        records = emit_records(
            load("attempts.json"), EXPERIMENT / "keys" / "test-private.pem"
        )

        self.assertEqual(len(records), 3)
        self.assertEqual(
            [(record["attempt_id"], record["record_kind"], record["outcome"]) for record in records],
            [
                ("attempt-allow", "decision", "allow"),
                ("attempt-deny", "decision", "deny"),
                ("attempt-refuse", "refusal", "unencodable"),
            ],
        )
        self.assertEqual(records[0]["previous_record_sha256"], "genesis")
        self.assertTrue(records[1]["previous_record_sha256"].startswith("sha256:"))
        self.assertTrue(records[2]["signature"].startswith("ed25519:"))


class RefusalCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load("attempts.json")
        cls.public_key = EXPERIMENT / "keys" / "test-public.pem"
        cls.records = emit_records(
            cls.manifest, EXPERIMENT / "keys" / "test-private.pem"
        )

    def test_complete_records_verify(self) -> None:
        result = check_records(self.manifest, self.records, self.public_key)
        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["missing_attempt_ids"], [])
        self.assertTrue(result["signature_verification_passed"])
        self.assertTrue(result["chain_verification_passed"])

    def test_missing_terminal_refusal_is_a_violation_even_when_chain_still_valid(self) -> None:
        result = check_records(self.manifest, self.records[:-1], self.public_key)
        self.assertEqual(result["outcome"], "violation")
        self.assertEqual(result["missing_attempt_ids"], ["attempt-refuse"])
        self.assertTrue(result["signature_verification_passed"])
        self.assertTrue(result["chain_verification_passed"])
        self.assertEqual(result["decisive_check"], "external-attempt-commitment")

    def test_missing_middle_record_breaks_completeness_and_chain(self) -> None:
        result = check_records(
            self.manifest, [self.records[0], self.records[2]], self.public_key
        )
        self.assertEqual(result["outcome"], "violation")
        self.assertEqual(result["missing_attempt_ids"], ["attempt-deny"])
        self.assertFalse(result["chain_verification_passed"])

    def test_silence_without_an_external_commitment_is_unverifiable(self) -> None:
        result = check_records({}, [], self.public_key)
        self.assertEqual(result["outcome"], "unverifiable")
        self.assertEqual(result["decisive_check"], "missing-external-commitment")

    def test_tampered_record_signature_is_rejected(self) -> None:
        tampered = [dict(record) for record in self.records]
        tampered[0]["outcome"] = "deny"
        result = check_records(self.manifest, tampered, self.public_key)
        self.assertEqual(result["outcome"], "violation")
        self.assertFalse(result["signature_verification_passed"])

    def test_malformed_signature_is_a_violation_not_a_checker_crash(self) -> None:
        malformed = [dict(record) for record in self.records]
        malformed[0]["signature"] = "ed25519:not*base64"

        result = check_records(self.manifest, malformed, self.public_key)

        self.assertEqual(result["outcome"], "violation")
        self.assertFalse(result["signature_verification_passed"])

    def test_validly_signed_records_must_match_the_external_attempt_semantics(self) -> None:
        different_manifest = copy.deepcopy(self.manifest)
        different_manifest["attempts"][0]["tool"] = "inventory.export"
        different_manifest["attempts"][2]["unencodable_arguments"]["field"] = "other"
        differently_signed = emit_records(
            different_manifest, EXPERIMENT / "keys" / "test-private.pem"
        )

        result = check_records(self.manifest, differently_signed, self.public_key)

        self.assertEqual(result["outcome"], "violation")
        self.assertTrue(result["signature_verification_passed"])
        self.assertFalse(result["record_semantics_passed"])


class RefusalExperimentTests(unittest.TestCase):
    def test_upstream_tail_deletion_result_is_pinned(self) -> None:
        artifact = EXPERIMENT / "artifacts" / "upstream-tail-deletion.json"
        self.assertTrue(artifact.is_file(), "frozen upstream result is missing")
        result = json.loads(
            artifact.read_text(encoding="utf-8")
        )

        self.assertEqual(
            result["upstream_commit"],
            "f2efb313d113149c6ddc9656307a605a7619f8ea",
        )
        self.assertEqual(
            result["full"],
            {"breaks": [], "ok": True, "total": 3},
        )
        self.assertEqual(
            result["tail_deleted"],
            {"breaks": [], "ok": True, "total": 2},
        )
        self.assertEqual(
            result["finding"],
            "present-record verification does not establish terminal completeness",
        )

    def test_frozen_cases_produce_the_expected_four_outcomes(self) -> None:
        report = run_experiment(EXPERIMENT)
        self.assertEqual(
            report["sources_sha256"],
            hashlib.sha256((EXPERIMENT / "sources.json").read_bytes()).hexdigest(),
        )
        outcomes = {case["case_id"]: case["outcome"] for case in report["results"]}
        self.assertEqual(
            outcomes,
            {
                "complete": "verified",
                "missing-terminal-refusal": "violation",
                "missing-middle-deny": "violation",
                "no-external-commitment": "unverifiable",
            },
        )
        terminal = next(
            case for case in report["results"] if case["case_id"] == "missing-terminal-refusal"
        )
        self.assertTrue(terminal["chain_verification_passed"])
        self.assertEqual(terminal["decisive_check"], "external-attempt-commitment")
        self.assertTrue(report["all_expected"])

    def test_cli_report_matches_committed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "audit_refusal_fit",
                    "--experiment",
                    str(EXPERIMENT),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            committed = json.loads(
                (EXPERIMENT / "artifacts" / "results.json").read_text(encoding="utf-8")
            )
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), committed)

    def test_source_pins_are_frozen_and_fetchable_by_the_existing_fetcher(self) -> None:
        sources = load("sources.json")["sources"]
        self.assertEqual(
            [source["id"] for source in sources],
            [
                "bradley-acceptance-message",
                "audit-decision-records-00",
                "execution-governance-receipts",
            ],
        )
        for source in sources:
            self.assertEqual(len(source["sha256"]), 64)
            int(source["sha256"], 16)
            self.assertGreater(source["bytes"], 0)
            self.assertTrue(
                source.get("url", "").startswith("https://")
                or len(source.get("commit", "")) == 40
            )

    def test_committed_report_hash_is_named_in_the_experiment_readme(self) -> None:
        artifact = (EXPERIMENT / "artifacts" / "results.json").read_bytes()
        digest = hashlib.sha256(artifact).hexdigest()
        readme = (EXPERIMENT / "README.md").read_text(encoding="utf-8")
        self.assertIn(digest, readme)
        self.assertIn("missing-terminal-refusal", readme)
        self.assertIn("external-attempt-commitment", readme)
        self.assertIn("not an external reproduction", readme.lower())

    def test_root_readme_points_to_the_refusal_completeness_experiment(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("AUDIT-REFUSAL-COMPLETENESS-001", readme)
        self.assertIn("audit-refusal-completeness-001", readme)


if __name__ == "__main__":
    unittest.main()
