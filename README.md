# AIP-MATRIX-FIT-002

Status: **AIP v0.2 externally accepted; second-protocol registry test complete**

AIP-MATRIX-FIT-002 is an out-of-tree correction and reproduction release. It asks a
narrow question: can the security claims made or carried by AIP draft-01 be
represented without overstatement in the verifier-facing vocabulary of
Principal Binding draft-06?

This is not a new protocol, token, wire format, certification program, or claim
that AIP is defective. A declared limitation is a successful mapping result.
The experiment rewards an exact mapping and a minimal reproducible gap equally.
The frozen v0.1 record remains immutable at tag
`aip-matrix-fit-001-v0.1.0` and commit
`8ed65b70f8933a659dcab00331d86bac40009abe`.

## What changed after external review

Songbo Bu independently reran the v0.1 release and supplied five corrections.
Sunil Prakash, the AIP draft author, publicly agreed with the core mapping
corrections and with the UNREPRESENTED result for exact A2A/MCP action binding.
This release:

- separates participant identifiers committed inside the artifact from the
  identity of the live presenter;
- separates credential/revocation freshness from completion-evidence freshness;
- emits `expected_row_outcome` because the harness predicts a constrained row
  outcome but does not emit a complete Principal Binding row-result record;
- verifies locally supplied source bytes and records `passed`, `failed`, or
  `skipped`; and
- declares who supplies ambient tool, time, and depth facts and what AIP does
  not authenticate about those facts.

The public review and reproduction records live under `registry/`. They keep
reproduced facts, reviewer assertions, author statements, and untested claims
separate. “External reproducer” does not imply an independently established
organizational control domain.

Songbo subsequently reran the corrected v0.2 tag, reproduced all 25 tests and
all six pinned source-byte checks, matched the committed result byte for byte,
and confirmed that v0.2 reflects the intended Principal Binding semantics.

## Frozen inputs

- `sources.json` retains the exact v0.1 source pins for the IETF draft text, the Border crossing case
  and receipt artifacts, and Minority Prophet's claim-warrant semantics.
- `matrix.json` is the pre-adapter claim-to-verifier table.
- `cases.json` freezes the four hostile-but-valid situations and the constrained
  outcomes expected from the mapping.

The matrix and case JSON files are experiment records. They are not schemas and
are not intended for use on an agent wire.

The v0.1 mapping table and negative cases were committed before its evaluator
was implemented. `artifacts/results.json` is the reproducible v0.2 output after
applying the five review corrections without rewriting v0.1 history.

## Report dispositions

- `EXACT`: the distinction is faithfully represented with a verifier, binding,
  failure path, and constrained conclusion.
- `DECLARED-GAP`: the source draft explicitly says the property is not
  established. This is a good result.
- `AMBIGUOUS`: relevant language or a carrier exists, but the verifier,
  binding, freshness, failure behavior, or permitted conclusion is incomplete.
- `UNREPRESENTED`: the evaluated fact has no source-draft carrier or verifier
  rule in the evaluated profile.

These are mapping-report dispositions only. The evaluator's
`expected_row_outcome` predicts how a complete Principal Binding draft-06 row
would be constrained, using values such as `satisfied`, `unsatisfied`,
`indeterminate`, and `unsupported`. It is not itself a complete row-result
record.

## Claim boundary

The matrix evaluates AIP draft-01 as written. It does not infer deployment
controls, treat a signature as evidence of truth, treat an external name as
proof of independence, or let evidence assessment grant execution authority.

The v0.1 table and cases were frozen in git before its evaluator was added, so
implementation results cannot be used to rewrite that historical exam. The
v0.2 correction release explicitly supersedes it and is independently pinned.

## Run

The evaluator uses only the Python standard library:

```text
python3 -m aip_matrix_fit
python3 -m unittest discover -s tests -v
```

With no local source files, the report records source-byte verification as
`skipped`; it never silently fetches mutable URLs. To verify the pinned bytes,
repeat `--source ID=PATH` for all six IDs in `sources.json` and require a pass:

```text
python3 -m aip_matrix_fit \
  --source aip-01=/path/to/draft-prakash-aip-01.txt \
  --source principal-binding-06=/path/to/draft-bu-agentproto-security-principal-binding-06.txt \
  --source border-crossing-cases=/path/to/cases.json \
  --source border-crossing-receipt=/path/to/crossing_receipt.py \
  --source border-crossing-receipt-tests=/path/to/test_crossing_receipt.py \
  --source minority-prophet-claim-warrant=/path/to/claim-warrant.schema.json \
  --require-source-verification
```

The report preserves two different levels deliberately:

- `mapping_result` says how AIP draft-01 maps to the claim.
- `expected_row_outcome` is the harness's constrained expectation for a
  Principal Binding row outcome.

For the action-swap vector, the report also shows the adjacent AIP tool-scope
row succeeding while the exact-action row remains unsupported. The successful
scope check is never promoted into an exact-payload conclusion.

`command-center-card.html` is the self-contained Daily Cheese card for this
experiment. Its green states mean that the distinction is faithfully reported;
they do not mean that a signature establishes every adjacent claim.

## Neutral registry boundary

`registry/record.schema.json` defines only the smallest repository metadata
envelope shared by a mapping record, an external reproduction, and a protocol
author review. It deliberately leaves protocol claim semantics inside the
version-pinned artifacts. It is not a new credential format, standards
proposal, certification mark, or IANA registry.

Registry generality is now **TESTED ON TWO PROTOCOLS**. The second mapping,
[`AGTP-MATRIX-FIT-001`](experiments/agtp-matrix-fit-001/), applies the same nine
experiment grouping labels and the unchanged record envelope to
`draft-hood-independent-agtp-08`. The mapping required no new claim semantics
and no schema change. [`AGTP-MATRIX-FIT-002`](experiments/agtp-matrix-fit-002/)
corrects the interpretation without rewriting v0.1: the grouping labels are not
Principal Binding claim identifiers, an exact identity-document artifact check
is not a C-001 live-presenter result, and the harness does not emit a complete
accepted-result object. No external reproduction record is included in this
correction release.

## License

Apache-2.0. The referenced IETF drafts and upstream artifacts remain subject
to their respective terms; this repository pins and links them rather than
redistributing their full contents.
