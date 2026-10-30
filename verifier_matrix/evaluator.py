"""Data-driven negative-vector evaluator shared by protocol mappings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPORT_DISPOSITIONS = {"EXACT", "DECLARED-GAP", "AMBIGUOUS", "UNREPRESENTED"}
ROW_OUTCOMES = {"satisfied", "unsatisfied", "indeterminate", "unsupported"}
WARRANT_OUTCOMES = {"verified", "rejected", "unverifiable"}
GROUPING_LABELS = [
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
# Backward-compatible name for the frozen AGTP-MATRIX-FIT-001 output.
CORE_CLAIM_CLASSES = GROUPING_LABELS


class EvaluationError(ValueError):
    """Raised when an experiment or vector violates its frozen contract."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvaluationError(f"{path} must contain a JSON object")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_argument_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def verify_pinned_bytes(data: bytes, expected_sha256: str, expected_bytes: int | None) -> bool:
    if expected_bytes is not None and len(data) != expected_bytes:
        return False
    return hashlib.sha256(data).hexdigest() == expected_sha256


def verify_source_files(
    sources_path: Path, source_files: dict[str, Path] | None = None
) -> dict[str, Any]:
    manifest = _load(sources_path)
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise EvaluationError("sources must be a list")
    supplied = source_files or {}
    declared_ids = {source.get("id") for source in sources}
    unknown_ids = sorted(set(supplied) - declared_ids)
    if unknown_ids:
        raise EvaluationError(f"unknown supplied source ids: {', '.join(unknown_ids)}")

    checks: list[dict[str, Any]] = []
    for source in sources:
        source_id = source.get("id")
        path = supplied.get(source_id)
        if path is None:
            checks.append({"id": source_id, "status": "skipped"})
            continue
        try:
            data = path.read_bytes()
        except OSError as error:
            checks.append({"id": source_id, "status": "failed", "error": str(error)})
            continue
        passed = verify_pinned_bytes(data, source["sha256"], source.get("bytes"))
        checks.append(
            {
                "id": source_id,
                "status": "passed" if passed else "failed",
                "observed_bytes": len(data),
                "observed_sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    statuses = {check["status"] for check in checks}
    if "failed" in statuses:
        status = "failed"
    elif checks and statuses == {"passed"}:
        status = "passed"
    else:
        status = "skipped"
    return {"status": status, "checks": checks}


def _matrix_rows(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        raise EvaluationError("matrix rows must be a list")
    labels = [row.get("label") for row in rows]
    if labels != GROUPING_LABELS:
        raise EvaluationError("matrix changed the frozen grouping labels or their order")
    required = {"id", "label", "claim", "carrier", "verifier", "binding", "failure", "result", "permitted_conclusion"}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not required.issubset(row):
            raise EvaluationError(f"incomplete matrix row: {row.get('id')!r}")
        if row["result"] not in REPORT_DISPOSITIONS:
            raise EvaluationError(f"invalid mapping disposition: {row['result']!r}")
        if row["id"] in indexed:
            raise EvaluationError(f"duplicate matrix row: {row['id']!r}")
        indexed[row["id"]] = row
    return indexed


def _base_result(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    if not case.get("prohibited_conclusions"):
        raise EvaluationError(f"{case.get('id')}: prohibited conclusions are required")
    return {
        "case_id": case["id"],
        "title": case["title"],
        "matrix_row": row["id"],
        "mapping_result": row["result"],
        "expected_row_outcome": case["expected_row_outcome"],
        "permitted_conclusion": case["expected_permitted_conclusion"],
        "prohibited_conclusions": case["prohibited_conclusions"],
        "adjacent_successes": [],
    }


def _presenter_substitution(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    required_successes = [
        "transport_server_authenticated",
        "identity_document_signature_valid",
        "registrar_trust_configured",
        "agent_id_header_matches_document",
    ]
    if not all(situation.get(field) is True for field in required_successes):
        raise EvaluationError("presenter vector requires intact adjacent identity checks")
    if situation.get("live_presenter") == situation.get("document_agent_id"):
        raise EvaluationError("presenter vector did not substitute the live presenter")
    if situation.get("presenter_proof_of_possession_present") is not False:
        raise EvaluationError("presenter vector unexpectedly contains proof of possession")
    if situation.get("agent_mutual_tls_present") is not False:
        raise EvaluationError("presenter vector unexpectedly contains agent mTLS")
    result["adjacent_successes"].extend(required_successes)
    result["diagnostic"] = (
        "The declared Agent-ID resolves to a valid signed document, but resolving a public "
        "document does not prove that the live sender controls an agent key."
    )
    return result


def _same_control_verifier(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if not situation.get("attribution_signature_valid"):
        raise EvaluationError("same-control vector requires a valid attribution signature")
    if not situation.get("attestation_evidence_signature_valid"):
        raise EvaluationError("same-control vector requires valid attestation evidence")
    if situation.get("executor_control_domain") != situation.get("verifier_control_domain"):
        raise EvaluationError("same-control vector does not preserve common control")
    if situation.get("control_domain_provenance_verified") is not True:
        raise EvaluationError("same-control vector requires verified control-domain facts")
    result["adjacent_successes"].extend(
        ["attribution_signature_valid", "attestation_evidence_signature_valid"]
    )
    result["diagnostic"] = (
        "Distinct signatures and a checkable execution environment do not establish that "
        "the verifier is outside the executor's organizational control."
    )
    return result


def _stale_unverifiable_evidence(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if not situation.get("attribution_signature_valid") or not situation.get("result_hash_valid"):
        raise EvaluationError("evidence vector requires an intact signed attribution record")
    evidence = situation.get("underlying_evidence")
    if not isinstance(evidence, dict):
        raise EvaluationError("evidence vector has no underlying evidence state")
    warrant_outcome = evidence.get("verify_outcome")
    if warrant_outcome not in WARRANT_OUTCOMES:
        raise EvaluationError("evidence vector has an invalid warrant outcome")
    if warrant_outcome != "unverifiable":
        raise EvaluationError("frozen evidence vector must remain unverifiable")
    if evidence.get("freshness_within_relying_bound") is not False:
        raise EvaluationError("frozen evidence vector is not stale")
    result["warrant_outcome"] = warrant_outcome
    result["adjacent_successes"].extend(
        ["attribution_signature_valid", "result_hash_valid"]
    )
    result["diagnostic"] = (
        "The attribution record is intact, but its optional evidence cannot be established "
        "as current or appraised; signature success does not repair that missing result."
    )
    return result


def _cross_protocol_action_swap(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    required_successes = [
        "identity_document_signature_valid",
        "governance_token_signature_valid",
        "governance_token_unexpired",
        "governance_token_agent_id_match",
        "authority_scope_satisfied",
    ]
    if not all(situation.get(field) is True for field in required_successes):
        raise EvaluationError("action vector requires intact adjacent authorization checks")
    if situation.get("governance_token_action") != situation.get("execute_action"):
        raise EvaluationError("action vector must preserve the high-level action label")
    authorized_digest = canonical_argument_digest(situation["authorized_arguments"])
    observed_digest = canonical_argument_digest(situation["observed_arguments"])
    if authorized_digest == observed_digest:
        raise EvaluationError("action vector arguments do not differ")
    if situation.get("canonical_payload_binding_defined") is not False:
        raise EvaluationError("action vector unexpectedly defines a canonical payload binding")
    if situation.get("border_exact_argument_digest_present") is not True:
        raise EvaluationError("Border reference comparison is not enabled")
    result["authorized_argument_digest"] = authorized_digest
    result["observed_argument_digest"] = observed_digest
    result["border_reference_outcome"] = "unsatisfied"
    result["adjacent_successes"].extend(required_successes)
    result["diagnostic"] = (
        "The identity, scope, token signature, expiry, agent identifier, and high-level "
        "action all pass while the reused Border digest detects a substituted payload."
    )
    return result


# Vector types below were added for AGTP-MATRIX-FIT-003. They model the
# draft-hood-independent-agtp-10 checks they name. Earlier experiments never
# reference them, so FIT-001 and FIT-002 output is unchanged.

REQUEST_SIGNATURE_COVERED_FIELDS = ["m", "p", "aid", "as", "dc", "bd", "iat", "n"]
DELEGATION_DEFAULT_MAX_DEPTH = 8


def _require_true(situation: dict[str, Any], fields: list[str], message: str) -> None:
    if not all(situation.get(field) is True for field in fields):
        raise EvaluationError(message)


def _sha256_hex(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def agtp_action_digest(request: dict[str, Any]) -> str:
    """AGTP-10 Section 7.3.8 action_digest over a modelled request.

    The digest input is {method, path, action, parameters, payload_type,
    payload_sha256} with absent members omitted. The payload digest is taken
    over the canonical JSON form of the payload in this model.
    """
    fields: dict[str, Any] = {}
    for name in ["method", "path", "action", "parameters", "payload_type"]:
        if name in request and request[name] is not None:
            fields[name] = request[name]
    if request.get("payload") is not None:
        fields["payload_sha256"] = _sha256_hex(request["payload"])
    return "sha256:" + _sha256_hex(fields)


def _signed_presenter_substitution(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    required_successes = [
        "transport_server_authenticated",
        "identity_document_signature_valid",
        "registrar_trust_configured",
        "agent_id_header_matches_document",
    ]
    _require_true(situation, required_successes, "presenter vector requires intact adjacent identity checks")
    if situation.get("live_presenter") == situation.get("document_agent_id"):
        raise EvaluationError("presenter vector did not substitute the live presenter")
    document_key = situation.get("document_agent_public_key")
    if not document_key:
        raise EvaluationError("signed presenter vector requires an agent_public_key in the document")
    signature = situation.get("request_signature")
    if not isinstance(signature, dict):
        raise EvaluationError("signed presenter vector has no Request-Signature")
    if signature.get("kid") != situation.get("document_agent_id"):
        raise EvaluationError("Request-Signature kid must name the declared Agent-ID")
    if signature.get("covered_fields") != REQUEST_SIGNATURE_COVERED_FIELDS:
        raise EvaluationError("Request-Signature covered fields differ from AGTP-10 Section 6.5.4")
    age = situation["verification_time"] - signature["iat"]
    if not 0 <= age <= situation.get("acceptance_window_seconds", 300):
        raise EvaluationError("signed presenter vector must keep iat inside the window")
    if signature.get("nonce_seen_in_window") is not False:
        raise EvaluationError("signed presenter vector must use an unseen nonce")
    if signature.get("signing_key") == document_key:
        raise EvaluationError("signed presenter vector did not substitute the signing key")
    result["adjacent_successes"].extend(
        required_successes + ["request_signature_iat_in_window", "request_signature_nonce_unseen"]
    )
    result["agtp_status"] = 401
    result["agtp_reason"] = "possession-unproven"
    result["dispatched"] = False
    result["diagnostic"] = (
        "The declared Agent-ID resolves to a valid signed document and the signature is "
        "fresh, but it verifies under a key other than the document's agent_public_key, "
        "so the request is refused before dispatch."
    )
    return result


def _delegation_hop_checks(situation: dict[str, Any]) -> dict[str, Any]:
    origin = situation["origin"]
    hops = situation["hops"]
    resolved = situation.get("resolved_agents", {})
    now = situation["verification_time"]
    max_depth = situation.get("max_depth", DELEGATION_DEFAULT_MAX_DEPTH)
    invalid: list[dict[str, Any]] = []
    indeterminate: list[dict[str, Any]] = []
    seen = {origin["agent_id"]}
    for index, hop in enumerate(hops):
        delegate = hop["delegate"]
        expected_parent = origin["agent_id"] if index == 0 else hops[index - 1]["delegate"]
        parent_scope = origin["document_scope"] if index == 0 else hops[index - 1]["scope"]
        # 1. Membership.
        state = resolved.get(delegate)
        if state is None:
            indeterminate.append({"hop": index, "missing_input": f"lifecycle:{delegate}"})
        elif state.get("lifecycle") != "Active":
            invalid.append({"hop": index, "reason": "member-inactive"})
        # 2. Parent re-verification.
        if hop["parent"] != expected_parent:
            invalid.append({"hop": index, "reason": "link-unverifiable"})
        else:
            parent_state = resolved.get(hop["parent"])
            if parent_state is None or not parent_state.get("agent_public_key"):
                indeterminate.append({"hop": index, "missing_input": f"identity-document:{hop['parent']}"})
            elif hop["signed_by_key"] != parent_state["agent_public_key"]:
                invalid.append({"hop": index, "reason": "link-unverifiable"})
        # 3. Attenuation: strict subset of the parent's scope.
        if not set(hop["scope"]) < set(parent_scope):
            invalid.append({"hop": index, "reason": "scope-exceeds-parent"})
        # 4. Freshness.
        previous_mint = None if index == 0 else hops[index - 1]["minted_at"]
        if hop["expires_at"] <= now or (previous_mint is not None and hop["minted_at"] < previous_mint):
            invalid.append({"hop": index, "reason": "chain-expired"})
        # 5. Depth and cycles.
        if index + 1 > max_depth:
            invalid.append({"hop": index, "reason": "depth-exceeded"})
        if delegate in seen:
            invalid.append({"hop": index, "reason": "cycle-detected"})
        seen.add(delegate)
    if hops and situation["request_agent_id"] != hops[-1]["delegate"]:
        invalid.append({"hop": len(hops) - 1, "reason": "link-unverifiable"})
    if invalid:
        first = invalid[0]
        return {
            "verification": "invalid",
            "agtp_status": 551,
            "evaluation": "refused",
            "agtp_reason": first["reason"],
            "failing_hop": first["hop"],
        }
    if indeterminate:
        first = indeterminate[0]
        return {
            "verification": "indeterminate",
            "agtp_status": 551,
            "evaluation": "incomplete",
            "agtp_reason": "input-unavailable",
            "missing_input": first["missing_input"],
            "failing_hop": first["hop"],
            "relying_party_default": "deny",
        }
    return {"verification": "valid", "effective_scope": sorted(hops[-1]["scope"]) if hops else sorted(origin["document_scope"])}


def _delegation_hop_verification(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    required_successes = ["identity_document_signature_valid", "request_signature_valid"]
    _require_true(situation, required_successes, "delegation vector requires intact adjacent identity checks")
    if not situation.get("hops"):
        raise EvaluationError("delegation vector requires at least one hop")
    outcome = _delegation_hop_checks(situation)
    if outcome["verification"] == "valid":
        raise EvaluationError("delegation vector must exercise a failing or indeterminate path")
    result["adjacent_successes"].extend(required_successes)
    result.update(outcome)
    result["dispatched"] = False
    if outcome["verification"] == "invalid":
        result["diagnostic"] = (
            "Every hop signature verifies, but the 9.3 checks find a hop that fails on inputs "
            "the verifier holds, so the request is refused with the failing hop named."
        )
    else:
        result["diagnostic"] = (
            "A check cannot run because an input is unavailable; the outcome is carried as "
            "incomplete, kept apart from a refusal, and denied by default."
        )
    return result


def _scope_claim_check(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    required_successes = ["identity_document_signature_valid", "request_signature_valid"]
    _require_true(situation, required_successes, "scope vector requires intact adjacent identity checks")
    granted = set(situation["document_scope"])
    claimed = situation.get("claimed_scope")
    required = set(situation.get("endpoint_required_scopes", []))
    if claimed is not None and not set(claimed) <= granted:
        status, reason = 455, "scope-claim-invalid"
    elif not required <= granted:
        status, reason = 455, "scope-exceeded"
    elif claimed is not None and not required <= set(claimed):
        status, reason = 262, None
        result["agtp_condition"] = "b"
    else:
        raise EvaluationError("scope vector must exercise a failing path")
    result["adjacent_successes"].extend(required_successes)
    result["agtp_status"] = status
    result["agtp_reason"] = reason
    result["dispatched"] = False
    result["diagnostic"] = (
        "455 when the request exceeds what the signed document grants; 262 when the missing "
        "scope is one the document grants and the agent could add to its claim."
    )
    return result


def _token_action_inputs(situation: dict[str, Any]) -> tuple[str, str, str]:
    required_successes = [
        "identity_document_signature_valid",
        "request_signature_valid",
        "governance_token_signature_valid",
        "governance_token_unexpired",
        "governance_token_unused",
        "governance_token_agent_id_match",
        "authority_scope_satisfied",
    ]
    _require_true(situation, required_successes, "token vector requires intact adjacent authorization checks")
    token_digest = situation["governance_token_action_digest"]
    if token_digest != agtp_action_digest(situation["authorized_request"]):
        raise EvaluationError("token action_digest must be computed from the authorized request")
    observed_digest = agtp_action_digest(situation["observed_request"])
    return token_digest, observed_digest, ",".join(required_successes)


def _token_bound_action_swap(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    token_digest, observed_digest, successes = _token_action_inputs(situation)
    if situation["authorized_request"].get("action") != situation["observed_request"].get("action"):
        raise EvaluationError("action vector must preserve the high-level action label")
    authorized_arguments = situation["authorized_request"]["payload"]
    observed_arguments = situation["observed_request"]["payload"]
    border_authorized = canonical_argument_digest(authorized_arguments)
    border_observed = canonical_argument_digest(observed_arguments)
    if border_authorized == border_observed:
        raise EvaluationError("action vector payloads do not differ")
    if token_digest == observed_digest:
        raise EvaluationError("action vector did not change the token-bound request shape")
    result["adjacent_successes"].extend(successes.split(","))
    result["token_action_digest"] = token_digest
    result["observed_action_digest"] = observed_digest
    result["authorized_argument_digest"] = border_authorized
    result["observed_argument_digest"] = border_observed
    result["agtp_status"] = 262
    result["agtp_reason"] = "token-action-mismatch"
    result["dispatched"] = False
    result["border_reference_outcome"] = "unsatisfied"
    result["diagnostic"] = (
        "Identity, signature, scope, and token checks pass, and the token's action_digest "
        "no longer matches the request as received, so the swap is refused before dispatch."
    )
    return result


def _token_bound_task_substitution(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    token_digest, observed_digest, successes = _token_action_inputs(situation)
    if situation.get("authorized_task_id") == situation.get("observed_task_id"):
        raise EvaluationError("task vector did not substitute the task identifier")
    if token_digest != observed_digest:
        raise EvaluationError("task vector must keep the token-bound request shape unchanged")
    if situation.get("border_task_binding_present") is not True:
        raise EvaluationError("Border reference comparison is not enabled")
    result["adjacent_successes"].extend(successes.split(","))
    result["adjacent_successes"].append("token_action_digest_match")
    result["token_action_digest"] = token_digest
    result["observed_action_digest"] = observed_digest
    result["agtp_task_binding"] = "outside-action-digest"
    result["border_reference_outcome"] = "unsatisfied"
    result["diagnostic"] = (
        "The action_digest matches because the originating task identifier sits outside "
        "its inputs; the Border reference binds the task and detects the substitution."
    )
    return result


VECTOR_EVALUATORS = {
    "presenter-substitution": _presenter_substitution,
    "same-control-verifier": _same_control_verifier,
    "stale-unverifiable-evidence": _stale_unverifiable_evidence,
    "cross-protocol-action-swap": _cross_protocol_action_swap,
    "signed-presenter-substitution": _signed_presenter_substitution,
    "delegation-hop-verification": _delegation_hop_verification,
    "scope-claim-check": _scope_claim_check,
    "token-bound-action-swap": _token_bound_action_swap,
    "token-bound-task-substitution": _token_bound_task_substitution,
}
EXPECTED_AGTP_FIELDS = {
    "expected_agtp_status": "agtp_status",
    "expected_agtp_reason": "agtp_reason",
    "expected_agtp_evaluation": "evaluation",
    "expected_failing_hop": "failing_hop",
}


def _evaluate_case(
    case: dict[str, Any], rows: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    vector_type = case.get("vector_type")
    evaluator = VECTOR_EVALUATORS.get(vector_type)
    if evaluator is None:
        raise EvaluationError(f"unsupported vector type: {vector_type!r}")
    row_id = case.get("matrix_row")
    if row_id not in rows:
        raise EvaluationError(f"{case.get('id')}: missing matrix row {row_id!r}")
    result = evaluator(case, rows[row_id])
    if result["mapping_result"] != case.get("expected_mapping_result"):
        raise EvaluationError(f"{case['id']}: mapping result differs from frozen expectation")
    if result["expected_row_outcome"] not in ROW_OUTCOMES:
        raise EvaluationError(f"{case['id']}: invalid Principal Binding row outcome")
    if "expected_warrant_outcome" in case and result.get("warrant_outcome") != case["expected_warrant_outcome"]:
        raise EvaluationError(f"{case['id']}: warrant outcome changed")
    if "expected_border_reference_outcome" in case and result.get("border_reference_outcome") != case["expected_border_reference_outcome"]:
        raise EvaluationError(f"{case['id']}: Border reference outcome changed")
    for expected_key, result_key in EXPECTED_AGTP_FIELDS.items():
        if expected_key in case and result.get(result_key) != case[expected_key]:
            raise EvaluationError(f"{case['id']}: {result_key} differs from frozen expectation")
    result["conforms_to_frozen_expectation"] = True
    return result


def _evaluator_version(matrix: dict[str, Any]) -> str:
    contract = matrix.get("evaluator_contract")
    if contract is not None:
        if contract != "1.2.0":
            raise EvaluationError(f"unsupported evaluator contract: {contract!r}")
        return "1.2.0"
    return "1.1.0" if "grouping_labels" in matrix else "1.0.0"


def evaluate_experiment(
    experiment_dir: Path, source_files: dict[str, Path] | None = None
) -> dict[str, Any]:
    experiment_dir = experiment_dir.resolve()
    matrix_path = experiment_dir / "matrix.json"
    cases_path = experiment_dir / "cases.json"
    sources_path = experiment_dir / "sources.json"
    matrix = _load(matrix_path)
    cases_document = _load(cases_path)
    rows = _matrix_rows(matrix)
    cases = cases_document.get("cases")
    if not isinstance(cases, list):
        raise EvaluationError("cases must be a list")
    results = [_evaluate_case(case, rows) for case in cases]
    report = {
        "experiment": matrix["experiment"],
        "evaluator": "verifier_matrix",
        "evaluator_version": _evaluator_version(matrix),
        "source_protocol": matrix["source_protocol"],
        "evaluation_vocabulary": matrix["evaluation_vocabulary"],
        "profile": matrix["profile"],
        "core_claim_classes": CORE_CLAIM_CLASSES,
        "claim_semantics_extended": False,
        "registry_envelope_changed": False,
        "matrix_sha256": _file_sha256(matrix_path),
        "cases_sha256": _file_sha256(cases_path),
        "sources_sha256": _file_sha256(sources_path),
        "source_byte_verification": verify_source_files(sources_path, source_files),
        "case_count": len(results),
        "all_conform": all(result["conforms_to_frozen_expectation"] for result in results),
        "results": results,
    }
    if "grouping_labels" in matrix:
        report.pop("core_claim_classes")
        report["grouping_labels"] = GROUPING_LABELS
        report["grouping_label_semantics"] = matrix["grouping_label_semantics"]
        report["claim_inventory_completeness"] = matrix["claim_inventory_completeness"]
        report["result_object_status"] = matrix["result_object_status"]
        report["permitted_conclusion_semantics"] = matrix[
            "permitted_conclusion_semantics"
        ]
    if matrix.get("evaluator_contract") == "1.2.0":
        report["companion_imports"] = matrix["companion_imports"]
        report["companions_excluded"] = matrix["companions_excluded"]
    return report
