from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aip_matrix_fit import (
    canonical_argument_digest,
    evaluate_all,
    verify_pinned_bytes,
    verify_source_files,
)
from aip_matrix_fit.__main__ import _source_files_from_directory
from scripts.fetch_pinned_sources import FetchError, _source_url, fetch_all

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class CorrectedArtifactTests(unittest.TestCase):
    def test_matrix_has_separate_presenter_and_freshness_rows(self) -> None:
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
                "Credential Freshness",
                "Evidence Freshness",
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

    def test_artifact_participants_are_not_mapped_to_live_identity(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        self.assertNotIn("C-001", rows["delegation-participants"]["principal_binding_claim_ids"])
        self.assertIn("C-001", rows["presenter"]["principal_binding_claim_ids"])
        self.assertIn(
            "independently authenticated",
            " ".join(rows["delegation-participants"]["non_claims"]),
        )

    def test_scope_declares_ambient_fact_supplier_and_authentication_boundary(self) -> None:
        rows = {row["id"]: row for row in load("matrix.json")["rows"]}
        trust = rows["scope"]["ambient_input_trust"]
        self.assertEqual(set(trust), {"supplier", "authentication", "decision_boundary"})
        self.assertIn("physical", trust["authentication"])

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

    def test_source_directory_uses_manifest_ids_as_filenames(self) -> None:
        source_files = _source_files_from_directory(Path("vendor/sources"))
        self.assertEqual(len(source_files), 6)
        self.assertEqual(
            source_files["principal-binding-06"],
            Path("vendor/sources/principal-binding-06"),
        )


class PinnedSourceFetcherTests(unittest.TestCase):
    def test_git_blob_url_is_derived_from_full_commit(self) -> None:
        pin = {
            "id": "example",
            "repository": "https://github.com/example/project",
            "commit": "a" * 40,
            "path": "dir/source file.txt",
        }
        self.assertEqual(
            _source_url(pin),
            "https://raw.githubusercontent.com/example/project/"
            + "a" * 40
            + "/dir/source%20file.txt",
        )

    def test_fetcher_installs_only_verified_bytes(self) -> None:
        data = b"pinned bytes\n"
        manifest = {
            "sources": [
                {
                    "id": "source-1",
                    "url": "https://example.test/source.txt",
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "sources.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            def opener(request: object, timeout: int) -> io.BytesIO:
                self.assertEqual(timeout, 30)
                return io.BytesIO(data)

            installed = fetch_all(manifest_path, root / "vendor" / "sources", opener)
            self.assertEqual([path.name for path in installed], ["source-1"])
            self.assertEqual(installed[0].read_bytes(), data)

    def test_fetcher_fails_closed_on_digest_mismatch(self) -> None:
        manifest = {
            "sources": [
                {
                    "id": "source-1",
                    "url": "https://example.test/source.txt",
                    "sha256": "0" * 64,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "sources.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(FetchError):
                fetch_all(
                    manifest_path,
                    root / "vendor" / "sources",
                    lambda request, timeout: io.BytesIO(b"changed"),
                )
            self.assertFalse((root / "vendor" / "sources" / "source-1").exists())


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
        self.assertEqual(result["expected_row_outcome"], "unsupported")
        self.assertNotIn("row_outcome", result)
        self.assertIn("aip_chain_valid", result["adjacent_successes"])

    def test_same_control_signature_does_not_mint_independence(self) -> None:
        result = self.results["same_control_verifier"]
        self.assertEqual(result["mapping_result"], "AMBIGUOUS")
        self.assertEqual(result["expected_row_outcome"], "indeterminate")
        self.assertIn("attestation_signature_valid", result["adjacent_successes"])

    def test_unverifiable_is_not_collapsed_into_rejected(self) -> None:
        result = self.results["stale_unverifiable_completion"]
        self.assertEqual(result["warrant_outcome"], "unverifiable")
        self.assertNotEqual(result["warrant_outcome"], "rejected")
        self.assertEqual(result["expected_row_outcome"], "indeterminate")

    def test_action_swap_preserves_scope_success_without_claim_elevation(self) -> None:
        result = self.results["a2a_mcp_action_swap"]
        self.assertIn("aip_tool_scope_satisfied", result["adjacent_successes"])
        self.assertEqual(result["mapping_result"], "UNREPRESENTED")
        self.assertEqual(result["expected_row_outcome"], "unsupported")
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

    def test_source_verification_reports_skipped_passed_and_failed(self) -> None:
        self.assertEqual(verify_source_files()["status"], "skipped")
        data = b"locally supplied source bytes\n"
        digest = hashlib.sha256(data).hexdigest()
        manifest = {
            "sources": [
                {"id": "test-source", "sha256": digest, "bytes": len(data)}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_bytes(data)
            with patch("aip_matrix_fit.evaluator._load", return_value=manifest):
                self.assertEqual(
                    verify_source_files({"test-source": path})["status"], "passed"
                )
                path.write_bytes(data + b"changed")
                self.assertEqual(
                    verify_source_files({"test-source": path})["status"], "failed"
                )

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

    def test_cli_fails_closed_when_source_verification_is_required_but_skipped(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "aip_matrix_fit", "--require-source-verification"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)


if __name__ == "__main__":
    unittest.main()
