# Specification-only review revision

Prior immutable freeze: `22fadbcd0126b66935a420b0e305e9619fe25f47`.
Only the original sanitized input bundle, local source/tests, and the
authorized specification-only review findings were used. No expected
neutral-case verdicts or oracle information were received or inspected.

## Test-first observations

Before any reader implementation change, seven synthetic regression tests
were added in `test_review.py`, then this exact command was run:

```sh
python3 -E -S -B -m unittest -v test_review
```

Observed: `Ran 7 tests`, `FAILED (failures=8)`, exit status 1. All seven
methods failed; method 6 had two separately failing subcases. Their
individual observed failures were:

1. Missing prior-run adapter identity produced `reject`, but absent identity
   with unresolved evidence establishes uncertainty, not a schema violation.
2. Adding an unsupported projection hid a decidable moved mismatch in the
   supported fired-rule projection, producing `cannot-tell` instead of the
   explicit §2 rejection.
3. A verdict-only observation pair without rule fields returned no
   recomputed moved set, although verdict movement was fully available.
4. Identical fixed checker/configuration digest identifiers still produced
   `cannot-tell`, leaving the binding condition with no success path.
5. A verdict record with unshared uniformly carried evidence produced a
   counter uncertainty even though no sharing or mixed carriage existed.
6. Non-authoritative arity and absence of the optional roll-up each produced
   an uncertainty solely because of their presence/absence.
7. Evidence lacking an adapter identifier bypassed row 14 entirely; missing
   observations produced only identity uncertainty instead of form rejection.

## Corrections and successful verification

The reader now distinguishes missing adapter facts from contradictions,
evaluates known projections independently, supports verdict-only
observations, accepts equal supplied fixed bindings as declared consistency,
detects actual shared/mixed counter topology, ignores non-authoritative arity,
permits absent optional roll-up, and validates anonymous evidence objects.
The former arity test was updated to assert invariance under optional arity.
The collection-hash construction/serialization/count-binding uncertainty
remains unchanged and explicit.

The complete suite command was then run:

```sh
python3 -E -S -B -m unittest -v test_reader test_bundle test_review
```

Observed: `Ran 58 tests`, `OK`, exit status 0. This includes deterministic
evaluation and input-order invariance over every manifest-listed neutral
case, without assertions against expected neutral-case outcomes.

The updated `verify_freeze.py` repeats that suite and checks byte-identical
prediction/count regeneration before writing the verification and hash
records. The new freeze is a descendant of the original commit; it does not
rewrite the original source, tests, or predictions in Git history.

## Further review: partial evidence and impossible counters

Preserved prior freeze: `d05b0d333927c084859e58b777988416d17c26cb`.

Five new regression methods in `test_partial_evidence.py` were run before
reader changes with:

```sh
python3 -E -S -B -m unittest -v test_partial_evidence
```

All five methods failed on their first run. The supplied-input test was
then generalized, still before reader changes, to select every case whose
referenced counter exceeds its verdict-record population without embedding
any case ID or expected corpus outcome. That preimplementation run observed
`Ran 5 tests`, `FAILED (failures=8)`, exit status 1. Its failures showed:

1. Missing control configuration suppressed a known checker mismatch.
2. Missing control checker suppressed a known constraint-set mismatch.
3. Conflicting fired-rule lists discarded an agreed verdict projection,
   preventing a decidable row-13 rejection.
4. A synthetic carried count of 100 with one verdict record was accepted.
5. Structurally selected supplied cases with referenced counts above their
   verdict-record populations had no explicit bound violation finding.

Each supplied binding component is now checked independently. An unresolved
component does not hide a contradiction in another. Observation conflicts
are similarly projection-local: agreed projections still drive their rows.

§5.3 says the counters count verdict records, so an individual counter
cannot exceed that population. The reader flags this as `cannot-tell` when
there is no independent rejection: §5.3 explicitly says the counter is
disclosure and not rejection, so inventing a new rejection row would exceed
the text. The finding is recorded even when another requirement rejects.
No leaf serialization, observation-count convention, or sum/disjointness
assumption is needed for this upper bound.

After implementation, the full command was:

```sh
python3 -E -S -B -m unittest -v test_reader test_bundle test_review test_partial_evidence
```

Observed: `Ran 63 tests`, `OK`, exit status 0. Input integrity,
determinism, and order invariance remain covered. The collection-hash
construction/serialization/count-binding uncertainty is unchanged.
No oracle or comparison information was consulted before this freeze.

## Final review: empty or partial redundant carriage

Preserved prior freeze: `7fdc252c81692193e69c08da0d7eb0ef0fcad3a3`.

Before changing the reader, this exact new regression was run:

```sh
python3 -E -S -B -m unittest -v test_partial_evidence.PartialEvidenceReviewTests.test_5_partial_carriage_cannot_hide_resolved_verdict_contradiction
```

Observed: `Ran 1 test`, `FAILED (failures=2)`, exit status 1. Both the
empty carried object and the partial rules-only carried object hid a
digest-matching resolved verdict. The reported result was `cannot-tell`
instead of the independently decidable row-13 rejection.

The reader now fills each supported projection absent from the carried
representation from the digest-matching resolved representation. A value
already present only in carriage remains available. Agreement retains the
projection; disagreement suppresses only that projection and records its
uncertainty. No representation's mere presence suppresses facts provided by
the other, and no serialization assumption is introduced.

The full existing suite plus the new regression then observed `Ran 64
tests`, `OK`, exit status 0 using the complete suite command above.
The final verification repeats these tests and confirms deterministic
regeneration before creating the new freeze. No comparison was performed.

## Opaque-primitive review

Preserved prior freeze: `c75beb06db71af7f9dd519bdf80cdb8bad7f0095`.
The allowed specification was reread at lines 152–188 and 558–588 before
implementation. The resulting distinction is between machine-comparable
verdict/rule-list projections and the recompute-opaque error-list primitive,
which no rejection row reads (§§2.1, 6.1, 7.1).

Two synthetic regressions were added and run before reader changes:

```sh
python3 -E -S -B -m unittest -v test_opaque
```

Observed: `Ran 2 tests`, `FAILED (failures=2)`, exit status 1.
The first pattern had correct verdict and fired-rule movement plus an
additional opaque `error list` declaration; it wrongly rejected on the
subset condition. The other pattern declared comparable verdict movement,
but resolved observations changed only the fired-rule list. It correctly
found the comparable mismatch and row 13, but incorrectly added a rejection
and uncertainty about the opaque primitive. The test isolates the permitted
rejection grounds rather than merely asserting a rejection verdict.

The implementation now partitions declared moved. Subset/equality checks
read only machine-comparable projections. The recomputed comparable set is
still required to be contained in compared; the opaque addition neither
causes a rejection nor suppresses any comparable contradiction.

The full suite command was then run:

```sh
python3 -E -S -B -m unittest -v test_reader test_bundle test_review test_partial_evidence test_opaque
```

Observed: `Ran 66 tests`, `OK`, exit status 0. All original input hashes,
determinism checks, and order-invariance checks remain part of verification.
No expected neutral-case result or comparison data was used.
