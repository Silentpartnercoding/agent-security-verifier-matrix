# AIP-MATRIX-FIT-001

Status: **exploratory, frozen before adapter implementation**

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

The adapter is intentionally not present in this commit. The table and cases
are frozen first so implementation results cannot be used to rewrite the exam.
