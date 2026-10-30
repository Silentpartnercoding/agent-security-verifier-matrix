from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from verifier_matrix import evaluate_experiment
from verifier_matrix.evaluator import EvaluationError, VECTOR_EVALUATORS, agtp_action_digest


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "agtp-matrix-fit-003"
PREVIOUS = ROOT / "experiments" / "agtp-matrix-fit-002"


def load(name: str, experiment: Path = EXPERIMENT) -> dict:
    return json.loads((experiment / name).read_text(encoding="utf-8"))


def rows() -> dict:
    return {row["id"]: row for row in load("matrix.json")["rows"]}


def case(case_id: str) -> dict:
    return copy.deepcopy(next(item for item in load("cases.json")["cases"] if item["id"] == case_id))


class AgtpTenRoundTests(unittest.TestCase):
    def test_round_is_pinned_to_agtp_10_and_imports_one_companion(self) -> None:
        matrix = load("matrix.json")
        self.assertEqual(matrix["source_protocol"], "draft-hood-independent-agtp-10")
        self.assertEqual(matrix["evaluation_vocabulary"], "draft-bu-agentproto-security-principal-binding-06")
        self.assertEqual(matrix["evaluator_contract"], "1.2.0")
        imports = matrix["companion_imports"]
        self.assertEqual([item["source"] for item in imports], ["identity-document-00"])
        self.assertIn("agent_public_key", imports[0]["imported_for"])
        self.assertIn("draft-hood-agtp-identity-document-00 only for agent_public_key", matrix["profile"])
        for name in ["AGTP-CERT", "AGTP-LOG", "AGTP-TRUST", "AGTP-IDENTIFIERS", "AGTP-COMPOSITION"]:
            self.assertIn(name, matrix["companions_excluded"])
            self.assertIn(name, matrix["profile"])
        source_ids = {item["id"] for item in load("sources.json")["sources"]}
        self.assertIn("agtp-10", source_ids)
        self.assertIn("identity-document-00", source_ids)
        self.assertNotIn("agtp-08", source_ids)

    def test_previous_round_stays_pinned_to_agtp_08(self) -> None:
        self.assertEqual(load("matrix.json", PREVIOUS)["source_protocol"], "draft-hood-independent-agtp-08")
        self.assertNotIn("evaluator_contract", load("matrix.json", PREVIOUS))

    def test_grades(self) -> None:
        expected = {
            "identity-document-artifact": "EXACT",
            "delegated-authority": "EXACT",
            "live-presenter": "EXACT",
            "request-scope": "EXACT",
            "cross-protocol-action": "AMBIGUOUS",
            "completion-provenance": "AMBIGUOUS",
            "credential-freshness": "AMBIGUOUS",
            "completion-evidence-freshness": "AMBIGUOUS",
            "verifier-independence": "AMBIGUOUS",
        }
        self.assertEqual({key: row["result"] for key, row in rows().items()}, expected)
        for row in rows().values():
            self.assertTrue(any(ref.startswith("agtp-10:") for ref in row["source_refs"]))
            self.assertFalse(any(ref.startswith("agtp-08:") for ref in row["source_refs"]))

    def test_artifact_identity_stays_a_supporting_fact(self) -> None:
        artifact = rows()["identity-document-artifact"]
        self.assertEqual(artifact["principal_binding_claim_ids"], [])
        self.assertEqual(artifact["principal_binding_role"], "supporting-fact-only")
        presenter = rows()["live-presenter"]
        self.assertEqual(presenter["principal_binding_claim_ids"], ["C-001"])
        self.assertIn("shared agent key", " ".join(presenter["non_claims"]))

    def test_cross_protocol_action_keeps_task_binding_open(self) -> None:
        action = rows()["cross-protocol-action"]
        self.assertEqual(action["principal_binding_role"], "direct-incomplete-mapping")
        self.assertIn("task identifier sits outside", action["binding"])

    def test_report(self) -> None:
        report = evaluate_experiment(EXPERIMENT)
        self.assertTrue(report["all_conform"])
        self.assertEqual(report["case_count"], 9)
        self.assertEqual(report["evaluator_version"], "1.2.0")
        self.assertEqual(report["companion_imports"][0]["source"], "identity-document-00")
        outcomes = {item["case_id"]: item for item in report["results"]}
        self.assertEqual(outcomes["wrong_presenter"]["agtp_status"], 401)
        self.assertEqual(outcomes["widened_delegation_hop"]["failing_hop"], 1)
        self.assertEqual(outcomes["unreachable_delegation_registry"]["evaluation"], "incomplete")
        self.assertEqual(outcomes["unreachable_delegation_registry"]["relying_party_default"], "deny")
        self.assertEqual(outcomes["claimed_scope_beyond_grant"]["agtp_status"], 455)
        self.assertEqual(outcomes["granted_scope_unclaimed"]["agtp_status"], 262)
        self.assertEqual(outcomes["a2a_mcp_action_swap"]["agtp_reason"], "token-action-mismatch")
        self.assertEqual(outcomes["a2a_task_substitution"]["expected_row_outcome"], "indeterminate")
        self.assertEqual(outcomes["a2a_task_substitution"]["border_reference_outcome"], "unsatisfied")

    def test_committed_artifact_and_registry_hashes_match(self) -> None:
        record = json.loads(
            (ROOT / "registry" / "records" / "agtp-matrix-fit-003.mapping.json").read_text()
        )
        for name in ["matrix.json", "cases.json", "sources.json", "artifacts/results.json"]:
            observed = hashlib.sha256((EXPERIMENT / name).read_bytes()).hexdigest()
            self.assertEqual(observed, record["payload"]["artifact_hashes"][name])


