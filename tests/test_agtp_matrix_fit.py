from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verifier_matrix import evaluate_experiment


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "agtp-matrix-fit-001"
EXPECTED_LABELS = [
    "Identity",
    "Authority",
    "Presenter",
    "Scope",
    "Action",
    "Provenance",
    "Credential Freshness",
    "Evidence Freshness",
    "Independence",
]


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


class AgtpMatrixArtifactTests(unittest.TestCase):
    def test_second_protocol_reuses_the_same_claim_classes(self) -> None:
        matrix = load("matrix.json")
        self.assertEqual(matrix["core_claim_classes"], EXPECTED_LABELS)
        self.assertEqual([row["label"] for row in matrix["rows"]], EXPECTED_LABELS)
        self.assertFalse(matrix["claim_semantics_extended"])
        self.assertFalse(matrix["registry_envelope_changed"])

    def test_profile_does_not_import_unpinned_companion_semantics(self) -> None:
        profile = load("matrix.json")["profile"]
        self.assertIn("AGTP-CERT", profile)
        self.assertIn("not imported", profile)

    def test_presenter_lookup_is_not_promoted_to_proof_of_possession(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        presenter = rows["live-presenter"]
        self.assertEqual(presenter["result"], "AMBIGUOUS")
        self.assertIn("proof-of-possession", presenter["verifier"])
        self.assertIn("live sender", presenter["permitted_conclusion"])

    def test_scope_failure_conflict_is_machine_readable(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        failure = rows["request-scope"]["failure"]
        self.assertIn("262", failure)
        self.assertIn("455", failure)
        self.assertEqual(rows["request-scope"]["result"], "AMBIGUOUS")

    def test_source_pins_are_complete(self) -> None:
        sources = load("sources.json")["sources"]
        self.assertEqual(len(sources), 5)
        for source in sources:
            self.assertEqual(len(source["sha256"]), 64)
            int(source["sha256"], 16)
        agtp = next(source for source in sources if source["id"] == "agtp-08")
        self.assertEqual(agtp["bytes"], 429521)
        self.assertEqual(agtp["revision"], "draft-hood-independent-agtp-08")


class ProtocolNeutralEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = evaluate_experiment(EXPERIMENT)
        cls.results = {item["case_id"]: item for item in cls.report["results"]}

    def test_all_four_vectors_conform_without_extending_semantics(self) -> None:
        self.assertTrue(self.report["all_conform"])
        self.assertEqual(self.report["case_count"], 4)
        self.assertFalse(self.report["claim_semantics_extended"])
        self.assertFalse(self.report["registry_envelope_changed"])

    def test_wrong_presenter_remains_indeterminate(self) -> None:
        result = self.results["wrong_presenter"]
        self.assertEqual(result["mapping_result"], "AMBIGUOUS")
        self.assertEqual(result["expected_row_outcome"], "indeterminate")
        self.assertIn("identity_document_signature_valid", result["adjacent_successes"])

    def test_unverifiable_evidence_is_not_rejection(self) -> None:
        result = self.results["stale_unverifiable_completion"]
        self.assertEqual(result["warrant_outcome"], "unverifiable")
        self.assertNotEqual(result["warrant_outcome"], "rejected")

    def test_action_swap_preserves_adjacent_authorization_success(self) -> None:
        result = self.results["a2a_mcp_action_swap"]
        self.assertEqual(result["mapping_result"], "AMBIGUOUS")
        self.assertEqual(result["border_reference_outcome"], "unsatisfied")
        self.assertIn("governance_token_unexpired", result["adjacent_successes"])
        self.assertNotEqual(
            result["authorized_argument_digest"], result["observed_argument_digest"]
        )

    def test_committed_report_matches_regeneration_except_supplied_source_state(self) -> None:
        committed = load("artifacts/results.json")
        regenerated = dict(self.report)
        committed_without_sources = dict(committed)
        regenerated.pop("source_byte_verification")
        committed_without_sources.pop("source_byte_verification")
        self.assertEqual(regenerated, committed_without_sources)
        self.assertEqual(committed["source_byte_verification"]["status"], "passed")

    def test_committed_artifact_hash_matches_registry_record(self) -> None:
        artifact = (EXPERIMENT / "artifacts" / "results.json").read_bytes()
        digest = hashlib.sha256(artifact).hexdigest()
        record = json.loads(
            (ROOT / "registry" / "records" / "agtp-matrix-fit-001.mapping.json").read_text()
        )
        self.assertEqual(digest, record["payload"]["artifact_hashes"]["artifacts/results.json"])

    def test_generic_cli_runs_the_second_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "verifier_matrix",
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
            self.assertEqual(json.loads(output.read_text()), self.report)


if __name__ == "__main__":
    unittest.main()
