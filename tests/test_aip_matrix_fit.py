from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aip_matrix_fit import canonical_argument_digest, evaluate_all, verify_pinned_bytes

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class FrozenArtifactTests(unittest.TestCase):
    def test_matrix_has_the_eight_frozen_rows_and_required_columns(self) -> None:
        matrix = load("matrix.json")
        rows = matrix["rows"]
        self.assertEqual(
            [row["label"] for row in rows],
            [
                "Identity",
                "Authority",
                "Presenter",
                "Scope",
                "Action",
                "Provenance",
                "Freshness",
                "Independence",
            ],
        )
        required = {
            "carrier",
            "verifier",
            "binding",
            "failure",
            "result",
            "permitted_conclusion",
        }
        for row in rows:
            self.assertTrue(required.issubset(row), row["id"])
            self.assertIn(row["result"], matrix["report_dispositions"])

    def test_four_cases_are_complete_and_keep_the_chain_valid(self) -> None:
        cases = load("cases.json")["cases"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "wrong_presenter",
                "same_control_verifier",
                "stale_unverifiable_completion",
                "a2a_mcp_action_swap",
            ],
        )
        for case in cases:
            self.assertIs(case["situation"]["aip_chain_valid"], True)
            self.assertTrue(case["prohibited_conclusions"])

    def test_border_case_is_reused_with_its_pinned_identity(self) -> None:
        case = load("cases.json")["cases"][3]["reused_border_case"]
        sources = {item["id"]: item for item in load("sources.json")["sources"]}
        self.assertEqual(case["experiment"], "A2A-MCP-CROSSING-001")
        self.assertEqual(case["id"], "change_mcp_tool_or_payload")
        self.assertEqual(
            case["mutation"],
            "the MCP tool name or its arguments differ from what the authority named",
        )
        self.assertEqual(case["source_commit"], sources["border-crossing-cases"]["commit"])
        self.assertEqual(
            case["source_blob_sha256"], sources["border-crossing-cases"]["sha256"]
        )

    def test_source_pins_are_full_sha256_values(self) -> None:
        for source in load("sources.json")["sources"]:
            self.assertEqual(len(source["sha256"]), 64)
            int(source["sha256"], 16)
            if source["kind"] == "git-blob":
                self.assertEqual(len(source["commit"]), 40)
                int(source["commit"], 16)


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = evaluate_all()
        cls.results = {item["case_id"]: item for item in cls.report["results"]}

    def test_all_frozen_cases_conform(self) -> None:
        self.assertTrue(self.report["all_conform"])
        self.assertEqual(self.report["case_count"], 4)

    def test_wrong_presenter_is_a_good_declared_gap(self) -> None:
        result = self.results["wrong_presenter"]
        self.assertEqual(result["mapping_result"], "DECLARED-GAP")
        self.assertEqual(result["row_outcome"], "unsupported")
        self.assertIn("aip_chain_valid", result["adjacent_successes"])

    def test_same_control_signature_does_not_mint_independence(self) -> None:
        result = self.results["same_control_verifier"]
        self.assertEqual(result["mapping_result"], "AMBIGUOUS")
        self.assertEqual(result["row_outcome"], "indeterminate")
        self.assertIn("attestation_signature_valid", result["adjacent_successes"])

    def test_unverifiable_is_not_collapsed_into_rejected(self) -> None:
        result = self.results["stale_unverifiable_completion"]
        self.assertEqual(result["warrant_outcome"], "unverifiable")
        self.assertNotEqual(result["warrant_outcome"], "rejected")
        self.assertEqual(result["row_outcome"], "indeterminate")

    def test_action_swap_preserves_scope_success_without_claim_elevation(self) -> None:
        result = self.results["a2a_mcp_action_swap"]
        self.assertIn("aip_tool_scope_satisfied", result["adjacent_successes"])
        self.assertEqual(result["mapping_result"], "UNREPRESENTED")
        self.assertEqual(result["row_outcome"], "unsupported")
        self.assertEqual(result["border_reference_outcome"], "unsatisfied")
        self.assertNotEqual(
            result["authorized_argument_digest"], result["observed_argument_digest"]
        )

    def test_border_digest_is_canonical_across_key_order(self) -> None:
        self.assertEqual(
            canonical_argument_digest({"a": 1, "b": 2}),
            canonical_argument_digest({"b": 2, "a": 1}),
        )

    def test_pin_verification_checks_both_length_and_digest(self) -> None:
        data = b"pinned source bytes\n"
        digest = hashlib.sha256(data).hexdigest()
        self.assertTrue(verify_pinned_bytes(data, digest, len(data)))
        self.assertFalse(verify_pinned_bytes(data, digest, len(data) + 1))
        self.assertFalse(verify_pinned_bytes(data + b"x", digest, None))

    def test_cli_report_matches_library_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            completed = subprocess.run(
                [sys.executable, "-m", "aip_matrix_fit", "--output", str(output)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.report)


if __name__ == "__main__":
    unittest.main()
