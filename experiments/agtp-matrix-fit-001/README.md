# AGTP-MATRIX-FIT-001

AGTP-MATRIX-FIT-001 is the second-protocol falsification test for the neutral
verifier-matrix registry. It maps the base profile of
`draft-hood-independent-agtp-08` to the same Principal Binding draft-06 claim
classes used for AIP, without changing the registry envelope or adding claim
semantics.

The evaluated profile includes AGTP Level 2 signed identity documents,
Governance Tokens, EXECUTE composition, Attribution-Records, and optional RATS
evidence. It does not import unpinned semantics from AGTP-CERT or other
companion drafts.

## Why AGTP

AGTP is structurally different from AIP. It is a proposed transport and
composition substrate rather than one delegated credential. It explicitly
claims protocol-level identity, authority, attribution, and A2A/MCP mappings.
That makes it a useful test of whether the registry is protocol-neutral.

## Frozen findings

- `EXACT`: registrar-signed artifact identity under a configured trust policy.
- `AMBIGUOUS`: multi-hop authority, live presenter identity, scope failure
  behavior, exact cross-protocol action binding, provenance appraisal,
  credential/revocation freshness, evidence freshness, and organizational
  verifier independence.

The concentration of `AMBIGUOUS` results is not a protocol score. Each result
identifies the smallest missing or conflicting verifier-facing fact. Two
particularly reproducible findings are:

1. Level 2 resolves and verifies the document for a self-asserted Agent-ID but
   does not require the live requester to prove possession of an agent key.
2. The draft assigns both 262 and 455 to Authority-Scope failures in different
   normative sections.

## Run

```text
python3 -m verifier_matrix experiments/agtp-matrix-fit-001
python3 -m unittest discover -s tests -v
```

To require the pinned official draft bytes:

```text
python3 -m verifier_matrix experiments/agtp-matrix-fit-001 \
  --source agtp-08=/path/to/draft-hood-independent-agtp-08.txt \
  --source principal-binding-06=/path/to/draft-bu-agentproto-security-principal-binding-06.txt \
  --source border-crossing-cases=/path/to/cases.json \
  --source border-crossing-receipt=/path/to/crossing_receipt.py \
  --source minority-prophet-claim-warrant=/path/to/claim-warrant.schema.json \
  --require-source-verification
```

No registry schema, wire protocol, certification claim, or historical AIP
artifact is changed by this experiment.
