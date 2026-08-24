"""Data-driven negative-vector evaluator shared by protocol mappings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPORT_DISPOSITIONS = {"EXACT", "DECLARED-GAP", "AMBIGUOUS", "UNREPRESENTED"}
ROW_OUTCOMES = {"satisfied", "unsatisfied", "indeterminate", "unsupported"}
WARRANT_OUTCOMES = {"verified", "rejected", "unverifiable"}
CORE_CLAIM_CLASSES = [
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
    if labels != CORE_CLAIM_CLASSES:
        raise EvaluationError("matrix changed the frozen core claim classes or their order")
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


VECTOR_EVALUATORS = {
    "presenter-substitution": _presenter_substitution,
    "same-control-verifier": _same_control_verifier,
    "stale-unverifiable-evidence": _stale_unverifiable_evidence,
    "cross-protocol-action-swap": _cross_protocol_action_swap,
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
    result["conforms_to_frozen_expectation"] = True
    return result


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
    return {
        "experiment": matrix["experiment"],
        "evaluator": "verifier_matrix",
        "evaluator_version": "1.0.0",
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
