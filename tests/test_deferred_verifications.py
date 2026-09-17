"""The deferred-verification check, and the inputs that flip it.

Each test names the input that would flip it, so none is single-valued. The
load-bearing pair is test_pending_condition_that_has_fired_fails against
test_pending_condition_that_has_not_fired_passes: same record shape, same
status, different condition state, opposite outcome. Without that pair the
check could be a constant returning zero.

The probe is monkeypatched rather than hitting the network, so these tests are
deterministic and run offline. The real prober is exercised separately by
running the script in CI.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = "records/songbo-bu-2026-08-23.external-reproduction.json"

_spec = importlib.util.spec_from_file_location(
    "check_deferred_verifications", ROOT / "scripts" / "check_deferred_verifications.py"
)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


class DeferredVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads((ROOT / "registry" / RECORD).read_text())
        self.entry = self.record["payload"]["deferred_verifications"][0]
        self._real_probers = dict(check.PROBERS)

    def tearDown(self) -> None:
        check.PROBERS.clear()
        check.PROBERS.update(self._real_probers)

    def _run(self, record, *, condition):
        """Run the checker over one in-memory record with a stubbed probe."""
        check.PROBERS["ietf-draft-revision-published"] = (
            lambda blocked_on, offline: (condition, "stubbed")
        )
        written = ROOT / "registry" / RECORD
        original = written.read_text()
        written.write_text(json.dumps(record, indent=2) + "\n")
        try:
            return check.main()
        finally:
            written.write_text(original)

    # --- the pair that proves the check is not constant --------------------

    def test_pending_condition_that_has_fired_fails(self) -> None:
        """The original defect: -07 went public and the record still said not-yet."""
        record = copy.deepcopy(self.record)
        entry = record["payload"]["deferred_verifications"][0]
        entry["status"] = "pending"
        record["payload"]["reviewer_assertions_not_yet_publicly_verifiable"] = [
            entry["assertion"]
        ]
        self.assertEqual(self._run(record, condition=check.FIRED), 1)

    def test_pending_condition_that_has_not_fired_passes(self) -> None:
        """A genuinely unresolvable claim is allowed to sit, and must not fail."""
        record = copy.deepcopy(self.record)
        entry = record["payload"]["deferred_verifications"][0]
        entry["status"] = "pending"
        record["payload"]["reviewer_assertions_not_yet_publicly_verifiable"] = [
            entry["assertion"]
        ]
        self.assertEqual(self._run(record, condition=check.NOT_FIRED), 0)

    def test_unknown_is_not_collapsed_into_not_fired(self) -> None:
        """Three-valued, not two. On the committed (resolved) record a
        not-fired probe is a contradiction and fails; an unknown probe cannot
        disprove anything and must pass. If unknown were folded into not-fired
        these two would agree, and a network outage would start failing the
        build with a claim it never actually checked."""
        record = copy.deepcopy(self.record)
        self.assertEqual(self._run(record, condition=check.NOT_FIRED), 1)
        self.assertEqual(self._run(record, condition=check.UNKNOWN), 0)

    # --- structural invariants, all offline --------------------------------

    def test_parked_assertion_without_a_testable_condition_fails(self) -> None:
        record = copy.deepcopy(self.record)
        record["payload"]["reviewer_assertions_not_yet_publicly_verifiable"] = [
            "a claim nobody attached a condition to"
        ]
        self.assertEqual(self._run(record, condition=check.NOT_FIRED), 1)

    def test_resolved_entry_still_parked_fails(self) -> None:
        record = copy.deepcopy(self.record)
        entry = record["payload"]["deferred_verifications"][0]
        record["payload"]["reviewer_assertions_not_yet_publicly_verifiable"] = [
            entry["assertion"]
        ]
        self.assertEqual(self._run(record, condition=check.FIRED), 1)

    def test_resolution_must_state_what_it_does_not_establish(self) -> None:
        """A condition firing makes a claim checkable, not true. Dropping the
        negative space is how a resolution quietly widens a claim."""
        record = copy.deepcopy(self.record)
        record["payload"]["deferred_verifications"][0]["resolution"].pop("not_established")
        self.assertEqual(self._run(record, condition=check.FIRED), 1)

    def test_resolution_must_cite_evidence(self) -> None:
        record = copy.deepcopy(self.record)
        record["payload"]["deferred_verifications"][0]["resolution"]["evidence"] = []
        self.assertEqual(self._run(record, condition=check.FIRED), 1)

    def test_untestable_condition_kind_fails(self) -> None:
        record = copy.deepcopy(self.record)
        record["payload"]["deferred_verifications"][0]["blocked_on"]["kind"] = "when-someone-remembers"
        self.assertEqual(self._run(record, condition=check.FIRED), 1)

    def test_resolved_entry_whose_condition_never_fired_fails(self) -> None:
        record = copy.deepcopy(self.record)
        self.assertEqual(self._run(record, condition=check.NOT_FIRED), 1)

    # --- the committed record itself ---------------------------------------

    def test_committed_record_passes_offline(self) -> None:
        """No network: the structural invariants must still carry the check."""
        check.PROBERS.clear()
        check.PROBERS.update(self._real_probers)
        self.assertEqual(check.main(["--offline"]), 0)


if __name__ == "__main__":
    unittest.main()
