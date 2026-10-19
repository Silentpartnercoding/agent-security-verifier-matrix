import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audit.summarize import summarize
from audit.build_comparison import build_rows
from audit.replay_mutations import normalized_stderr_sha256


ROOT = Path(__file__).resolve().parents[1]


class AuditSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = summarize(ROOT)

    def test_three_way_verdict_matrix_is_frozen(self):
        self.assertEqual(
            self.summary["verdict_matrix"],
            {
                "accept/accept/cannot-tell": 77,
                "accept/cannot-tell/cannot-tell": 44,
                "accept/reject/cannot-tell": 3,
                "reject/accept/cannot-tell": 5,
                "reject/cannot-tell/cannot-tell": 1,
                "reject/cannot-tell/reject": 10,
                "reject/reject/cannot-tell": 1,
                "reject/reject/reject": 24,
            },
        )

    def test_clean_reader_never_opposes_oracle(self):
        self.assertEqual(self.summary["clean_opposite_oracle"], [])
        self.assertEqual(self.summary["clean_counts"], {"accept": 0, "cannot-tell": 131, "reject": 34})

    def test_clean_reader_finds_explicit_violations_lars_leaves_open(self):
        self.assertEqual(
            self.summary["clean_reject_lars_cannot_tell"],
            [
                "case-014", "case-052", "case-063", "case-073", "case-092",
                "case-096", "case-099", "case-130", "case-131", "case-149",
            ],
        )

    def test_public_claim_adjudication_separates_policy_disputes_from_ambiguities(self):
        adjudication = json.loads(
            (ROOT / "artifacts" / "lars-cannot-tell-adjudication.json").read_text()
        )
        self.assertEqual(
            adjudication["subject_commit"],
            "6d8ee54b01d20a819869ceb9fcea096d59251f8c",
        )
        self.assertEqual(len(adjudication["cases"]), 10)
        self.assertEqual(
            {row["classification"] for row in adjudication["cases"]},
            {
                "explicit-contradiction-disputed-rejection-policy",
                "underdetermined-under-v0.1",
            },
        )
        policy_disputes = {
            row["case"] for row in adjudication["cases"]
            if row["classification"] == "explicit-contradiction-disputed-rejection-policy"
        }
        underdetermined = {
            row["case"] for row in adjudication["cases"]
            if row["classification"] == "underdetermined-under-v0.1"
        }
        self.assertEqual(
            policy_disputes,
            {
                "case-014", "case-052", "case-073", "case-092",
                "case-096", "case-130", "case-131", "case-149",
            },
        )
        self.assertEqual(underdetermined, {"case-063", "case-099"})
        self.assertEqual(
            policy_disputes | underdetermined,
            set(self.summary["clean_reject_lars_cannot_tell"]),
        )
        self.assertEqual(adjudication["claim_boundary"]["policy_dispute_count"], 8)
        self.assertEqual(adjudication["claim_boundary"]["underdetermined_count"], 2)
        self.assertEqual(
            adjudication["claim_boundary"]["permitted_public_claim"],
            "Eight cases contain explicit input contradictions or omissions that the Lars reader detects but does not make mandatory rejection grounds under its documented v0.1 refusal policy; two additional disagreements remain underdetermined by v0.1.",
        )
        self.assertNotIn(
            "proven violations",
            adjudication["claim_boundary"]["permitted_public_claim"].lower(),
        )

    def test_lars_oracle_oppositions_are_listed_not_overclaimed(self):
        self.assertEqual(
            self.summary["lars_opposite_oracle"],
            ["case-015", "case-036", "case-051", "case-053", "case-098", "case-142", "case-155", "case-164"],
        )

    def test_adversarial_mutations_cover_completeness_order_and_parser_failures(self):
        by_case = self.summary["mutations"]
        self.assertEqual(by_case["omit_rejected_member"]["exit"], 0)
        self.assertEqual(by_case["omit_rejected_member"]["output_lines"], 164)
        self.assertEqual(by_case["duplicate_member_file"]["exit"], 0)
        self.assertEqual(by_case["duplicate_member_file"]["output_lines"], 166)
        self.assertEqual(by_case["duplicate_json_key"]["exit"], 0)
        self.assertEqual(by_case["empty_directory"]["exit"], 0)
        self.assertEqual(by_case["empty_directory"]["output_lines"], 0)
        for name in ("unhashable_evidence_id", "integer_observations", "list_negative_kind"):
            self.assertNotEqual(by_case[name]["exit"], 0)

    def test_replay_is_bound_to_exact_inputs_outputs_and_legacy_results(self):
        replay = json.loads((ROOT / "artifacts" / "mutation-replay.json").read_text())
        self.assertEqual(replay["source_commit"], "6d8ee54b01d20a819869ceb9fcea096d59251f8c")
        self.assertEqual(len(replay["recipes"]), 35)
        by_case = {row["case"]: row for row in replay["recipes"]}
        legacy = []
        for name in ("mutation-results.json", "mutation-results-more.json"):
            legacy.extend(json.loads((ROOT / "artifacts" / name).read_text()))
        for old in legacy:
            current = by_case[old["case"]]
            for key in ("exit", "output_lines", "summary", "affected"):
                self.assertEqual(current[key], old[key], (old["case"], key))
            for key in ("mutated_input_tree_sha256", "stdout_sha256", "stderr_sha256"):
                self.assertRegex(current[key], r"^[0-9a-f]{64}$")

    def test_crash_fingerprint_ignores_only_local_fixture_paths(self):
        left = b'Traceback\n  File "/tmp/clone-a/reader.py", line 1\n  File "/tmp/case-a/member.json"\nTypeError: boom\n'
        right = b'Traceback\n  File "/different/clone/reader.py", line 1\n  File "/different/case/member.json"\nTypeError: boom\n'
        self.assertEqual(
            normalized_stderr_sha256(left, Path("/tmp/clone-a"), Path("/tmp/case-a")),
            normalized_stderr_sha256(right, Path("/different/clone"), Path("/different/case")),
        )

    def test_frozen_summary_round_trips(self):
        frozen = json.loads((ROOT / "artifacts" / "audit-summary.json").read_text())
        self.assertEqual(self.summary, frozen)

    def test_comparison_rows_rebuild_from_three_frozen_sources(self):
        expected = json.loads((ROOT / "artifacts" / "comparison-rows.json").read_text())
        self.assertEqual(build_rows(ROOT), expected)

    def test_comparison_rejects_duplicate_lars_identifier(self):
        with tempfile.TemporaryDirectory(prefix="comparison-duplicate-") as tmp:
            target = Path(tmp) / "experiment"
            shutil.copytree(ROOT, target)
            path = target / "artifacts" / "lars-run.jsonl"
            first = path.read_text().splitlines()[0]
            with path.open("a") as stream:
                stream.write(first + "\n")
            with self.assertRaises(ValueError):
                build_rows(target)

    def test_comparison_rejects_unexpected_lars_identifier(self):
        with tempfile.TemporaryDirectory(prefix="comparison-extra-") as tmp:
            target = Path(tmp) / "experiment"
            shutil.copytree(ROOT, target)
            path = target / "artifacts" / "lars-run.jsonl"
            with path.open("a") as stream:
                stream.write(json.dumps({"id": "unexpected", "verdict": "accept", "ground": "", "grounds": []}) + "\n")
            with self.assertRaises(ValueError):
                build_rows(target)


if __name__ == "__main__":
    unittest.main()
