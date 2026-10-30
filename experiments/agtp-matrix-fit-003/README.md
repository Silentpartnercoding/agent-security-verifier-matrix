# AGTP-MATRIX-FIT-003

AGTP-MATRIX-FIT-003 is a new grading round for the out-of-tree mapping review
of AGTP against `draft-bu-agentproto-security-principal-binding-06`. It is
pinned to `draft-hood-independent-agtp-10`, published 30 October 2026.
AGTP-MATRIX-FIT-002 stays frozen and pinned to `-08`; this round leaves its
artifacts, tag, and registry record untouched.

This is a pre-adapter mapping review. It does not test an AGTP implementation,
complete a Principal Binding verifier matrix, state an IETF position, or claim
that the Principal Binding claim inventory is complete.

## Profile

Base AGTP-10 Level 2 path: signed identity document, Request-Signature,
Delegation-Chain verification, Governance Token action digest, EXECUTE,
Attribution-Records, and optional RATS evidence. Imports
draft-hood-agtp-identity-document-00 only for agent_public_key, its freshness
rules, and its rotation and prior-version retention rules, because the
mandatory request signature in -10 depends on them. All other companions stay
excluded: AGTP-CERT, AGTP-LOG, AGTP-TRUST, AGTP-IDENTIFIERS, AGTP-COMPOSITION,
and AGTP-DISCOVERY.

Earlier rounds imported no companion draft. In `-10` the identity document
format moved out of the base draft into `draft-hood-agtp-identity-document-00`,
and the base draft now requires every non-anonymous request to carry a
signature checked under the `agent_public_key` that companion defines. The
presenter row cannot be graded without it, so this round imports that one
companion for those fields and nothing else.

## Why a new round

`-10` changes the base protocol in ways that touch this matrix. Issues raised
on agentproto in August (presenter possession, 262 versus 455, token to payload
binding) are addressed in -10. The draft also adds a verified Delegation-Chain
and structured failure fields.

## Grades

| Row | FIT-002 (-08) | FIT-003 (-10) | -10 sections |
| --- | --- | --- | --- |
| identity-document-artifact | EXACT | EXACT | 2, 2.1, 7.1, 7.2, 7.3.2, 12.2, 12.4.1; identity-document-00 3.3, 3.5 |
| delegated-authority | AMBIGUOUS | EXACT | 6.6, 6.6.1, 8.2.9, 9.1 to 9.5, 12.4.3 |
| live-presenter | AMBIGUOUS | EXACT | 6.5.3, 6.5.4, 12.2, 12.4.1, 12.4.7; identity-document-00 3.3 |
| request-scope | AMBIGUOUS | EXACT | 2, 6.5.3, 6.6, 7.3.8, 8.2.8, 12.3, 12.4.2 |
| cross-protocol-action | AMBIGUOUS | AMBIGUOUS | 2, 6.5.3, 7.3.8, 8.2.8, 9.5.1, 10.2, 10.4, D.3 |
| completion-provenance | AMBIGUOUS | AMBIGUOUS | 6.5.5, 6.6.1, 8.2.4, 12.4.5, 12.4.11; identity-document-00 3.5 |
| credential-freshness | AMBIGUOUS | AMBIGUOUS | 6.5.4, 7.3.8, 9.3, 9.6, 12.4.4; identity-document-00 2.3, 3.3 |
| completion-evidence-freshness | AMBIGUOUS | AMBIGUOUS | 6.5.5, 12.4.11 |
| verifier-independence | AMBIGUOUS | AMBIGUOUS | 8.2.4, 12.4.5, 12.4.8, 12.4.11 |

Notes on the rows that moved or changed wording:

- `live-presenter`: a request whose signature fails under the document's
  `agent_public_key` is refused with 401 and reason `possession-unproven`.
  The row covers key possession by the sender. Several instances sharing one
  agent key remain indistinguishable, so C-001 at instance granularity stays
  open.
- `delegated-authority`: Section 9.3 fixes the inputs and the five checks, and
  Section 9.4 gives refused and incomplete outcomes with a reason and the
  failing hop. Membership resolution cites AGTP-DISCOVERY, which this profile
  excludes; when that input is unavailable the result is incomplete and denied,
  which `-10` defines exactly. Whether the origin grant itself was lawful stays
  outside the row (Section 9.5).
- `request-scope`: Section 6.6 now applies one obtainability rule: 455 when the
  request exceeds what the agent holds, 262 when the agent could obtain the
  missing authority.
