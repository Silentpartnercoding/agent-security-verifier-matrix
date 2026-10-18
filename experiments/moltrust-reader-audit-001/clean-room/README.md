# Clean-room v0.1 conformance reader

Python standard library only. The sole external task inputs are listed in
`EXPOSURE.md` and `INPUT-SHA256SUMS`. No network access or oracle comparison
is part of this implementation or its tests.

From this `clean-room` directory, run:

```sh
python3 -E -S -B -m unittest -v test_reader test_bundle test_review test_partial_evidence test_opaque
python3 -E -S -B reader.py --inputs ../inputs --predictions predictions.jsonl --counts counts.json
python3 -E -S -B verify_freeze.py
```

The final commands ignore Python environment overrides and site startup
customizations. The reader verifies every manifest hash before evaluating any cases. It
emits one deterministic JSONL row for each manifest case, sorted by neutral
filename. The filename determines only `case_id`. Each row contains a
three-way `verdict`, exact specification `grounds`, a `reason`, and any
remaining `unresolved` issues when a definitive violation already rejects.
Aggregate counts are computed from these rows; no case IDs, outcome totals,
or neutral-case verdicts are hardcoded in source or tests.

`AMBIGUITIES.md` records the boundaries of the text, adapter decisions,
and what cannot be established without outside specifications or code.
In particular, `flat` collection hashing is intentionally not guessed.

## Test-driven development evidence

The synthetic suite was authored before `reader.py`. Its first run failed
with `ModuleNotFoundError: No module named 'reader'`. The initial
implementation then passed 47 tests. Four further tests were added before
the next change: one caught the semantic contradiction between
`precondition-unsatisfiable` and an exercised state; its first run failed
because the implementation accepted that synthetic report. The reader was
then corrected under §1.2. The additional tests verify malformed-field
robustness, deterministic output for every allowed input, and input-order
invariance for every allowed input. Corpus tests assert properties only;
they never consult expected verdicts.

The final verification record is generated as `VERIFICATION.json` and
`ARTIFACT-SHA256SUMS`; the repository commit freezes source, tests,
exposure/hash records, predictions, counts, and these documents before any
oracle is available to this implementation.

## Specification-only review revision

The original freeze remains in Git history at
`22fadbcd0126b66935a420b0e305e9619fe25f47`.
The seven review findings and their test-first evidence are recorded in
`REVIEW-TDD.md`. All seven new test methods failed before implementation
changes (eight assertion failures because the optional-field test has two
subcases). The revised complete suite contains 58 test methods. No review
finding carried an expected neutral-case outcome, and no oracle or other
implementation was accessed during this revision.

A further specification-only review preserves the second freeze at
`d05b0d333927c084859e58b777988416d17c26cb`. Five additional test methods
cover partial control bindings, projection-specific observation conflicts,
and the verdict-record upper bound on disclosure counters. Their final
preimplementation run failed all five methods (eight assertion failures
including dynamically selected permitted-input subcases). The revised full
suite contains 63 test methods. `REVIEW-TDD.md` records this third freeze's
test-first evidence and the §5.3 counter classification.

The final partial-carriage correction preserves the third freeze at
`7fdc252c81692193e69c08da0d7eb0ef0fcad3a3`. One new regression method
first failed for both empty and partial carried objects, then passed after
nonconflicting projections were merged independently from carried/resolved
representations. At that freeze, the full suite contained 64 test methods.

The opaque-primitive correction preserves the fourth freeze at
`c75beb06db71af7f9dd519bdf80cdb8bad7f0095`. Two additional tests failed
before implementation: a correct comparable moved set was rejected solely
for additionally naming the opaque error list, and a real comparable
mismatch incorrectly added an opaque-subset rejection. The reader now
partitions comparable projections from the recognized opaque primitive.
The full current suite contains 66 test methods.

## Portable packaging note

The clean-room freeze was created at Git commit
`24c54f14824f6a802572786ff6f7a58db341d760`. This copy changes only four
hard-coded temporary input paths to repository-relative paths so a stranger
can rerun it after cloning. The reader's decision logic is byte-for-byte the
same as that freeze. Regeneration still produces the frozen prediction and
count digests recorded in `VERIFICATION.json`.
