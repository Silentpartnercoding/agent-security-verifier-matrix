"""Emit signed evidence records with explicit declared lineage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .crypto import sign_ed25519
from .encoding import canonical_json, sha256_identifier


class EvidenceEmissionError(ValueError):
    """A declared-lineage manifest cannot produce an honest test record."""


def emit_evidence_records(
    manifest: dict[str, Any], private_key: Path
) -> list[dict[str, Any]]:
    specifications = manifest.get("records")
    key_id = manifest.get("key_id")
    if not isinstance(specifications, list) or not specifications:
        raise EvidenceEmissionError("evidence manifest needs a non-empty records list")
    if not isinstance(key_id, str) or not key_id:
        raise EvidenceEmissionError("evidence manifest must identify its test key")

    emitted: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    previous_record_sha256 = "genesis"
    for sequence, specification in enumerate(specifications):
        if not isinstance(specification, dict):
            raise EvidenceEmissionError("every evidence record must be an object")
        record_id = specification.get("record_id")
        claim = specification.get("claim")
        side = specification.get("side")
        if not all(
            isinstance(value, str) and value for value in (record_id, claim, side)
        ):
            raise EvidenceEmissionError(
                "every evidence record needs a non-empty record_id, claim, and side"
            )
        if record_id in seen_ids:
            raise EvidenceEmissionError(f"duplicate evidence record id {record_id}")
        seen_ids.add(record_id)

        record: dict[str, Any] = {
            "evidence_profile": "declared-evidence-lineage-v1",
            "record_id": record_id,
            "sequence": sequence,
            "claim": claim,
            "side": side,
            "previous_record_sha256": previous_record_sha256,
            "key_id": key_id,
            "signature_profile": "ed25519-test-vector-v1",
        }
        for optional_field in (
            "parent_record_id",
            "root_basis_state",
            "root_basis_id",
        ):
            if optional_field in specification:
                value = specification[optional_field]
                if not isinstance(value, str) or not value:
                    raise EvidenceEmissionError(
                        f"{record_id}: {optional_field} must be a non-empty string"
                    )
                record[optional_field] = value

        record["signature"] = sign_ed25519(canonical_json(record), private_key)
        emitted.append(record)
        previous_record_sha256 = sha256_identifier(record)
    return emitted
