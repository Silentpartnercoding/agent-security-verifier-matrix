# AIP-MATRIX-FIT-001

Status: **exploratory, frozen evaluation with executable results**

AIP-MATRIX-FIT-001 is an out-of-tree compatibility experiment. It asks a
narrow question: can the security claims made or carried by AIP draft-01 be
represented without overstatement in the verifier-facing vocabulary of
Principal Binding draft-06?

This is not a new protocol, token, wire format, certification program, or claim
that AIP is defective. A declared limitation is a successful mapping result.
The experiment rewards an exact mapping and a minimal reproducible gap equally.

## Frozen inputs

- `sources.json` pins the exact IETF draft text bytes, the Border crossing case
  and receipt artifacts, and Minority Prophet's claim-warrant semantics.
- `matrix.json` is the pre-adapter claim-to-verifier table.
- `cases.json` freezes the four hostile-but-valid situations and the constrained
  outcomes expected from the mapping.

The JSON files are experiment records. They are not schemas and are not
intended for use on an agent wire.

The mapping table and negative cases were committed before the evaluator was
implemented. `artifacts/results.json` is the reproducible output of applying
the evaluator to those frozen inputs.

## Report dispositions

- `EXACT`: the distinction is faithfully represented with a verifier, binding,
  failure path, and constrained conclusion.
- `DECLARED-GAP`: the source draft explicitly says the property is not
  established. This is a good result.
- `AMBIGUOUS`: relevant language or a carrier exists, but the verifier,
  binding, freshness, failure behavior, or permitted conclusion is incomplete.
- `UNREPRESENTED`: the evaluated fact has no source-draft carrier or verifier
  rule in the evaluated profile.

These are mapping-report dispositions only. Executable row evaluation must use
Principal Binding draft-06 outcomes such as `satisfied`, `unsatisfied`,
`indeterminate`, and `unsupported`.

## Claim boundary

The matrix evaluates AIP draft-01 as written. It does not infer deployment
controls, treat a signature as evidence of truth, treat an external name as
proof of independence, or let evidence assessment grant execution authority.

The table and cases were frozen in git before the evaluator was added, so
implementation results cannot be used to rewrite the exam.

## Run

The evaluator uses only the Python standard library:

```text
python3 -m aip_matrix_fit
python3 -m unittest discover -s tests -v
```

The report preserves two different levels deliberately:

- `mapping_result` says how AIP draft-01 maps to the claim.
- `row_outcome` uses Principal Binding's per-input evaluation vocabulary.

For the action-swap vector, the report also shows the adjacent AIP tool-scope
row succeeding while the exact-action row remains unsupported. The successful
scope check is never promoted into an exact-payload conclusion.

`command-center-card.html` is the self-contained Daily Cheese card for this
experiment. Its green states mean that the distinction is faithfully reported;
they do not mean that a signature establishes every adjacent claim.

## License

Apache-2.0. The referenced IETF drafts and upstream artifacts remain subject
to their respective terms; this repository pins and links them rather than
redistributing their full contents.
