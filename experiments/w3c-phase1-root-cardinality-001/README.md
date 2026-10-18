# W3C-PHASE1-ROOT-CARDINALITY-001

This is a proposed paired test vector for
[`w3c-cg/ai-computed-provenance#1`](https://github.com/w3c-cg/ai-computed-provenance/issues/1).
It stays within one producer and one provenance context. Both cases contain the
same computed artifacts `A`, `B`, and `C`, the same computed values, and three
checked attestations. Only the recorded PROV-O entity-level input topology
differs:

```text
Observed R -> computed A/B/C       Observed R1/R2/R3 -> computed A/B/C
3 computed artifacts               3 computed artifacts
3 checked attestations             3 checked attestations
1 distinct observed root           3 distinct observed roots
```

`cases.json` uses the existing `prov:wasDerivedFrom` relation. Its JSON-LD
context maps every carrier term to an IRI, while separate `one:` and `three:`
namespaces keep the alternative A/B/C nodes from merging during expansion; the
human labels remain A/B/C in both cases. The standard-library runner serializes
the complete fixture to canonical JSON, reloads it, expands the six lineage
triples, then follows each computed artifact's immediate relationship to its
recorded observed input. It fails closed on undefined JSON-LD terms, unscoped or
duplicate artifact identifiers, missing or extra inputs, ancestry on an
observed root, or a producer/context mismatch. The regenerated output must
match the committed `artifacts/results.json` byte for byte.

## One-command reproduction

Requirements are Python 3.9 or newer. No network access, API key, or private
credential is required. From the repository root:

```text
python3 -m w3c_phase1_fit --experiment experiments/w3c-phase1-root-cardinality-001 --output /tmp/w3c-phase1-root-cardinality-results.json && cmp /tmp/w3c-phase1-root-cardinality-results.json experiments/w3c-phase1-root-cardinality-001/artifacts/results.json && python3 -m unittest tests.test_w3c_phase1_fit -v
```

## Claim boundary

This fixture establishes only that the recorded distinction between one
observed root and three observed roots survives the JSON serialization/query
round-trip implemented here while the outputs and checked-attestation count stay
fixed. It is not a W3C conformance test, an adopted Community Group artifact,
or a proposed normative data model. Distinct recorded identifiers do not by
themselves establish truth, causal independence, statistical independence, or
organizational independence. Signatures and attestations do not create new
evidence roots.
