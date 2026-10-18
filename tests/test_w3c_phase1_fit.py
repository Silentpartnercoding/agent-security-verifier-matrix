from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from w3c_phase1_fit import FixtureError, evaluate_pair, run_experiment


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "w3c-phase1-root-cardinality-001"


def load_cases() -> dict:
    return json.loads((EXPERIMENT / "cases.json").read_text(encoding="utf-8"))


class W3cPhase1PairTests(unittest.TestCase):
    def test_roundtrip_preserves_one_root_vs_three_roots(self) -> None:
        report = evaluate_pair(load_cases())
        by_id = {case["case_id"]: case for case in report["case_results"]}

        self.assertEqual(
            by_id["one-observed-root"]["distinct_observed_root_ids"], ["R"]
        )
        self.assertEqual(
            by_id["one-observed-root"]["distinct_observed_root_count"], 1
        )
        self.assertEqual(
            by_id["three-observed-roots"]["distinct_observed_root_ids"],
            ["R1", "R2", "R3"],
        )
        self.assertEqual(
            by_id["three-observed-roots"]["distinct_observed_root_count"], 3
        )
        self.assertTrue(report["same_computed_artifacts"])
        self.assertTrue(report["same_attestation_count"])
        self.assertTrue(report["serialization_roundtrip_preserved"])
        self.assertTrue(report["preserves_required_distinction"])
        self.assertEqual(
            report["expanded_lineage_predicate"],
            "http://www.w3.org/ns/prov#wasDerivedFrom",
        )
        self.assertEqual(
            report["expanded_lineage_quads"],
            {
                "one-observed-root": [
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/A",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/R",
                    },
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/B",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/R",
                    },
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/C",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/R",
                    },
                ],
                "three-observed-roots": [
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/A",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/R1",
                    },
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/B",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/R2",
                    },
                    {
                        "subject": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/C",
                        "predicate": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "object": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/R3",
                    },
                ],
            },
        )
        self.assertEqual(report["independence_state"], "not-established")

    def test_missing_immediate_input_fails_closed_with_its_id(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["observed_artifacts"] = []

        with self.assertRaisesRegex(FixtureError, "missing immediate input R"):
            evaluate_pair(document)

    def test_duplicate_artifact_id_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["observed_artifacts"].append(
            {"@id": "one:R", "label": "R-copy", "value": "different-observation"}
        )

        with self.assertRaisesRegex(FixtureError, "duplicate artifact id one:R"):
            evaluate_pair(document)

    def test_pair_must_share_one_producer_and_context(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][1]["context"] = "different-context"

        with self.assertRaisesRegex(FixtureError, "one producer/context"):
            evaluate_pair(document)

    def test_proposition_drift_breaks_the_paired_control(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][1]["computed_artifacts"][0]["proposition"] = (
            "different-proposition"
        )

        with self.assertRaisesRegex(FixtureError, "computed controls differ"):
            evaluate_pair(document)

    def test_computed_artifact_without_ancestry_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        del document["cases"][0]["computed_artifacts"][0][
            "prov:wasDerivedFrom"
        ]

        with self.assertRaisesRegex(FixtureError, "A must have one immediate input"):
            evaluate_pair(document)

    def test_unreferenced_observed_artifact_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["observed_artifacts"].append(
            {"@id": "one:UNUSED", "label": "UNUSED", "value": "same-observation"}
        )

        with self.assertRaisesRegex(FixtureError, "unreferenced observed artifact UNUSED"):
            evaluate_pair(document)

    def test_observed_root_cannot_carry_ancestry(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["observed_artifacts"][0][
            "prov:wasDerivedFrom"
        ] = [{"@id": "X"}]

        with self.assertRaisesRegex(FixtureError, "observed roots cannot carry lineage"):
            evaluate_pair(document)

    def test_undefined_jsonld_carrier_term_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["computed_artifacts"][0]["mystery"] = "dropped"

        with self.assertRaisesRegex(FixtureError, "undefined JSON-LD term mystery"):
            evaluate_pair(document)

    def test_case_scoped_node_ids_prevent_graph_merge(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][1]["computed_artifacts"][0]["@id"] = "one:A"

        with self.assertRaisesRegex(FixtureError, "node identifiers differ"):
            evaluate_pair(document)

    def test_case_namespace_collision_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["@context"]["three"] = document["@context"]["one"]

        with self.assertRaisesRegex(FixtureError, "distinct frozen case namespaces"):
            evaluate_pair(document)

    def test_document_wrapper_cannot_hide_extra_lineage(self) -> None:
        document = copy.deepcopy(load_cases())
        document["prov:wasDerivedFrom"] = [{"@id": "one:R"}]

        with self.assertRaisesRegex(FixtureError, "document shape differs"):
            evaluate_pair(document)

    def test_case_wrapper_cannot_hide_extra_lineage(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["prov:wasDerivedFrom"] = [{"@id": "one:R"}]

        with self.assertRaisesRegex(FixtureError, "case shape differs"):
            evaluate_pair(document)

    def test_incomplete_computed_set_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["computed_artifacts"].pop()

        with self.assertRaisesRegex(FixtureError, "must contain exactly A, B, and C"):
            evaluate_pair(document)

    def test_unchecked_attestation_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        document["cases"][0]["computed_artifacts"][0]["attestation"] = "unchecked"

        with self.assertRaisesRegex(FixtureError, "three checked attestations"):
            evaluate_pair(document)

    def test_missing_producer_fails_closed(self) -> None:
        document = copy.deepcopy(load_cases())
        del document["cases"][0]["producer"]

        with self.assertRaisesRegex(FixtureError, "non-empty producer and context"):
            evaluate_pair(document)

    def test_three_root_case_must_pair_each_output_with_its_root(self) -> None:
        document = copy.deepcopy(load_cases())
        computed = document["cases"][1]["computed_artifacts"]
        computed[0]["prov:wasDerivedFrom"] = [
            {"@id": "three:R1"},
            {"@id": "three:R2"},
            {"@id": "three:R3"},
        ]
        computed[1]["prov:wasDerivedFrom"] = []
        computed[2]["prov:wasDerivedFrom"] = []

        with self.assertRaisesRegex(FixtureError, "A must have one immediate input"):
            evaluate_pair(document)

    def test_frozen_report_matches_regeneration(self) -> None:
        report = run_experiment(EXPERIMENT)
        committed = json.loads(
            (EXPERIMENT / "artifacts" / "results.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(report, committed)

    def test_one_command_cli_reproduces_frozen_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "results.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "w3c_phase1_fit",
                    "--experiment",
                    str(EXPERIMENT),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                output.read_bytes(),
                (EXPERIMENT / "artifacts" / "results.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
