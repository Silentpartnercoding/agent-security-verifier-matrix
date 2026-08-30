# AGTP-MATRIX-FIT-002

AGTP-MATRIX-FIT-002 is a correction release for the out-of-tree mapping review
of `draft-hood-independent-agtp-08` against
`draft-bu-agentproto-security-principal-binding-06`. It supersedes the mapping
interpretation in AGTP-MATRIX-FIT-001 without rewriting its frozen artifact,
tag, or registry record.

This is a pre-adapter mapping review. It is not an AGTP implementation test, a
complete Principal Binding verifier matrix, an IETF position, or a claim that
the initial Principal Binding claim inventory is complete.

## Why a correction release

The v0.1 harness executes reproducibly, but its documentation blurred three
different layers:

1. The nine labels (`Identity`, `Authority`, and so on) are experiment grouping
   labels, not Principal Binding C-001 through C-014 claim identifiers.
2. Verifying a signed public Agent Identity Document is an exact artifact check,
   but it does not satisfy C-001, which asks which live instance is acting now.
3. `permitted_conclusion` and `expected_row_outcome` constrain this review; they
   are not stable accepted-result or complete row-result objects.

The corrected matrix therefore records the identity-document check as a
supporting fact, maps C-001 only to the `live-presenter` row, and states that the
signed document supplies at most an issuer-stated baseline scope for C-003. It
does not prove current key possession or a delegation chain.

`registry_envelope_changed: false` remains a structural observation.
`claim_semantics_extended: false` remains an experiment declaration; neither
field proves that this experiment's claim inventory is complete.

## Corrected findings

- `EXACT`: the pinned AGTP artifact-level identity-document verification under
  a configured trust policy. This is a supporting fact, not a C-001 result.
- `AMBIGUOUS`: C-001 live presenter identity; C-003 delegation semantics and
  attenuation; request-scope failure behavior; exact A2A/AGTP/MCP action
  binding; provenance appraisal; credential and evidence freshness; and
  organizational verifier independence.
- `UNREPRESENTED`: none in the four frozen cases.

The four cases still reproduce their constrained expectations. That shows the
harness behaves deterministically under the pinned interpretation. It does not
show that an AGTP implementation conforms, that every Principal Binding claim
has been mapped, or that the mapping is semantically complete.

## Frozen inputs and run

The five source pins are inherited unchanged from AGTP-MATRIX-FIT-001. With
local copies of those exact bytes:

```text
python3 -m verifier_matrix experiments/agtp-matrix-fit-002 \
  --source agtp-08=/path/to/draft-hood-independent-agtp-08.txt \
  --source principal-binding-06=/path/to/draft-bu-agentproto-security-principal-binding-06.txt \
  --source border-crossing-cases=/path/to/cases.json \
  --source border-crossing-receipt=/path/to/crossing_receipt.py \
  --source minority-prophet-claim-warrant=/path/to/claim-warrant.schema.json \
  --require-source-verification

python3 -m unittest discover -s tests -v
```

The evaluator never silently fetches mutable inputs. A required source-byte
verification fails closed when any supplied byte count or SHA-256 digest
differs from the frozen manifest.
