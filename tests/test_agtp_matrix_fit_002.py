from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from verifier_matrix import evaluate_experiment


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "agtp-matrix-fit-002"


def load(name: str) -> dict:
    return json.loads((EXPERIMENT / name).read_text(encoding="utf-8"))


class CorrectedAgtpMappingTests(unittest.TestCase):
    def test_human_readable_labels_are_not_claim_identifiers(self) -> None:
        matrix = load("matrix.json")
        self.assertIn("grouping_labels", matrix)
        self.assertNotIn("core_claim_classes", matrix)
        self.assertIn("not Principal Binding", matrix["grouping_label_semantics"])
        self.assertEqual(matrix["claim_inventory_completeness"], "not-established")

    def test_artifact_identity_is_not_promoted_to_live_instance_identity(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        artifact = rows["identity-document-artifact"]
        presenter = rows["live-presenter"]
        self.assertEqual(artifact["principal_binding_claim_ids"], [])
        self.assertEqual(artifact["principal_binding_role"], "supporting-fact-only")
        self.assertNotIn("C-001", artifact["principal_binding_claim_ids"])
        self.assertEqual(presenter["principal_binding_claim_ids"], ["C-001"])
        self.assertEqual(presenter["result"], "AMBIGUOUS")

    def test_c003_scope_is_narrow_and_does_not_claim_a_chain(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        authority = rows["delegated-authority"]
        self.assertIn("issuer-stated baseline scope", authority["issued_baseline_scope"])
        self.assertIn("does not establish", authority["issued_baseline_scope"])
        self.assertEqual(authority["result"], "AMBIGUOUS")

    def test_review_constraints_are_not_result_objects(self) -> None:
        matrix = load("matrix.json")
        cases = load("cases.json")
        self.assertEqual(matrix["result_object_status"], "not-emitted")
        self.assertIn("not a stable", matrix["permitted_conclusion_semantics"])
        self.assertIn("not a complete", cases["outcome_semantics"])

    def test_four_cases_still_reproduce_under_corrected_interpretation(self) -> None:
        report = evaluate_experiment(EXPERIMENT)
        self.assertTrue(report["all_conform"])
        self.assertEqual(report["case_count"], 4)
        self.assertEqual(report["evaluator_version"], "1.1.0")
        self.assertIn("grouping_labels", report)
        self.assertNotIn("core_claim_classes", report)
        self.assertEqual(report["claim_inventory_completeness"], "not-established")

    def test_committed_artifact_and_registry_hashes_match(self) -> None:
        record = json.loads(
            (ROOT / "registry" / "records" / "agtp-matrix-fit-002.mapping.json").read_text()
        )
        for name in ["matrix.json", "cases.json", "sources.json", "artifacts/results.json"]:
            observed = hashlib.sha256((EXPERIMENT / name).read_bytes()).hexdigest()
            self.assertEqual(observed, record["payload"]["artifact_hashes"][name])


if __name__ == "__main__":
    unittest.main()
