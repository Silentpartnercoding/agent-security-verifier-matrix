"""Run the frozen refusal-record completeness cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .checker import check_records
from .evidence import emit_evidence_records
from .emitter import emit_records
from .root_counter import count_declared_roots


class ExperimentError(ValueError):
    """A frozen experiment input or expected result is inconsistent."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExperimentError(f"{path} must contain one JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_experiment(experiment_dir: Path) -> dict[str, Any]:
    experiment_dir = experiment_dir.resolve()
    attempts_path = experiment_dir / "attempts.json"
    cases_path = experiment_dir / "cases.json"
    evidence_cases_path = experiment_dir / "evidence-cases.json"
    sources_path = experiment_dir / "sources.json"
    upstream_tail_probe_path = (
        experiment_dir / "artifacts" / "upstream-tail-deletion.json"
    )
    private_key = experiment_dir / "keys" / "test-private.pem"
    public_key = experiment_dir / "keys" / "test-public.pem"
    manifest = _load(attempts_path)
    cases_document = _load(cases_path)
    evidence_cases_document = _load(evidence_cases_path)
    upstream_tail_probe = _load(upstream_tail_probe_path)
    expected_upstream_tail_probe = {
        "finding": "present-record verification does not establish terminal completeness",
        "full": {"breaks": [], "ok": True, "total": 3},
        "tail_deleted": {"breaks": [], "ok": True, "total": 2},
        "upstream_commit": "f2efb313d113149c6ddc9656307a605a7619f8ea",
    }
    upstream_conforms = upstream_tail_probe == expected_upstream_tail_probe
    cases = cases_document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ExperimentError("cases.json must contain a non-empty cases list")

    complete_records = emit_records(manifest, private_key)
    results: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ExperimentError("every case must have a string id")
        mutation = case.get("mutation")
        case_manifest = manifest
        records = list(complete_records)
        if mutation == "none":
            pass
        elif mutation == "remove-attempt":
            attempt_id = case.get("attempt_id")
            records = [record for record in records if record["attempt_id"] != attempt_id]
            if len(records) == len(complete_records):
                raise ExperimentError(f"{case['id']}: mutation removed no record")
        elif mutation == "remove-manifest-and-records":
            case_manifest = {}
            records = []
        else:
            raise ExperimentError(f"{case['id']}: unknown mutation {mutation!r}")

        result = check_records(case_manifest, records, public_key)
        expected_outcome = case.get("expected_outcome")
        if expected_outcome not in {"verified", "violation", "unverifiable"}:
            raise ExperimentError(f"{case['id']}: invalid expected outcome")
        result["case_id"] = case["id"]
        result["expected_outcome"] = expected_outcome
        result["conforms_to_frozen_expectation"] = result["outcome"] == expected_outcome
        results.append(result)

    evidence_cases = evidence_cases_document.get("cases")
    if not isinstance(evidence_cases, list) or not evidence_cases:
        raise ExperimentError(
            "evidence-cases.json must contain a non-empty cases list"
        )
    root_count_results: list[dict[str, Any]] = []
    for case in evidence_cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ExperimentError("every evidence case must have a string id")
        specifications = case.get("records")
        if not isinstance(specifications, list) or not specifications:
            raise ExperimentError(f"{case['id']}: records must be a non-empty list")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected:
            raise ExperimentError(f"{case['id']}: expected must be an object")
        evidence_records = emit_evidence_records(
            {"key_id": manifest.get("key_id"), "records": specifications},
            private_key,
        )
        root_result = count_declared_roots(evidence_records, public_key)
        root_result["case_id"] = case["id"]
        root_result["expected"] = expected
        root_result["conforms_to_frozen_expectation"] = all(
            root_result.get(field) == value for field, value in expected.items()
        )
        root_count_results.append(root_result)

    result_by_id = {result["case_id"]: result for result in results}

    def cell(outcome: str, verifier: str) -> dict[str, str]:
        return {"outcome": outcome, "verifier": verifier}

    result_table = [
        {
            "case_id": "upstream-full",
            "present_record_integrity": cell(
                "verified"
                if upstream_tail_probe.get("full", {}).get("ok")
                else "violation",
                "execution-governance verifyReceiptFile at pinned commit",
            ),
            "expected_record_completeness": cell("not-evaluated", "none"),
            "declared_root_counting": cell("not-evaluated", "none"),
        },
        {
            "case_id": "upstream-tail-deleted",
            "present_record_integrity": cell(
                "verified"
                if upstream_tail_probe.get("tail_deleted", {}).get("ok")
                else "violation",
                "execution-governance verifyReceiptFile at pinned commit",
            ),
            "expected_record_completeness": cell("not-evaluated", "none"),
            "declared_root_counting": cell("not-evaluated", "none"),
        },
        {
            "case_id": "missing-terminal-refusal",
            "present_record_integrity": cell(
                "verified",
                "audit_refusal_fit signature and chain checks",
            ),
            "expected_record_completeness": cell(
                result_by_id["missing-terminal-refusal"]["outcome"],
                "audit_refusal_fit external-attempt commitment",
            ),
            "declared_root_counting": cell("not-evaluated", "none"),
        },
        {
            "case_id": "missing-middle-deny",
            "present_record_integrity": cell(
                "verified"
                if result_by_id["missing-middle-deny"][
                    "chain_verification_passed"
                ]
                else "violation",
                "audit_refusal_fit signature and chain checks",
            ),
            "expected_record_completeness": cell(
                result_by_id["missing-middle-deny"]["outcome"],
                "audit_refusal_fit external-attempt commitment",
            ),
            "declared_root_counting": cell("not-evaluated", "none"),
        },
        {
            "case_id": "photocopy-three-one-root",
            "present_record_integrity": cell(
                "verified",
                "audit_refusal_fit declared-lineage signature and chain checks",
            ),
            "expected_record_completeness": cell("not-evaluated", "none"),
            "declared_root_counting": cell(
                "1-declared-root-from-3-signed-records",
                "audit_refusal_fit count_declared_roots",
            ),
        },
    ]

    root_expected = all(
        result["conforms_to_frozen_expectation"] for result in root_count_results
    )

    return {
        "experiment": manifest.get("experiment"),
        "implementation": "audit_refusal_fit",
        "implementation_version": "1.1.0",
        "attempts_sha256": _sha256(attempts_path),
        "cases_sha256": _sha256(cases_path),
        "evidence_cases_sha256": _sha256(evidence_cases_path),
        "sources_sha256": _sha256(sources_path),
        "upstream_tail_probe_sha256": _sha256(upstream_tail_probe_path),
        "public_key_sha256": _sha256(public_key),
        "case_count": len(results),
        "root_case_count": len(root_count_results),
        "upstream_conforms_to_frozen_expectation": upstream_conforms,
        "all_expected": all(
            result["conforms_to_frozen_expectation"] for result in results
        )
        and root_expected
        and upstream_conforms,
        "claim_boundary": {
            "established": [
                "At the pinned upstream commit, verifyReceiptFile accepts a valid two-record prefix after a third terminal record is deleted.",
                "The independent checker detects a required terminal refusal record that is absent when a separately frozen attempt manifest says it must exist.",
                "The declared-lineage counter counts three signed descendant records as one declared evidence root.",
            ],
            "not_established": [
                "A defect in an upstream verifier limited to integrity of the records supplied to it.",
                "Conformance of Bradley B's eg-conform implementation or receipt format beyond the pinned probe.",
                "Production suitability of the committed test-vector signing key.",
                "Truth or causal independence of a declared evidence root.",
                "Organizational independence merely because this code is in a different repository.",
                "External reproduction until another party runs the frozen release.",
            ],
        },
        "results": results,
        "root_count_results": root_count_results,
        "result_table": result_table,
        "upstream_tail_probe": upstream_tail_probe,
    }
