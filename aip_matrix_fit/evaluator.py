"""Evaluate the corrected AIP x verifier-matrix cases.

This module does not implement AIP cryptography. Every negative vector keeps
the surrounding AIP chain valid and asks only what the pinned draft permits a
consumer to conclude after that adjacent success.

The exact-action comparison reuses the canonical JSON digest behavior from the
pinned Border crossing receipt. The evidence case preserves Minority Prophet's
three-valued verified/rejected/unverifiable distinction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "matrix.json"
CASES_PATH = ROOT / "cases.json"
SOURCES_PATH = ROOT / "sources.json"

REPORT_DISPOSITIONS = frozenset(
    {"EXACT", "DECLARED-GAP", "AMBIGUOUS", "UNREPRESENTED"}
)
ROW_OUTCOMES = frozenset(
    {
        "satisfied",
        "unsatisfied",
        "indeterminate",
        "unsupported",
        "not-evaluated",
        "not-applicable",
    }
)
WARRANT_OUTCOMES = frozenset({"verified", "rejected", "unverifiable"})


class EvaluationError(ValueError):
    """The frozen artifact is incomplete, inconsistent, or silently widened."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationError(f"{path.name} must contain one JSON object")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_argument_digest(arguments: Any) -> str:
    """Match Border's pinned canonical argument digest behavior."""
    encoded = json.dumps(
        arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_pinned_bytes(data: bytes, expected_sha256: str, expected_bytes: int | None) -> bool:
    """Verify source bytes without fetching or assigning authority to a URL."""
    if expected_bytes is not None and len(data) != expected_bytes:
        return False
    return hashlib.sha256(data).hexdigest() == expected_sha256


def verify_source_files(source_files: dict[str, Path] | None = None) -> dict[str, Any]:
    """Verify locally supplied source bytes against every pin in sources.json.

    No network retrieval is implicit. With no supplied files the result is
    explicitly ``skipped``. Once any file is supplied, every pinned source must
    be supplied and valid for the aggregate result to be ``passed``.
    """
    sources_document = _load(SOURCES_PATH)
    pins = sources_document.get("sources")
    if not isinstance(pins, list):
        raise EvaluationError("sources must be a list")
    supplied = source_files or {}
    known_ids = {pin.get("id") for pin in pins}
    unknown_ids = sorted(set(supplied) - known_ids)
    if unknown_ids:
        raise EvaluationError(f"unknown source ids: {', '.join(unknown_ids)}")

    results: list[dict[str, Any]] = []
    for pin in pins:
        source_id = pin.get("id")
        if not isinstance(source_id, str):
            raise EvaluationError("every source pin must have a string id")
        path = supplied.get(source_id)
        if path is None:
            results.append(
                {
                    "source_id": source_id,
                    "status": "skipped",
                    "reason": "local source bytes not supplied",
                }
            )
            continue
        try:
            data = path.read_bytes()
        except OSError:
            results.append(
                {
                    "source_id": source_id,
                    "status": "failed",
                    "reason": "could not read local source bytes",
                }
            )
            continue
        passed = verify_pinned_bytes(data, pin["sha256"], pin.get("bytes"))
        results.append(
            {
                "source_id": source_id,
                "status": "passed" if passed else "failed",
                "observed_bytes": len(data),
                "observed_sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    if not supplied:
        aggregate = "skipped"
    elif all(item["status"] == "passed" for item in results):
        aggregate = "passed"
    else:
        aggregate = "failed"
    return {
        "status": aggregate,
        "policy": "all pinned sources must be locally supplied and valid once verification is requested",
        "results": results,
    }


def _row_index(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        raise EvaluationError("matrix rows must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise EvaluationError("every matrix row must have a string id")
        if row["id"] in indexed:
            raise EvaluationError(f"duplicate matrix row {row['id']!r}")
        if row.get("result") not in REPORT_DISPOSITIONS:
            raise EvaluationError(f"invalid disposition for row {row['id']!r}")
        indexed[row["id"]] = row
    return indexed


def _base_result(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    situation = case.get("situation")
    if not isinstance(situation, dict) or situation.get("aip_chain_valid") is not True:
        raise EvaluationError(
            f"{case.get('id', '<unknown>')}: hostile vector must preserve AIP chain validity"
        )
    return {
        "case_id": case["id"],
        "title": case["title"],
        "matrix_row": row["id"],
        "mapping_result": row["result"],
        "expected_row_outcome": None,
        "permitted_conclusion": case["expected_permitted_conclusion"],
        "adjacent_successes": ["aip_chain_valid"],
        "non_claims": list(case.get("prohibited_conclusions", [])),
    }


def _wrong_presenter(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if situation["leaf_subject"] == situation["live_presenter"]:
        raise EvaluationError("wrong_presenter does not contain a presenter substitution")
    if situation["external_proof_of_possession_present"]:
        raise EvaluationError("wrong_presenter unexpectedly supplies an external PoP result")
    result["expected_row_outcome"] = "unsupported"
    result["diagnostic"] = (
        "AIP draft-01 deliberately has no presenter proof-of-possession check; "
        "the valid bearer chain cannot be promoted into live-presenter authentication."
    )
    return result


def _same_control_verifier(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if not situation["completion_signature_valid"] or not situation["attestation_signature_valid"]:
        raise EvaluationError("same_control_verifier requires valid surrounding signatures")
    if situation["executor_control_domain"] != situation["verifier_control_domain"]:
        raise EvaluationError("same_control_verifier does not share a control domain")
    result["expected_row_outcome"] = "indeterminate"
    result["adjacent_successes"].extend(
        ["completion_signature_valid", "attestation_signature_valid"]
    )
    result["diagnostic"] = (
        "The signer is authenticated, but draft-01 supplies no organizational "
        "control-domain independence rule or constrained result."
    )
    return result


def _stale_unverifiable_completion(
    case: dict[str, Any], row: dict[str, Any]
) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if not situation["completion_signature_valid"] or not situation["result_hash_valid"]:
        raise EvaluationError("completion vector requires an intact completion artifact")
    evidence = situation.get("underlying_evidence")
    if not isinstance(evidence, dict):
        raise EvaluationError("completion vector has no underlying evidence state")
    warrant_outcome = evidence.get("verify_outcome")
    if warrant_outcome not in WARRANT_OUTCOMES:
        raise EvaluationError("completion vector has an invalid warrant outcome")
    if warrant_outcome != "unverifiable":
        raise EvaluationError("frozen completion vector must preserve unverifiable")
    if evidence.get("freshness_within_relying_bound") is not False:
        raise EvaluationError("frozen completion evidence is not stale")
    result["expected_row_outcome"] = "indeterminate"
    result["warrant_outcome"] = warrant_outcome
    result["adjacent_successes"].extend(
        ["completion_signature_valid", "result_hash_valid"]
    )
    result["diagnostic"] = (
        "The artifact is intact, but unreachable or stale evidence is unverifiable, "
        "not rejected; no adjacent signature success repairs that missing appraisal."
    )
    return result


def _a2a_mcp_action_swap(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(case, row)
    situation = case["situation"]
    if situation["aip_simple_tool"] != situation["observed_mcp_tool"]:
        raise EvaluationError(
            "action-swap specialization must keep the AIP-scoped tool unchanged"
        )
    authorized_digest = canonical_argument_digest(situation["authorized_arguments"])
    observed_digest = canonical_argument_digest(situation["observed_arguments"])
    if authorized_digest == observed_digest:
        raise EvaluationError("action-swap arguments do not differ")
    if situation["aip_exact_argument_digest_present"]:
        raise EvaluationError("frozen AIP profile unexpectedly carries an argument digest")
    if not situation["border_exact_argument_digest_present"]:
        raise EvaluationError("Border reference comparison is not enabled")
    result["expected_row_outcome"] = "unsupported"
    result["border_reference_outcome"] = "unsatisfied"
    result["authorized_argument_digest"] = authorized_digest
    result["observed_argument_digest"] = observed_digest
    result["adjacent_successes"].append("aip_tool_scope_satisfied")
    result["diagnostic"] = (
        "The AIP Simple-profile tool check succeeds, while the reused Border "
        "argument-digest comparison detects a different payload. Tool scope is "
        "not promoted into exact-action authorization."
    )
    return result


EVALUATORS = {
    "wrong_presenter": _wrong_presenter,
    "same_control_verifier": _same_control_verifier,
    "stale_unverifiable_completion": _stale_unverifiable_completion,
    "a2a_mcp_action_swap": _a2a_mcp_action_swap,
}


def evaluate_case(case: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    case_id = case.get("id")
    if case_id not in EVALUATORS:
        raise EvaluationError(f"no evaluator for frozen case {case_id!r}")
    row_id = case.get("matrix_row")
    if row_id not in rows:
        raise EvaluationError(f"case {case_id!r} references missing row {row_id!r}")
    result = EVALUATORS[case_id](case, rows[row_id])
    if result["mapping_result"] != case.get("expected_mapping_result"):
        raise EvaluationError(f"{case_id}: mapping result differs from frozen expectation")
    if result["expected_row_outcome"] not in ROW_OUTCOMES:
        raise EvaluationError(f"{case_id}: invalid Principal Binding row outcome")
    if result["expected_row_outcome"] != case.get("expected_row_outcome"):
        raise EvaluationError(f"{case_id}: row outcome differs from frozen expectation")
    if "expected_warrant_outcome" in case and result.get("warrant_outcome") != case[
        "expected_warrant_outcome"
    ]:
        raise EvaluationError(f"{case_id}: warrant outcome was collapsed or changed")
    if "expected_border_reference_outcome" in case and result.get(
        "border_reference_outcome"
    ) != case["expected_border_reference_outcome"]:
        raise EvaluationError(f"{case_id}: Border reference outcome changed")
    result["conforms_to_frozen_expectation"] = True
    return result


def evaluate_all(source_files: dict[str, Path] | None = None) -> dict[str, Any]:
    matrix = _load(MATRIX_PATH)
    cases_document = _load(CASES_PATH)
    sources = _load(SOURCES_PATH)
    rows = _row_index(matrix)
    cases = cases_document.get("cases")
    if not isinstance(cases, list):
        raise EvaluationError("cases must be a list")
    results = [evaluate_case(case, rows) for case in cases]
    return {
        "experiment": "AIP-MATRIX-FIT-002",
        "evaluator_version": "0.2.0",
        "source_protocol": matrix["source_protocol"],
        "evaluation_vocabulary": matrix["evaluation_vocabulary"],
        "matrix_sha256": _file_sha256(MATRIX_PATH),
        "cases_sha256": _file_sha256(CASES_PATH),
        "sources_sha256": _file_sha256(SOURCES_PATH),
        "source_count": len(sources.get("sources", [])),
        "source_byte_verification": verify_source_files(source_files),
        "case_count": len(results),
        "all_conform": all(item["conforms_to_frozen_expectation"] for item in results),
        "results": results,
    }
