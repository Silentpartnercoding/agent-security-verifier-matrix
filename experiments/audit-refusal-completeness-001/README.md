# AUDIT-REFUSAL-COMPLETENESS-001

This experiment implements one narrow acceptance test proposed in the
AgentProto discussion: an implementation separate from the proposer emits and
checks refusal records against frozen inputs, including a case where a required
record should exist but is absent.

The experiment name describes its intended discussion venue. It is not an IETF
work item, an adopted AUDIT document, or an IETF endorsement.

It does not copy or invoke the upstream `execution-governance` implementation.
The Python emitter and checker were written from the pinned public requirements
and use OpenSSL only for Ed25519 test-vector signing and verification.

## Result

The frozen manifest commits to three attempts: one allowed decision, one denied
decision, and one request whose arguments have no canonical JSON
representation. The last attempt produces a separate signed refusal record; it
does not place a placeholder digest into an authorization receipt.

Four frozen cases are checked:

- `complete` is `verified`.
- `missing-terminal-refusal` is a `violation`. Its remaining signatures and
  hash chain still verify, so `external-attempt-commitment` is the decisive
  check.
- `missing-middle-deny` is a `violation`; both the manifest comparison and the
  chain expose the deletion.
- `no-external-commitment` is `unverifiable`, because silence cannot say whether
  an attempt or its record is missing.

The committed report is
`04537757831823352150fe8fa621e0b0ec4bf43e869eae0bd39e64cf26f6e209`.

## One-command reproduction

Requirements are Python 3.9 or newer and an `openssl` command with Ed25519
support. No API key, network service, or private credential is required. The
committed private key is deliberately a public test-vector key and MUST NOT be
used outside this experiment.

From the repository root:

```text
python3 scripts/fetch_pinned_sources.py --manifest experiments/audit-refusal-completeness-001/sources.json --destination experiments/audit-refusal-completeness-001/vendor/sources && python3 -m audit_refusal_fit --experiment experiments/audit-refusal-completeness-001 --output /tmp/audit-refusal-results.json && cmp /tmp/audit-refusal-results.json experiments/audit-refusal-completeness-001/artifacts/results.json && python3 -m unittest tests.test_audit_refusal_fit -v
```

The fetch step fails closed on a byte-count or SHA-256 mismatch. The evaluator
does not access the network.

## Independence and claim boundary

This is a separate implementation root: a different repository and language,
with no upstream source code imported or invoked. It was written after reading
the pinned public requirements, so it is not a clean-room implementation. It is
also not an external reproduction, because it was produced under the
Silentpartnercoding control domain. A separate person or organization must run
the frozen command and publish what it obtained before an external-reproduction
claim is warranted.

The result establishes only that the checker detects a missing terminal refusal
record when a separately frozen attempt manifest says the record must exist. It
does not establish conformance of Bradley B's `eg-conform` format checker,
production suitability of the public test key, or progress by a party that
emitted an entry record and then remained silent.

The public IPR disclosure associated with the motivating contribution states
royalty-free reasonable and non-discriminatory terms for Necessary Patent
Claims used to implement the relevant IETF specification:
<https://datatracker.ietf.org/ipr/7500/>.
