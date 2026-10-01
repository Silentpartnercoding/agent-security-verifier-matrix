"""Count declared lineage roots without promoting signatures to independence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .crypto import verify_ed25519
from .encoding import canonical_json, sha256_identifier


def _result(
    *,
    outcome: str,
    distinct_record_count: int,
    root_record_ids: list[str],
    root_basis_ids: list[str],
    signatures_valid: bool,
    chain_valid: bool,
    diagnostics: list[str],
) -> dict[str, Any]:
    counted = outcome == "counted"
    root_count = len(root_basis_ids) if counted else None
    return {
        "outcome": outcome,
        "distinct_record_count": distinct_record_count,
        "declared_root_count": root_count,
        "collapsed_descendant_count": (
            distinct_record_count - root_count if root_count is not None else None
        ),
        "root_record_ids": root_record_ids if counted else [],
        "root_basis_ids": root_basis_ids if counted else [],
        "signature_verification_passed": signatures_valid,
        "chain_verification_passed": chain_valid,
        "independence_state": "not-established",
        "diagnostics": diagnostics,
    }


def count_declared_roots(
    records: list[dict[str, Any]], public_key: Path
) -> dict[str, Any]:
    if not records:
        return _result(
            outcome="unverifiable",
            distinct_record_count=0,
            root_record_ids=[],
            root_basis_ids=[],
            signatures_valid=True,
            chain_valid=True,
            diagnostics=["no evidence records were supplied"],
        )

    diagnostics: list[str] = []
    signatures_valid = True
    chain_valid = True
    semantics_valid = True
    previous_record_sha256 = "genesis"
    by_id: dict[str, dict[str, Any]] = {}

    for position, record in enumerate(records):
        if not isinstance(record, dict):
            semantics_valid = False
            diagnostics.append(f"record {position} is not an object")
            continue
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            semantics_valid = False
            diagnostics.append(f"record {position} has no non-empty record_id")
            continue
        if record_id in by_id:
            semantics_valid = False
            diagnostics.append(f"duplicate record id {record_id}")
        by_id[record_id] = record

        signature = record.get("signature")
        unsigned = dict(record)
        unsigned.pop("signature", None)
        if not isinstance(signature, str) or not verify_ed25519(
            canonical_json(unsigned), signature, public_key
        ):
            signatures_valid = False
            diagnostics.append(f"signature failed for {record_id}")

        if record.get("previous_record_sha256") != previous_record_sha256:
            chain_valid = False
            diagnostics.append(f"chain predecessor failed for {record_id}")
        previous_record_sha256 = sha256_identifier(record)

        if record.get("evidence_profile") != "declared-evidence-lineage-v1":
            semantics_valid = False
            diagnostics.append(f"unsupported evidence profile for {record_id}")
        if record.get("sequence") != position:
            semantics_valid = False
            diagnostics.append(f"sequence differs for {record_id}")
        if not isinstance(record.get("claim"), str) or not record.get("claim"):
            semantics_valid = False
            diagnostics.append(f"claim missing for {record_id}")
        if not isinstance(record.get("side"), str) or not record.get("side"):
            semantics_valid = False
            diagnostics.append(f"side missing for {record_id}")

    if not signatures_valid or not chain_valid or not semantics_valid:
        return _result(
            outcome="violation",
            distinct_record_count=len(by_id),
            root_record_ids=[],
            root_basis_ids=[],
            signatures_valid=signatures_valid,
            chain_valid=chain_valid,
            diagnostics=diagnostics,
        )

    claims = {record["claim"] for record in by_id.values()}
    if len(claims) != 1:
        diagnostics.append("multiple claims")
        return _result(
            outcome="unverifiable",
            distinct_record_count=len(by_id),
            root_record_ids=[],
            root_basis_ids=[],
            signatures_valid=True,
            chain_valid=True,
            diagnostics=diagnostics,
        )

    resolved_roots: dict[str, str] = {}
    lineage_invalid = False
    for start_id in by_id:
        current_id = start_id
        path: set[str] = set()
        while True:
            if current_id in resolved_roots:
                resolved_roots[start_id] = resolved_roots[current_id]
                break
            if current_id in path:
                diagnostics.append(f"lineage cycle reached from {start_id}")
                lineage_invalid = True
                break
            path.add(current_id)
            current = by_id[current_id]
            parent_id = current.get("parent_record_id")
            if parent_id is None:
                if (
                    current.get("root_basis_state") != "declared"
                    or not isinstance(current.get("root_basis_id"), str)
                    or not current.get("root_basis_id")
                ):
                    diagnostics.append(
                        f"record {current_id} has no parent and no declared root basis"
                    )
                    lineage_invalid = True
                    break
                root_id = current_id
                for path_id in path:
                    resolved_roots[path_id] = root_id
                break
            if not isinstance(parent_id, str) or not parent_id:
                diagnostics.append(f"invalid parent on {current_id}")
                lineage_invalid = True
                break
            if parent_id not in by_id:
                diagnostics.append(f"missing parent {parent_id}")
                lineage_invalid = True
                break
            parent = by_id[parent_id]
            if parent.get("claim") != current.get("claim") or parent.get(
                "side"
            ) != current.get("side"):
                diagnostics.append(f"claim or side changes across parent edge for {current_id}")
                lineage_invalid = True
                break
            current_id = parent_id

    if lineage_invalid or len(resolved_roots) != len(by_id):
        return _result(
            outcome="unverifiable",
            distinct_record_count=len(by_id),
            root_record_ids=[],
            root_basis_ids=[],
            signatures_valid=True,
            chain_valid=True,
            diagnostics=diagnostics,
        )

    root_record_ids = sorted(set(resolved_roots.values()))
    root_basis_ids = sorted(
        {str(by_id[root_id]["root_basis_id"]) for root_id in root_record_ids}
    )
    return _result(
        outcome="counted",
        distinct_record_count=len(by_id),
        root_record_ids=root_record_ids,
        root_basis_ids=root_basis_ids,
        signatures_valid=True,
        chain_valid=True,
        diagnostics=diagnostics,
    )