class AgtpTenVectorGuardTests(unittest.TestCase):
    def run_vector(self, item: dict) -> dict:
        return VECTOR_EVALUATORS[item["vector_type"]](item, rows()[item["matrix_row"]])

    def test_presenter_vector_requires_a_substituted_key(self) -> None:
        item = case("wrong_presenter")
        item["situation"]["request_signature"]["signing_key"] = item["situation"]["document_agent_public_key"]
        with self.assertRaises(EvaluationError):
            self.run_vector(item)

    def test_presenter_vector_requires_agent_public_key(self) -> None:
        item = case("wrong_presenter")
        del item["situation"]["document_agent_public_key"]
        with self.assertRaises(EvaluationError):
            self.run_vector(item)

    def test_valid_delegation_chain_is_rejected_as_a_vector(self) -> None:
        item = case("widened_delegation_hop")
        item["situation"]["hops"][1]["scope"] = ["documents:query"]
        with self.assertRaises(EvaluationError):
            self.run_vector(item)

    def test_invalid_hop_outranks_unavailable_input(self) -> None:
        item = case("widened_delegation_hop")
        del item["situation"]["resolved_agents"]["agtp:sha256:agent-c"]
        result = self.run_vector(item)
        self.assertEqual(result["verification"], "invalid")
        self.assertEqual(result["agtp_reason"], "scope-exceeds-parent")

    def test_last_hop_must_match_request_agent(self) -> None:
        item = case("unreachable_delegation_registry")
        item["situation"]["resolved_agents"]["agtp:sha256:agent-b"] = {
            "lifecycle": "Active",
            "agent_public_key": "ed25519:agent-b-key",
        }
        item["situation"]["request_agent_id"] = "agtp:sha256:agent-z"
        result = self.run_vector(item)
        self.assertEqual(result["agtp_reason"], "link-unverifiable")

    def test_scope_inside_grant_is_rejected_as_a_vector(self) -> None:
        item = case("claimed_scope_beyond_grant")
        item["situation"]["claimed_scope"] = ["documents:query"]
        item["situation"]["endpoint_required_scopes"] = ["documents:query"]
        with self.assertRaises(EvaluationError):
            self.run_vector(item)

    def test_action_digest_omits_absent_members_and_covers_payload(self) -> None:
        request = load("cases.json")["cases"][-1]["situation"]["authorized_request"]
        changed = dict(request, payload={"tool": "other.tool", "arguments": {"message": "hello"}})
        self.assertNotEqual(agtp_action_digest(request), agtp_action_digest(changed))
        trimmed = {key: value for key, value in request.items() if key != "path"}
        self.assertEqual(agtp_action_digest(trimmed), agtp_action_digest(dict(trimmed, path=None)))

    def test_task_substitution_requires_unchanged_digest(self) -> None:
        item = case("a2a_task_substitution")
        item["situation"]["observed_request"] = case("a2a_mcp_action_swap")["situation"]["observed_request"]
        with self.assertRaises(EvaluationError):
            self.run_vector(item)


if __name__ == "__main__":
    unittest.main()
