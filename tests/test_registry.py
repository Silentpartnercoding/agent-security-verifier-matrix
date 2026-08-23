from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry"


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads((REGISTRY / "record.schema.json").read_text())
        cls.index = json.loads((REGISTRY / "index.json").read_text())
        cls.records = [
            json.loads((REGISTRY / path).read_text())
            for path in cls.index["records"]
        ]

    def test_minimal_envelope_represents_both_mapping_versions(self) -> None:
        required = set(self.schema["required"])
        for record in self.records:
            self.assertEqual(set(record), required)
        mappings = {
            record["subject"]["id"]: record
            for record in self.records
            if record["record_type"] == "mapping"
        }
        self.assertEqual(set(mappings), {"AIP-MATRIX-FIT-001", "AIP-MATRIX-FIT-002"})
        self.assertFalse(mappings["AIP-MATRIX-FIT-001"]["payload"]["historical_record_mutated"])
        self.assertEqual(
            mappings["AIP-MATRIX-FIT-002"]["payload"]["supersedes"],
            mappings["AIP-MATRIX-FIT-001"]["record_id"],
        )

    def test_external_reproduction_does_not_overstate_independence(self) -> None:
        record = next(
            item for item in self.records if item["record_type"] == "external-reproduction"
        )
        self.assertEqual(record["payload"]["control_domain_independence"], "not-established")
        self.assertTrue(record["payload"]["reviewer_assertions_not_yet_publicly_verifiable"])
        self.assertEqual(len(record["payload"]["corrections"]), 5)

    def test_protocol_author_security_claims_remain_unreproduced(self) -> None:
        record = next(
            item for item in self.records if item["record_type"] == "protocol-author-review"
        )
        statuses = {
            claim["registry_verification_status"]
            for claim in record["payload"]["implementation_security_assertions"]
        }
        self.assertEqual(statuses, {"public-commit-reference-present-not-locally-reproduced"})


if __name__ == "__main__":
    unittest.main()
