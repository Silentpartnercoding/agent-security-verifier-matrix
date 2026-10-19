# What the pinned Lars reader actually verifies

This is a capability boundary, not a character judgment and not a claim that
the package misdescribes itself. Its README calls it a reader of report
objects. The important question is whether its output can be used as proof
that the reported checks and artifacts are genuine. It cannot.

The audit inspected commit
`6d8ee54b01d20a819869ceb9fcea096d59251f8c` and froze source hashes in
`SOURCE-PINS.json`.

## What it does verify

- It parses the supplied report objects and applies a substantial set of
  refusal and cannot-tell rules from the v0.1 text.
- It recomputes differences between the two *supplied observation objects*
  for verdict and fired-rule projections.
- It checks equality between a supplied reference digest string and a
  supplied resolved-object digest string.
- Its pinned baseline is deterministic on this machine and exactly matches
  the package's recorded output: 165 reports, 82 accept, 28 reject, and 55
  cannot-tell; JSONL SHA-256
  `505dfb71a640e7ef0eceb7f2d859e5cf08dac4c81bed80672135e0eb51b92130`.

## What it does not verify

- It never runs the checker named in a report.
- It never loads or hashes the underlying input or result artifact.
- It compares digest *strings* supplied inside the report; it does not prove
  that those strings describe the referenced bytes.
- It does not reconstruct or verify the declared collection root, leaf
  serialization, or count binding.
- For a prior run it explicitly notes that the content is not read.
- It enumerates whatever `.json` files are present. It has no external
  manifest, expected member count, or corpus digest, so omitted and duplicated
  reports are not rejected.
- If the specification file is absent, citation checking is skipped rather
  than failed closed.
- Its documented `PYTHONHASHSEED=0 python3 -I ...` command does not actually
  set that seed because isolated mode ignores Python environment variables.

The relevant source boundaries are `reader.py` lines 65–73, 218–240,
419–429, and 545–548 in the pinned commit.

## Adversarial data results

The frozen mutation artifacts show concrete failures at the input boundary.
`audit/replay_mutations.py` records the exact recipes, verifies the pinned
source commit and source hashes, and binds every mutated input tree and output
stream by SHA-256:

- Delete one known rejected report: exit 0, 164 outputs.
- Duplicate one report file: exit 0, 166 outputs.
- Replace a rejected report with an accepting body but retain its identifier:
  exit 0 and the identifier becomes accepted.
- Add a duplicate JSON key that overwrites the operative value: exit 0 and a
  known rejection becomes an acceptance.
- Supply an empty directory: exit 0 with a zero-member success summary.
- Supply duplicate evidence identifiers: the first object silently wins, so
  reversing the pair can change the verdict.
- Several malformed values crash the process. Two crashes occur after 160
  JSONL rows have already been emitted, creating a partial-output hazard for a
  caller that ignores the exit status.

These are robustness and corpus-integrity findings. Because the project does
not publish a JSON serialization schema, malformed-type cases should not be
misrepresented as violations of a schema it never claimed. The deletion,
duplication, identifier, ordering, and partial-output behaviors still matter
if this reader is used as evidence about a frozen corpus.

## Comparison without overclaiming

Against the selected upstream oracle, Lars matches 102 of 165 verdicts,
abstains on 55, and gives the opposite binary verdict on 8. Those 8 are
reported as disagreements, not automatically as bugs: the v0.1 prose leaves
some adapter and interpretation choices underdetermined.

The separately frozen specification-only reader rejects 34 reports and
abstains on 131. All 34 explicit rejections agree with the upstream expected
labels; none oppose them. For 10 of those cases Lars returns cannot-tell.
Case-by-case adjudication finds explicit contradictions or omissions in eight,
but the Lars reader identifies those facts and abstains under its documented
reading of v0.1's refusal policy. Two additional cases are underdetermined at
an earlier interpretive step. The clean-room reader deliberately accepts none
because the text does not pin the flat-tree leaf serialization and
count-binding encoding needed to establish the collection digest
cryptographically.

The defensible conclusion is therefore narrow: Lars's package is useful as
one semantic reading of self-reported objects, but its green cells do not
prove that the named checker ran, that the artifacts hash to the declared
digests, or that the corpus is complete. Running it and matching its output
is reproduction of a report interpreter, not independent verification of the
underlying claim.
