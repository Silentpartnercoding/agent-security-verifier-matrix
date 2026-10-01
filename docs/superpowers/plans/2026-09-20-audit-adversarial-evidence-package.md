# AUDIT Adversarial Evidence Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the frozen refusal-completeness experiment with directly reproduced upstream tail-deletion evidence and a signed photocopy/root-count fixture, while keeping each claim within the checker that establishes it.

**Architecture:** Preserve `AUDIT-REFUSAL-COMPLETENESS-001` as the package root. Add a standalone Node probe that runs only against the pinned upstream checkout and a frozen summary of that run. Add a Python signed-evidence emitter and declared-lineage counter beside the existing independent completeness checker, then expose both result families in one deterministic report.

**Tech Stack:** Python 3 standard library, OpenSSL Ed25519 test vectors, optional Node.js/npm for reproducing the pinned upstream probe.

**Spec:** Owner-approved six-part package in the 2026-09-20 conversation: unchanged original case, terminal deletion, interior deletion, photocopy mutation, independent checker, and frozen result table.

## Global Constraints

- Do not change or patch the upstream implementation.
- Pin upstream execution-governance to commit `f2efb313d113149c6ddc9656307a605a7619f8ea`.
- Distinguish present-record integrity, expected-record completeness, and declared-root counting.
- A signature authenticates a record; it does not establish a separate evidence root.
- Count declared lineage roots only; do not claim truth, causal independence, or organizational independence.
- Keep the normal experiment reproduction free of API keys and paid services.
- Make no external post, submission, push, merge, or publication in this plan.

## Review Focus

- A valid terminal prefix must remain valid under the upstream present-record verifier while failing completeness against the frozen attempt manifest.
- Removing an interior record must break both the chain and expected-record completeness.
- Several separately signed descendants of one declared root must count as one declared root.
- Missing parents and lineage cycles must be `unverifiable`, never silently minted as new roots.
- The frozen artifact must bind every new input and the upstream probe result by SHA-256.

---

### Task 1: Freeze the pinned upstream tail-deletion reproduction

**Files:**
- Create: `experiments/audit-refusal-completeness-001/upstream-tail-deletion-probe.mjs`
- Create: `experiments/audit-refusal-completeness-001/artifacts/upstream-tail-deletion.json`
- Modify: `tests/test_audit_refusal_fit.py`
- Modify: `experiments/audit-refusal-completeness-001/README.md`

**Interfaces:**
- Consumes: the pinned execution-governance commit and its exported `createGate`, `verifyReceiptFile`, `generateSigningKey`, and `fromB64u` functions.
- Produces: deterministic JSON containing the pinned commit plus full-chain and tail-deleted verifier summaries.

- [ ] **Step 1: Write the failing artifact-contract test**

Add a test that loads `artifacts/upstream-tail-deletion.json` and requires the pinned commit, `{ok: true, total: 3, breaks: []}` for the full file, and `{ok: true, total: 2, breaks: []}` after terminal deletion.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.test_audit_refusal_fit.RefusalExperimentTests.test_upstream_tail_deletion_result_is_pinned -v`

Expected: FAIL because the frozen upstream artifact does not exist.

- [ ] **Step 3: Add the standalone upstream probe and frozen result**

The probe must generate three receipts using the pinned upstream package, verify the full JSONL file, delete only the final line, verify the prefix, and print only deterministic summary fields. Freeze the already reproduced output from an unmodified pinned checkout.

- [ ] **Step 4: Run the probe against a clean pinned checkout and compare it byte-for-byte**

Run from the upstream checkout after `npm ci && npm run build`:

`node /absolute/path/to/upstream-tail-deletion-probe.mjs > /tmp/upstream-tail-deletion.json && cmp /tmp/upstream-tail-deletion.json /absolute/path/to/artifacts/upstream-tail-deletion.json`

Expected: PASS.

- [ ] **Step 5: Run the focused Python test and verify GREEN**

Run: `python3 -m unittest tests.test_audit_refusal_fit.RefusalExperimentTests.test_upstream_tail_deletion_result_is_pinned -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `test: freeze upstream terminal-deletion counterexample`

