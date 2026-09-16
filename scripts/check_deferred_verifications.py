#!/usr/bin/env python3
"""Fail when a claim that was parked pending an external condition comes due.

The defect this exists for: a record states that some assertion cannot be
checked yet -- a draft is unpublished, a branch is unmerged, a run has not
happened -- and then nobody revisits it when the condition fires. The claim
keeps its provisional label forever, which reads as caution and is actually
staleness. That happened here: the AIP reproduction record parked a reviewer
assertion "until that revision is public", -07 went public on 2026-09-15, and
the record still said not-yet-verifiable the next day.

The mechanism is the one scripts/check_gate_coverage.py uses for unmerged
branches, generalised: a pending entry ASSERTS ITS BLOCKER IS STILL UNFIRED.
Satisfaction breaks the build. A check that only ever confirms "still pending"
would be single-valued and would have caught nothing.

Three outcomes, kept separate on purpose:

  fired       the condition happened -- a pending entry here is an ERROR
  not-fired   the condition has not happened -- a pending entry is fine
  unknown     we could not find out (offline, network error, API change)

`unknown` is never collapsed into `not-fired`. Reporting "still pending"
because the network was down is how a check launders its own blindness into a
clean result. Offline, the structural invariants below still run in full and
still fail the build on their own.

Exit 0 on success, 1 on any problem.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"

FIRED, NOT_FIRED, UNKNOWN = "fired", "not-fired", "unknown"
STATUSES = {"pending", "resolved"}

# Every kind must have a prober below. An unrecognised kind is an error, not an
# `unknown`: it means someone wrote a condition nothing can ever test.
PROBERS = {}


def prober(kind):
    def register(fn):
        PROBERS[kind] = fn
        return fn

    return register


@prober("ietf-draft-revision-published")
def _ietf_draft_revision_published(blocked_on, offline):
    """Has revision N of an IETF draft been published?"""
    if offline:
        return UNKNOWN, "offline mode"
    url = (
        f"https://www.ietf.org/archive/id/{blocked_on['draft']}-{blocked_on['revision']}.txt"
    )
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status == 200:
                return FIRED, f"{url} returns 200"
            return UNKNOWN, f"{url} returned {response.status}"
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return NOT_FIRED, f"{url} returns 404"
        return UNKNOWN, f"{url} returned HTTP {error.code}"
    except Exception as error:  # network down, DNS, TLS, timeout
        return UNKNOWN, f"{url} unreachable: {type(error).__name__}"


@prober("path-exists")
def _path_exists(blocked_on, offline):
    """Has an artifact landed in this repository?"""
    target = ROOT / blocked_on["path"]
    return (FIRED, f"{blocked_on['path']} exists") if target.exists() else (
        NOT_FIRED,
        f"{blocked_on['path']} absent",
    )


def main(argv=None) -> int:
    offline = "--offline" in (sys.argv if argv is None else argv)
    problems: list[str] = []
    index = json.loads((REGISTRY / "index.json").read_text(encoding="utf-8"))

    total = pending = resolved = 0
    unknowns: list[str] = []

    for relative in index["records"]:
        record = json.loads((REGISTRY / relative).read_text(encoding="utf-8"))
        payload = record["payload"]
        name = record["record_id"]
        deferred = payload.get("deferred_verifications", [])
        parked = payload.get("reviewer_assertions_not_yet_publicly_verifiable", [])

        # 1. No orphan prose. Anything still labelled not-publicly-verifiable
        #    must have a machine-testable condition attached, or nothing will
        #    ever tell us it came due.
        by_assertion = {entry["assertion"]: entry for entry in deferred}
        for assertion in parked:
            entry = by_assertion.get(assertion)
            if entry is None:
                problems.append(
                    f"{name}: assertion is parked as not-publicly-verifiable with no "
                    f"deferred_verifications entry, so nothing can detect when it comes due: {assertion!r}"
                )
            elif entry["status"] != "pending":
                problems.append(
                    f"{name}: assertion is marked {entry['status']!r} in deferred_verifications "
                    f"but is still listed as not-publicly-verifiable: {assertion!r}"
                )

        for entry in deferred:
            total += 1
            entry_id = f"{name}/{entry['id']}"

            if entry["status"] not in STATUSES:
                problems.append(f"{entry_id}: unknown status {entry['status']!r}")
                continue

            kind = entry["blocked_on"]["kind"]
            probe = PROBERS.get(kind)
            if probe is None:
                problems.append(
                    f"{entry_id}: blocked_on kind {kind!r} has no prober, so this condition "
                    "can never be tested. Add a prober or restate the condition."
                )
                continue

            state, why = probe(entry["blocked_on"], offline)

            if entry["status"] == "pending":
                pending += 1
                if state == FIRED:
                    problems.append(
                        f"{entry_id}: the blocking condition has FIRED ({why}). "
                        "Re-check the assertion against the now-available evidence, then move this "
                        "entry to resolved and take it out of reviewer_assertions_not_yet_publicly_verifiable."
                    )
                elif state == UNKNOWN:
                    unknowns.append(f"{entry_id} ({why})")
                continue

            # resolved
            resolved += 1
            if entry["assertion"] in parked:
                problems.append(
                    f"{entry_id}: resolved but still parked as not-publicly-verifiable"
                )
            resolution = entry.get("resolution") or {}
            if not resolution.get("evidence"):
                problems.append(f"{entry_id}: resolved without citing evidence")
            if not resolution.get("established"):
                problems.append(f"{entry_id}: resolved without stating what it established")
            # The asymmetry that makes this worth writing down: a condition
            # firing makes a claim checkable, not true, and rarely establishes
            # causation. Forcing the negative space to be written prevents a
            # resolution from quietly widening the claim.
            if not resolution.get("not_established"):
                problems.append(
                    f"{entry_id}: resolved without stating what it does NOT establish"
                )
            if state == NOT_FIRED:
                problems.append(
                    f"{entry_id}: marked resolved but its condition reports not-fired ({why})"
                )
            elif state == UNKNOWN:
                unknowns.append(f"{entry_id} ({why})")

    if problems:
        print("Deferred-verification check FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"Deferred-verification check passed: {total} entries "
        f"({pending} pending, {resolved} resolved); no parked assertion lacks a testable "
        "condition, no pending condition has fired, every resolution states what it does not establish."
    )
    if unknowns:
        print(
            f"  {len(unknowns)} condition(s) NOT CHECKED (reported as unknown, not as still-pending):"
        )
        for item in unknowns:
            print(f"    - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
