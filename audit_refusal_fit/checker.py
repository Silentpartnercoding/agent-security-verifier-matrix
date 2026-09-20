"""Check signed records against a separately supplied attempt commitment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .crypto import verify_ed25519
from .encoding import canonical_json, sha256_identifier


def _expected_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    attempts = manifest.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    expected: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        if not isinstance(attempt, dict) or not isinstance(attempt.get("attempt_id"), str):
            return None
        attempt_id = attempt["attempt_id"]
        if attempt_id in expected:
            return None
        expected[attempt_id] = attempt
    return expected


def check_records(
    manifest: dict[str, Any], records: list[dict[str, Any]], public_key: Path
) -> dict[str, Any]:
    expected = _expected_by_id(manifest)
    if expected is None:
        return {
            "outcome": "unverifiable",
            "decisive_check": "missing-external-commitment",
            "missing_attempt_ids": [],
            "unexpected_attempt_ids": [],
            "signature_verification_passed": None,
            "chain_verification_passed": None,
            "record_semantics_passed": None,
            "diagnostics": [
                "No valid external attempt manifest exists, so absent records cannot be distinguished from absent attempts."
            ],
        }

    diagnostics: list[str] = []
    expected_positions = {
        attempt["attempt_id"]: position
        for position, attempt in enumerate(manifest["attempts"])
    }
    expected_key_id = manifest.get("key_id")
    seen: dict[str, dict[str, Any]] = {}
    signatures_valid = True
    chain_valid = True
    semantics_valid = True
    previous_record_sha256 = "genesis"

    for position, record in enumerate(records):
        if not isinstance(record, dict):
            semantics_valid = False
            diagnostics.append(f"record {position} is not an object")
            continue
        attempt_id = record.get("attempt_id")
        if not isinstance(attempt_id, str):
            semantics_valid = False
            diagnostics.append(f"record {position} has no string attempt_id")
            continue
        if attempt_id in seen:
            semantics_valid = False
            diagnostics.append(f"duplicate record for {attempt_id}")
        seen[attempt_id] = record

        signature = record.get("signature")
        unsigned = dict(record)
        unsigned.pop("signature", None)
        if not isinstance(signature, str) or not verify_ed25519(
            canonical_json(unsigned), signature, public_key
        ):
            signatures_valid = False
            diagnostics.append(f"signature failed for {attempt_id}")

        if record.get("previous_record_sha256") != previous_record_sha256:
            chain_valid = False
            diagnostics.append(f"chain predecessor failed for {attempt_id}")
        previous_record_sha256 = sha256_identifier(record)

        expected_attempt = expected.get(attempt_id)
        if expected_attempt is None:
            semantics_valid = False
            diagnostics.append(f"unexpected record for {attempt_id}")
            continue
        if record.get("record_kind") != expected_attempt.get("expected_record_kind"):
            semantics_valid = False
            diagnostics.append(f"record kind differs for {attempt_id}")
        if record.get("outcome") != expected_attempt.get("expected_outcome"):
            semantics_valid = False
            diagnostics.append(f"outcome differs for {attempt_id}")
        if record.get("sequence") != expected_positions[attempt_id]:
            semantics_valid = False
            diagnostics.append(f"sequence differs for {attempt_id}")
        if record.get("key_id") != expected_key_id:
            semantics_valid = False
            diagnostics.append(f"key id differs for {attempt_id}")
        for field in ("tool", "reason"):
            if record.get(field) != expected_attempt.get(field):
                semantics_valid = False
                diagnostics.append(f"{field} differs for {attempt_id}")
        if expected_attempt.get("expected_record_kind") == "decision":
            expected_arguments_sha256 = sha256_identifier(expected_attempt.get("arguments"))
            if record.get("arguments_sha256") != expected_arguments_sha256:
                semantics_valid = False
                diagnostics.append(f"arguments commitment differs for {attempt_id}")
            if "refusal_descriptor_sha256" in record:
                semantics_valid = False
                diagnostics.append(f"decision carries a refusal descriptor for {attempt_id}")
        else:
            expected_descriptor_sha256 = sha256_identifier(
                expected_attempt.get("unencodable_arguments")
            )
            if record.get("refusal_descriptor_sha256") != expected_descriptor_sha256:
                semantics_valid = False
                diagnostics.append(f"refusal descriptor differs for {attempt_id}")
            if "arguments_sha256" in record:
                semantics_valid = False
                diagnostics.append(f"refusal carries an arguments digest for {attempt_id}")

    missing = sorted(set(expected) - set(seen))
    unexpected = sorted(set(seen) - set(expected))
    if missing:
        diagnostics.append("missing required records: " + ", ".join(missing))

    verified = (
        not missing
        and not unexpected
        and signatures_valid
        and chain_valid
        and semantics_valid
    )
    decisive_check = "all-required-records-present"
    if missing:
        decisive_check = "external-attempt-commitment"
    elif not signatures_valid:
        decisive_check = "record-signature"
    elif not chain_valid:
        decisive_check = "record-chain"
    elif not semantics_valid or unexpected:
        decisive_check = "record-semantics"
    return {
        "outcome": "verified" if verified else "violation",
        "decisive_check": decisive_check,
        "missing_attempt_ids": missing,
        "unexpected_attempt_ids": unexpected,
        "signature_verification_passed": signatures_valid,
        "chain_verification_passed": chain_valid,
        "record_semantics_passed": semantics_valid and not unexpected,
        "diagnostics": diagnostics,
    }