- `cross-protocol-action`: the Governance Token `action_digest` catches a
  payload swap, including a changed tool name inside the payload. The
  originating task identifier sits outside the digest, and tool or resource
  identity still has no first-class binding (Section 10.4 marks it as under
  review), so the row stays AMBIGUOUS.
- `completion-provenance` and `credential-freshness` keep their grade with
  updated wording. Attribution-Record tamper evidence still depends on
  AGTP-LOG, which is excluded. `-10` refers to identity-document freshness
  rules, while `identity-document-00` gives a 300 second threshold for the
  Namespace Document only and no window for the Identity Document.

## Cases

Nine frozen cases. The four FIT-002 cases carry over, with the presenter and
action cases rewritten for the `-10` checks, and five cases are new.

| Case | Row | Expected |
| --- | --- | --- |
| wrong_presenter | live-presenter | 401 possession-unproven |
| widened_delegation_hop | delegated-authority | 551 refused, scope-exceeds-parent, hop 1 |
| unreachable_delegation_registry | delegated-authority | 551 incomplete, input-unavailable, hop 0 |
| claimed_scope_beyond_grant | request-scope | 455 scope-claim-invalid |
| granted_scope_unclaimed | request-scope | 262 |
| same_control_verifier | verifier-independence | indeterminate |
| stale_unverifiable_completion | completion-evidence-freshness | warrant outcome unverifiable |
| a2a_mcp_action_swap | cross-protocol-action | 262 token-action-mismatch; Border reference unsatisfied |
| a2a_task_substitution | cross-protocol-action | indeterminate; Border reference unsatisfied |

The two cross-protocol cases reuse `change_mcp_tool_or_payload` and
`substitute_task_or_context_id` from the pinned Border A2A-MCP-CROSSING-001
case file. The new vector types live in `verifier_matrix/evaluator.py` and run
only when a matrix declares `evaluator_contract` 1.2.0, so the FIT-001 and
FIT-002 reports regenerate byte for byte.

## Frozen inputs and run

The source set is inherited from AGTP-MATRIX-FIT-002 with two changes: `agtp-08`
is replaced by `agtp-10`, and `identity-document-00` is added. The evaluation
vocabulary stays at `principal-binding-06` so that only the AGTP revision
changes between rounds. With local copies of those exact bytes:

```text
python3 -m verifier_matrix experiments/agtp-matrix-fit-003 \
  --source agtp-10=/path/to/draft-hood-independent-agtp-10.txt \
  --source identity-document-00=/path/to/draft-hood-agtp-identity-document-00.txt \
  --source principal-binding-06=/path/to/draft-bu-agentproto-security-principal-binding-06.txt \
  --source border-crossing-cases=/path/to/cases.json \
  --source border-crossing-receipt=/path/to/crossing_receipt.py \
  --source minority-prophet-claim-warrant=/path/to/claim-warrant.schema.json \
  --require-source-verification

python3 -m unittest discover -s tests -v
```

The evaluator never fetches mutable inputs. A required source-byte
verification fails closed when any supplied byte count or SHA-256 digest
differs from the frozen manifest.

## Text notes on -10

Gaps in the `-10` text that change how a checker behaves. None of them changes
a grade in this round.

- Base `-10` gives no request header or field that carries the Governance
  Token. The action vectors supply the token alongside the request.
- Section 9.3 gives no precedence when one hop is invalid and another is
  indeterminate. FIT-003 reports the invalid result (551 refused).
- The 262 outcome for condition (b) in Section 6.6 has no reason token. The
  `granted_scope_unclaimed` case expects no reason.
- The 401 reason vocabulary in Section 6.6 omits `possession-unproven`, which
  Section 6.5.4 uses.
- Section 12.4.1 (Agent Spoofing) does not mention Request-Signature.
- `token-action-mismatch` is returned with 262, while the 262 description in
  Section 6.6 lists only obtainable authorization.
- The 403 row in Section 6.6 still reads "Agent lacks authority for requested
  action per Authority-Scope", which overlaps the 455 rule.
- Section 7.3.8 lists `parameters` and `payload_sha256` as separate digest
  members, while the Appendix D.3 example nests the payload inside
  `parameters`. The vector keeps them separate.
- Section 7.3.8 does not say how the payload bytes are canonicalized before
  `payload_sha256` is taken.
- Section 12.3 still says Level 2 servers SHOULD retrieve the manifest when the
  declared scope exceeds read-only operations. FIT-003 treats retrieval of the
  signed identity document as required, since the request signature in `-10`
  depends on it.
