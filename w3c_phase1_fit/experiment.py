"""Round-trip and evaluate the frozen immediate-input lineage pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    """The paired fixture is malformed or does not preserve its boundary."""


EXPECTED_COMPUTED = {
    "A": ("same-computed-a", "computed-a-is-valid"),
    "B": ("same-computed-b", "computed-b-is-valid"),
    "C": ("same-computed-c", "computed-c-is-valid"),
}
EXPECTED_TOPOLOGIES = {
    "one-observed-root": {"A": "R", "B": "R", "C": "R"},
    "three-observed-roots": {"A": "R1", "B": "R2", "C": "R3"},
}
EXPECTED_NODE_IDS = {
    "one-observed-root": {
        "A": "one:A",
        "B": "one:B",
        "C": "one:C",
        "R": "one:R",
    },
    "three-observed-roots": {
        "A": "three:A",
        "B": "three:B",
        "C": "three:C",
        "R1": "three:R1",
        "R2": "three:R2",
        "R3": "three:R3",
    },
}
EXPECTED_CASE_NAMESPACES = {
    "one": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/one/",
    "three": "https://silentpartnercoding.github.io/agent-security-verifier-matrix/case/three/",
}
DOCUMENT_FIELDS = {"@context", "experiment", "profile", "cases"}
CASE_FIELDS = {
    "id",
    "producer",
    "context",
    "observed_artifacts",
    "computed_artifacts",
    "expected_distinct_observed_root_count",
}
OBSERVED_FIELDS = {"@id", "label", "value"}
COMPUTED_FIELDS = {
    "@id",
    "label",
    "value",
    "proposition",
    "prov:wasDerivedFrom",
    "attestation",
}


def _canonical_roundtrip(value: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    decoded = json.loads(encoded)
    if decoded != value:
        raise FixtureError("canonical JSON round-trip changed the fixture")
    return decoded


def _expand_term(term: str, context: dict[str, Any]) -> str:
    if term.startswith("@"):
        return term
    if ":" in term:
        prefix, suffix = term.split(":", 1)
        base = context.get(prefix)
        if not isinstance(base, str) or not base.startswith(("http://", "https://")):
            raise FixtureError(f"undefined JSON-LD prefix {prefix}")
        return base + suffix
    definition = context.get(term)
    if isinstance(definition, str):
        return _expand_term(definition, context)
    if isinstance(definition, dict) and isinstance(definition.get("@id"), str):
        return _expand_term(definition["@id"], context)
    raise FixtureError(f"undefined JSON-LD term {term}")


def _validate_jsonld_terms(value: Any, context: dict[str, Any]) -> None:
    if isinstance(value, list):
        for item in value:
            _validate_jsonld_terms(item, context)
        return
    if not isinstance(value, dict):
        return
    for term, nested in value.items():
        if term == "@context":
            continue
        _expand_term(term, context)
        _validate_jsonld_terms(nested, context)


def _expand_identifier(identifier: str, context: dict[str, Any]) -> str:
    if identifier.startswith(("http://", "https://")):
        return identifier
    if ":" not in identifier:
        raise FixtureError(f"JSON-LD node id {identifier} is not case-scoped")
    return _expand_term(identifier, context)


def evaluate_pair(document: dict[str, Any]) -> dict[str, Any]:
    roundtripped = _canonical_roundtrip(document)
    if set(roundtripped) != DOCUMENT_FIELDS:
        raise FixtureError("fixture document shape differs from the frozen pair")
    if roundtripped.get("experiment") != "w3c-phase1-root-cardinality-001":
        raise FixtureError("unexpected experiment id")
    if roundtripped.get("profile") != "prov-o-entity-lineage-v1":
        raise FixtureError("unexpected fixture profile")
    jsonld_context = roundtripped.get("@context")
    if not isinstance(jsonld_context, dict):
        raise FixtureError("fixture must provide a JSON-LD context")
    if jsonld_context.get("prov") != "http://www.w3.org/ns/prov#":
        raise FixtureError("fixture must bind the PROV-O namespace")
    if not isinstance(jsonld_context.get("fixture"), str):
        raise FixtureError("fixture must bind its carrier-term namespace")
    if any(
        jsonld_context.get(prefix) != namespace
        for prefix, namespace in EXPECTED_CASE_NAMESPACES.items()
    ):
        raise FixtureError("fixture must bind distinct frozen case namespaces")
    _validate_jsonld_terms(roundtripped, jsonld_context)
    expanded_lineage_predicate = _expand_term(
        "prov:wasDerivedFrom", jsonld_context
    )
    cases = roundtripped.get("cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise FixtureError("fixture must contain exactly two paired cases")
    if any(
        not isinstance(case, dict) or set(case) - CASE_FIELDS
        for case in cases
    ):
        raise FixtureError("fixture case shape differs from the frozen pair")
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if set(case_ids) != set(EXPECTED_TOPOLOGIES) or len(case_ids) != 2:
        raise FixtureError("fixture must contain the frozen one-root and three-root cases")

    producer_contexts: set[tuple[str, str]] = set()
    for case in cases:
        producer = case.get("producer")
        context = case.get("context")
        if not isinstance(producer, str) or not producer or not isinstance(
            context, str
        ) or not context:
            raise FixtureError("each case must have a non-empty producer and context")
        producer_contexts.add((producer, context))
    if len(producer_contexts) != 1:
        raise FixtureError("paired cases must share one producer/context")

    case_results: list[dict[str, Any]] = []
    expanded_lineage_quads: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        observed = case.get("observed_artifacts")
        computed = case.get("computed_artifacts")
        if not isinstance(observed, list) or not isinstance(computed, list):
            raise FixtureError(f"{case['id']}: artifact lists are required")
        artifacts = observed + computed
        if not all(isinstance(artifact, dict) for artifact in artifacts):
            raise FixtureError(f"{case['id']}: every artifact must be an object")
        for artifact in observed:
            if "prov:wasDerivedFrom" in artifact:
                raise FixtureError(
                    f"{case['id']}: observed roots cannot carry lineage"
                )
            if set(artifact) != OBSERVED_FIELDS:
                raise FixtureError(f"{case['id']}: observed artifact shape differs")
        for artifact in computed:
            if "prov:wasDerivedFrom" not in artifact:
                artifact_id = artifact.get("@id", "computed artifact")
                raise FixtureError(
                    f"{case['id']}: {artifact_id} must have one immediate input"
                )
            if set(artifact) != COMPUTED_FIELDS:
                raise FixtureError(f"{case['id']}: computed artifact shape differs")
        artifact_ids = [artifact.get("@id") for artifact in artifacts]
        if not all(
            isinstance(artifact_id, str) and artifact_id
            for artifact_id in artifact_ids
        ):
            raise FixtureError(f"{case['id']}: every artifact must have a non-empty @id")
        if len(artifact_ids) != len(set(artifact_ids)):
            duplicate_id = next(
                artifact_id
                for artifact_id in artifact_ids
                if artifact_ids.count(artifact_id) > 1
            )
            raise FixtureError(f"{case['id']}: duplicate artifact id {duplicate_id}")
        computed_by_label = {artifact.get("label"): artifact for artifact in computed}
        if set(computed_by_label) != set(EXPECTED_COMPUTED) or len(computed) != 3:
            raise FixtureError(f"{case['id']}: must contain exactly A, B, and C")
        observed_by_label = {artifact.get("label"): artifact for artifact in observed}
        if None in observed_by_label or len(observed_by_label) != len(observed):
            raise FixtureError(f"{case['id']}: observed labels must be unique")
        actual_node_ids = {
            label: artifact["@id"]
            for label, artifact in {**observed_by_label, **computed_by_label}.items()
        }
        controls = {
            label: (artifact.get("value"), artifact.get("proposition"))
            for label, artifact in computed_by_label.items()
        }
        if controls != EXPECTED_COMPUTED:
            raise FixtureError(f"{case['id']}: computed controls differ from the frozen pair")
        if any(artifact.get("attestation") != "checked" for artifact in computed):
            raise FixtureError(f"{case['id']}: must contain three checked attestations")

        topology: dict[str, str] = {}
        for artifact_label in sorted(computed_by_label):
            relationship = computed_by_label[artifact_label].get(
                "prov:wasDerivedFrom"
            )
            if not isinstance(relationship, list) or len(relationship) != 1:
                raise FixtureError(
                    f"{case['id']}: {artifact_label} must have one immediate input"
                )
            reference = relationship[0]
            if (
                not isinstance(reference, dict)
                or set(reference) != {"@id"}
                or not isinstance(reference.get("@id"), str)
                or not reference["@id"]
            ):
                raise FixtureError(
                    f"{case['id']}: {artifact_label} must use one JSON-LD @id reference"
                )
            topology[artifact_label] = reference["@id"]

        observed_by_id = {artifact["@id"]: artifact for artifact in observed}
        observed_ids = set(observed_by_id)
        referenced_ids = set(topology.values())
        missing_ids = sorted(referenced_ids - observed_ids)
        if missing_ids:
            missing_label = missing_ids[0].split(":", 1)[-1]
            raise FixtureError(
                f"{case['id']}: missing immediate input {missing_label}"
            )
        unreferenced_ids = sorted(observed_ids - referenced_ids)
        if unreferenced_ids:
            unreferenced_label = observed_by_id[unreferenced_ids[0]]["label"]
            raise FixtureError(
                f"{case['id']}: unreferenced observed artifact {unreferenced_label}"
            )
        if actual_node_ids != EXPECTED_NODE_IDS[case["id"]]:
            raise FixtureError(
                f"{case['id']}: case-scoped node identifiers differ from the frozen pair"
            )
        if any(artifact.get("value") != "same-observation" for artifact in observed):
            raise FixtureError(f"{case['id']}: observed controls differ from the frozen pair")
        topology_labels = {
            computed_label: observed_by_id[observed_id]["label"]
            for computed_label, observed_id in topology.items()
        }
        if topology_labels != EXPECTED_TOPOLOGIES[case["id"]]:
            raise FixtureError(f"{case['id']}: topology differs from the frozen pair")

        immediate_root_ids = sorted(
            observed_by_id[observed_id]["label"] for observed_id in referenced_ids
        )
        count = len(referenced_ids)
        expected = case.get("expected_distinct_observed_root_count")
        if expected != count:
            raise FixtureError(f"{case['id']}: expected root count contradicts topology")
        case_results.append(
            {
                "case_id": case["id"],
                "computed_artifact_count": len(computed),
                "attestation_count": sum(
                    artifact.get("attestation") == "checked" for artifact in computed
                ),
                "distinct_observed_root_ids": immediate_root_ids,
                "distinct_observed_root_count": count,
                "expected_distinct_observed_root_count": expected,
                "conforms_to_frozen_expectation": count == expected,
            }
        )
        expanded_lineage_quads[case["id"]] = [
            {
                "subject": _expand_identifier(
                    computed_by_label[label]["@id"], jsonld_context
                ),
                "predicate": expanded_lineage_predicate,
                "object": _expand_identifier(topology[label], jsonld_context),
            }
            for label in sorted(computed_by_label)
        ]

    by_id = {result["case_id"]: result for result in case_results}
    return {
        "experiment": roundtripped.get("experiment"),
        "profile": roundtripped.get("profile"),
        "expanded_lineage_predicate": expanded_lineage_predicate,
        "expanded_lineage_quads": expanded_lineage_quads,
        "case_results": case_results,
        "same_computed_artifacts": True,
        "same_attestation_count": True,
        "serialization_roundtrip_preserved": True,
        "preserves_required_distinction": (
            by_id["one-observed-root"]["distinct_observed_root_count"] == 1
            and by_id["three-observed-roots"]["distinct_observed_root_count"] == 3
        ),
        "independence_state": "not-established",
    }


def run_experiment(experiment_dir: Path) -> dict[str, Any]:
    cases_path = experiment_dir.resolve() / "cases.json"
    try:
        source_bytes = cases_path.read_bytes()
        document = json.loads(source_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureError(f"cannot load {cases_path}: {error}") from error
    if not isinstance(document, dict):
        raise FixtureError("cases.json must contain one JSON object")

    report = evaluate_pair(document)
    report.update(
        {
            "implementation": "w3c_phase1_fit",
            "implementation_version": "1.0.0",
            "cases_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "all_expected": report["preserves_required_distinction"],
            "claim_boundary": {
                "established": [
                    "Canonical JSON serialization and reload preserve the recorded immediate-input distinction between one observed root and three observed roots.",
                    "The paired cases keep the same producer, context, computed artifact values, and checked-attestation count while changing only the recorded input topology.",
                ],
                "not_established": [
                    "W3C conformance, adoption, endorsement, or a normative Phase 1 data model.",
                    "Truth, causal independence, or organizational independence of a recorded observed root.",
                    "That signatures or attestations create independent evidence roots.",
                ],
            },
        }
    )
    return report
