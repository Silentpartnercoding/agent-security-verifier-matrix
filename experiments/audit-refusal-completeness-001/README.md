# AUDIT-REFUSAL-COMPLETENESS-001

This experiment implements one narrow acceptance test proposed in the
AgentProto discussion: an implementation separate from the proposer emits and
checks refusal records against frozen inputs, including a case where a required
record should exist but is absent. The v1.1 package also carries a separate
declared-lineage fixture showing that three signed descendants of one recorded
observation remain one declared evidence root.

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

Five signed lineage cases are checked separately:

- `photocopy-three-one-root` contains three valid signed records and counts one
  declared root plus two collapsed descendants.
- `two-declared-roots` contains four valid signed records and counts two
  declared roots.
- `duplicate-root-basis` contains two separately signed root records carrying
  the same declared basis identifier and counts one root, not two.
- `missing-parent` and `lineage-cycle` are `unverifiable`; neither condition
  silently creates a root.

The counter reports `independence_state: not-established` in every case.
Declared lineage is sufficient to prevent record-count inflation; it is not
proof that a declared root is true or causally independent.

The committed combined report is
`2441c35b2e499c3ae2ee965fdba1464d18a32973ae60098c9686e574e686c845`.
The separately frozen upstream probe is
`5cb6451306300a1123e19d410e3256e735658cb310203826f0894d1445eb5b02`.

## Named-verifier result table

| Case | Present-record integrity | Expected-record completeness | Declared-root counting |
| --- | --- | --- | --- |
| Upstream complete file | `verified` by pinned upstream `verifyReceiptFile` | not evaluated | not evaluated |
| Upstream terminal deletion | `verified` by pinned upstream `verifyReceiptFile` | not evaluated | not evaluated |
| Independent complete corpus | `verified` by independent signature and chain checks | `verified` by external-attempt commitment | not evaluated |
| Independent terminal-refusal deletion | `verified` by independent signature and chain checks | `violation` by external-attempt commitment | not evaluated |
| Independent interior deletion | `violation` by independent chain check | `violation` by external-attempt commitment | not evaluated |
| Signed photocopy chain | `verified` by independent signature and chain checks | not evaluated | one declared root from three signed records |

The upstream terminal-deletion row and independent terminal-refusal row use
different record formats and frozen inputs. Their shared structural lesson is
reported without pretending the independent checker ran over upstream bytes.

## Pinned upstream tail-deletion probe

The separate `upstream-tail-deletion-probe.mjs` runs the upstream
`verifyReceiptFile` implementation itself at commit
`f2efb313d113149c6ddc9656307a605a7619f8ea`. It generates three valid
receipts, verifies the complete file, deletes only the final receipt, and
verifies the surviving prefix. Both calls return `ok: true`; the reported
total changes from three to two and neither report contains a break.

That is not a defect in a verifier whose stated scope is the integrity of
records supplied to it. It is a counterexample to the stronger claim that
present-record integrity alone establishes that every expected terminal record
exists. The independently written Python checker adds the separate external
attempt commitment needed to evaluate that stronger property.

To reproduce the upstream observation, check out the pinned commit in a clean
copy of `https://github.com/11-11AI/execution-governance`, run `npm ci && npm
run build`, then run this repository's probe with that checkout as the current
directory:

```text
node /path/to/agent-security-verifier-matrix/experiments/audit-refusal-completeness-001/upstream-tail-deletion-probe.mjs > /tmp/upstream-tail-deletion.json && cmp /tmp/upstream-tail-deletion.json /path/to/agent-security-verifier-matrix/experiments/audit-refusal-completeness-001/artifacts/upstream-tail-deletion.json
```

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

The result establishes three bounded observations: the pinned upstream verifier
accepts a valid prefix after terminal deletion; the independent checker detects
a missing terminal refusal when a separately frozen attempt manifest says it
must exist; and the declared-lineage counter collapses three signed descendants
to one declared root. It does not establish a defect in a present-record
integrity verifier, conformance of Bradley B's `eg-conform` beyond the pinned
probe, truth or causal independence of a declared root, production suitability
of the public test key, or progress by a party that emitted an entry record and
then remained silent.

The public IPR disclosure associated with the motivating contribution states
royalty-free reasonable and non-discriminatory terms for Necessary Patent
Claims used to implement the relevant IETF specification:
<https://datatracker.ietf.org/ipr/7500/>.
