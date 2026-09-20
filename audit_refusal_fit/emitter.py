"""Emit signed decision and refusal records from a frozen attempt manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .crypto import sign_ed25519
from .encoding import canonical_json, sha256_identifier


class EmissionError(ValueError):
    """The frozen attempt manifest cannot produce an honest record."""


def _unsigned_record(
    attempt: dict[str, Any], sequence: int, previous_record_sha256: str, key_id: str
) -> dict[str, Any]:
    attempt_id = attempt.get("attempt_id")
    tool = attempt.get("tool")
    record_kind = attempt.get("expected_record_kind")
    outcome = attempt.get("expected_outcome")
    reason = attempt.get("reason")
    if not all(isinstance(value, str) and value for value in [attempt_id, tool, record_kind, outcome, reason]):
        raise EmissionError("every attempt needs non-empty identity and expected record fields")
    if record_kind not in {"decision", "refusal"}:
        raise EmissionError(f"{attempt_id}: unsupported record kind {record_kind!r}")

    record: dict[str, Any] = {
        "record_profile": "audit-refusal-record-v1",
        "attempt_id": attempt_id,
        "sequence": sequence,
        "tool": tool,
        "record_kind": record_kind,
        "outcome": outcome,
        "reason": reason,
        "previous_record_sha256": previous_record_sha256,
        "key_id": key_id,
        "signature_profile": "ed25519-test-vector-v1",
    }
    if record_kind == "decision":
        if "arguments" not in attempt or "unencodable_arguments" in attempt:
            raise EmissionError(f"{attempt_id}: decision record needs canonical arguments")
        record["arguments_sha256"] = sha256_identifier(attempt["arguments"])
    else:
        descriptor = attempt.get("unencodable_arguments")
        if not isinstance(descriptor, dict) or "arguments" in attempt:
            raise EmissionError(
                f"{attempt_id}: refusal record needs a separate unencodable descriptor"
            )
        record["refusal_descriptor_sha256"] = sha256_identifier(descriptor)
    return record


def emit_records(manifest: dict[str, Any], private_key: Path) -> list[dict[str, Any]]:
    attempts = manifest.get("attempts")
    key_id = manifest.get("key_id")
    if not isinstance(attempts, list) or not attempts:
        raise EmissionError("attempt manifest must contain a non-empty attempts list")
    if not isinstance(key_id, str) or not key_id:
        raise EmissionError("attempt manifest must identify its test-vector signing key")

    records: list[dict[str, Any]] = []
    previous_record_sha256 = "genesis"
    for sequence, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise EmissionError("every attempt must be an object")
        record = _unsigned_record(attempt, sequence, previous_record_sha256, key_id)
        record["signature"] = sign_ed25519(canonical_json(record), private_key)
        records.append(record)
        previous_record_sha256 = sha256_identifier(record)
    return records
