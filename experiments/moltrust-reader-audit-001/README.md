# MolTrust v0.1 reader audit

This experiment answers a narrower and more useful question than “does Lars's
program rerun?”:

> What does the pinned reader independently establish, which inputs can make
> it fail or mislead a caller, and what happens when a second implementation
> reads the specification without seeing Lars's code or expected verdicts?

## Run

Python standard library only; no network and no API key:

```sh
python3 verify.py
```

The command runs 66 clean-room tests, regenerates 165 clean-room predictions
byte-for-byte, rebuilds the three-way comparison from the three frozen source
artifacts, authenticates the source pins and clean-room history bundle, and
runs the audit/provenance tests.

The data attacks can be independently replayed after cloning the pinned Lars
repository at the commit in `SOURCE-PINS.json`:

```sh
python3 -m audit.replay_mutations --repo /path/to/reporting-format-v01-reader \
  --check artifacts/mutation-replay.json
```

The replay records the exact Python runtime and raw stderr hash for forensic
comparison. Its portable gate compares a second stderr hash after replacing
only the temporary repository and case-directory prefixes, because Python
tracebacks embed those machine-local absolute paths.

## Result in plain English

Lars built a useful **report reader**. It reads what a report says happened
and checks whether those declarations contradict the v0.1 rules. It does not
run the named checker, inspect the referenced artifacts, compute their hashes,
or prove that every expected report is present. Therefore an `accept` result
means “this supplied story contains no contradiction this reader found,” not
“the underlying work was independently verified.”

The baseline reproduces exactly: 165 inputs produce 82 accept, 28 reject, and
55 cannot-tell. That is evidence that the package is reproducible—not that
its inputs are true.

The data attacks expose the missing boundaries: deleting a rejected member,
duplicating a member, replacing a rejected member's body under the same ID,
and an empty corpus all exit successfully. A duplicate JSON key can flip a
known rejection to acceptance. Duplicate evidence identifiers are
first-wins and order-sensitive. Some malformed values crash after 160 output
rows, so consumers must not treat partial stdout as a completed audit.

The clean-room reader was frozen before any oracle or Lars output was shown to
it. On the same 165 neutral cases it returns 34 reject and 131 cannot-tell.
Every explicit rejection agrees with the upstream oracle, and it finds 10
explicit violations that Lars leaves at cannot-tell. It accepts none because
the prose does not specify enough cryptographic serialization detail to prove
the declared collection root. That conservatism is a feature of the test: it
refuses to invent a green result.

## What this proves—and does not

This proves that Lars's package works as one implementation of a semantic
reader and has identifiable robustness/completeness gaps. It does **not**
prove maliciousness, does not prove that all 8 Lars/oracle binary
disagreements are Lars bugs, and does not make the upstream oracle infallible.
Those disagreements are preserved for adjudication rather than converted
into a headline number.

The key protocol finding is stronger than a score comparison: neither a
self-reported digest nor a reader's green verdict authenticates the bytes,
execution, or completeness it describes. Those bindings need to be specified
and verified separately.

## Evidence map

- `CODE-AUDIT.md` — capability boundary and source-level findings.
- `SOURCE-PINS.json` — exact repositories, commits, and hashes.
- `inputs/` — Apache-2.0 sanitized specification/cases and manifest.
- `clean-room/` — independent specification-only reader, tests, exposure log,
  ambiguity ledger, predictions, and verification record.
- `artifacts/clean-room-history.bundle` — complete isolated Git history
  preserving the recorded pre-comparison freeze at commit
  `24c54f14824f6a802572786ff6f7a58db341d760`. The exposure log and history
  document the isolation procedure; unsigned Git history cannot by itself
  prove that no outside information was ever seen.
- `artifacts/lars-run.jsonl` — exact pinned baseline output.
- `artifacts/mutation-results*.json` — adversarial input runs.
- `audit/replay_mutations.py` and `artifacts/mutation-replay.json` — exact
  mutation recipes plus per-input-tree and per-output hashes for replay.
- `artifacts/upstream-oracle-audit.json` — pinned selection and expected results.
- `artifacts/comparison-rows.json` — per-case three-way join.
- `artifacts/audit-summary.json` — frozen aggregate claims.

The inputs derive from `probityai/agent-evidence-vectors`, licensed under
Apache-2.0; the upstream license is retained as `inputs/LICENSE.upstream.txt`.
The Lars repository is referenced by immutable commit and source hashes, not
redistributed here.