### Task 2: Add signed declared-root counting and the consolidated result table

**Files:**
- Create: `audit_refusal_fit/evidence.py`
- Create: `audit_refusal_fit/root_counter.py`
- Create: `experiments/audit-refusal-completeness-001/evidence-cases.json`
- Modify: `audit_refusal_fit/__init__.py`
- Modify: `audit_refusal_fit/experiment.py`
- Modify: `tests/test_audit_refusal_fit.py`
- Modify: `experiments/audit-refusal-completeness-001/artifacts/results.json`
- Modify: `experiments/audit-refusal-completeness-001/README.md`

**Interfaces:**
- Consumes: `emit_evidence_records(manifest, private_key) -> list[dict]` and `count_declared_roots(records, public_key) -> dict`.
- Produces: `declared_root_count`, `distinct_record_count`, `collapsed_descendant_count`, signature and chain verification states, plus `unverifiable` for incomplete or cyclic lineage.

- [ ] **Step 1: Write failing tests for the photocopy and lineage-failure cases**

Require three separately signed records in one parent chain to report three records, one declared root, and two collapsed descendants. Require two declared roots to report two. Require a missing parent and a cycle to return `unverifiable` without inventing roots.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3 -m unittest tests.test_audit_refusal_fit.DeclaredRootCounterTests -v`

Expected: FAIL because the emitter and counter do not exist.

- [ ] **Step 3: Implement the minimal signed-evidence emitter and declared-lineage counter**

Sign canonical records with the existing public test-vector key. Verify every signature and the record chain before traversing parent links. Treat a root as declared only when `parent_record_id` is absent and `root_basis_state` is `declared`; never infer independence from a signer, key, repository, or record count.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python3 -m unittest tests.test_audit_refusal_fit.DeclaredRootCounterTests -v`

Expected: PASS.

- [ ] **Step 5: Add the frozen evidence cases to the experiment report**

Add the evidence manifest hash, upstream probe hash, root-count results, and an explicit three-column result table: present-record integrity, expected-record completeness, and declared-root count.

- [ ] **Step 6: Regenerate the artifact and update its named SHA-256**

Run: `python3 -m audit_refusal_fit --experiment experiments/audit-refusal-completeness-001 --output experiments/audit-refusal-completeness-001/artifacts/results.json`

Expected: exit 0 and `all_expected: true`.

- [ ] **Step 7: Run the focused and full suites**

Run: `python3 -m unittest tests.test_audit_refusal_fit -v`

Expected: PASS.

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS with zero failures.

- [ ] **Step 8: Run the exact one-command reproduction and compare artifacts**

Run the README command with a temporary output and `cmp` it against the committed report.

Expected: PASS.

- [ ] **Step 9: Commit**

Commit message: `feat: add signed evidence-root photocopy fixture`

### Task 3: Whole-branch evidence review

**Files:**
- Review only: every change from `de9153e5d199eaa95fef89db2d6036c0916b3d76` to branch HEAD.

**Interfaces:**
- Consumes: Task 1 upstream evidence and Task 2 deterministic report.
- Produces: a review verdict on claim boundaries, reproducibility, and whether any result is mislabeled as external or independent.

- [ ] **Step 1: Review the complete diff against the approved package**

Check every claim for its named verifier and ensure that upstream integrity, independent completeness, and declared-root counting remain distinct.

- [ ] **Step 2: Fix every Critical or Important finding test-first**

For each finding, add a focused failing test, verify RED, make the smallest correction, verify GREEN, and rerun the full suite.

- [ ] **Step 3: Run final verification from the committed tree**

Run the full Python suite, exact artifact regeneration, source-pin verification, and the pinned upstream probe comparison.

Expected: every command exits 0 and the worktree is clean.
