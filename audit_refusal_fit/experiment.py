"""Run the frozen refusal-record completeness cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .checker import check_records
from .emitter import emit_records


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
    sources_path = experiment_dir / "sources.json"
    private_key = experiment_dir / "keys" / "test-private.pem"
    public_key = experiment_dir / "keys" / "test-public.pem"
    manifest = _load(attempts_path)
    cases_document = _load(cases_path)
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

    return {
        "experiment": manifest.get("experiment"),
        "implementation": "audit_refusal_fit",
        "implementation_version": "1.0.0",
        "attempts_sha256": _sha256(attempts_path),
        "cases_sha256": _sha256(cases_path),
        "sources_sha256": _sha256(sources_path),
        "public_key_sha256": _sha256(public_key),
        "case_count": len(results),
        "all_expected": all(result["conforms_to_frozen_expectation"] for result in results),
        "claim_boundary": {
            "established": "The checker detects a required terminal refusal record that is absent when a separately frozen attempt manifest says it must exist.",
            "not_established": [
                "Conformance of Bradley B's eg-conform implementation or receipt format.",
                "Production suitability of the committed test-vector signing key.",
                "Organizational independence merely because this code is in a different repository.",
                "External reproduction until another party runs the frozen release.",
            ],
        },
        "results": results,
    }
