# Specification-only interpretation and unresolved points

Authority: `specification-v0.1.txt`, SHA-256
`8b0e9f66a1cc1ee5df3922e4057552dd365a927969ff79759fe43bf2aa418e3f`.
No corpus implementation, expected result, or oracle was consulted.

## Result semantics

`reject` means at least one explicit requirement is contradicted. Each row
lists the exact numbered rejection row or section that establishes it.
`cannot-tell` means no definitive violation was established and at least
one applicable question cannot be decided from the permitted text and data.
`accept` is reserved for inputs with neither violation nor unresolved issue.
An explicit rejection takes priority over uncertainty; `unresolved` preserves
the remaining limitations on rejected inputs. This is deliberately stronger
than equating “no numbered row fired” with unconditional acceptance.

## Open matters that the implementation does not fill in

1. **Collection hashes (§3.1, O3).** The text expressly says the list has not
   defined `flat` and that its vector pair defines the member. Those vector
   pairs and their expected results are outside this clean room. The text
   names `rfc6962` and `RFC9162_SHA256` but provides neither serialized leaf
   bytes nor a concrete count-binding encoding for these JSON reports. The
   reader validates the declared closed identifier and count consistency,
   then reports `cannot-tell` about root correctness and cryptographic count
   binding. It does not guess canonical JSON, salt strings, count prefixes,
   tree padding, root construction or hash composition. Domain-separation
   flags cannot resolve this (§3.1 explicitly says they are insufficient).

2. **JSON representation.** The text has no normative JSON schema, except
   the explicitly nonnormative proposed fixture in §5.5. The allowed case
   envelopes establish a minimal adapter: `subjectType=report`, `subject`,
   and a local `resolves` map; `cause.code`, qualifier `value`/`ref`, and
   the named report fields express the corresponding prose concepts.
   Malformed JSON, duplicate JSON members and unusable envelope structures
   fail closed as `cannot-tell`, not an invented normative “schema row”.
   A missing defined semantic field such as state, cause, or fixed checker
   still receives its directly applicable textual ground. An absent optional
   roll-up does not create uncertainty; a present malformed roll-up does.

3. **Resolver boundary (§3).** `resolves` is the supplied reader-environment
   fixture. Its `sha256` is treated as the resolver's observed artifact
   digest, not as a hash of the JSON summary containing `verdict` and
   `rules`. Digest disagreement is integrity failure; absent resolution is
   unchecked and cannot trigger row 13 merely by trusting declared moved.
   This reader does not independently rerun an external pinned checker,
   fetch external artifacts, or certify the truth of the fixture. A matching
   digest is only an equality comparison across supplied reader inputs.

4. **Evidence identity and conflict (§2–§3).** No duplicate-ID or
   carry-versus-reference precedence rule is supplied. Duplicate evidence
   identifiers, even identical duplicates, are flagged `cannot-tell` and
   are never silently overwritten. Every individual object is still checked
   for direct contradictions. Conflicting carried and resolved projections
   remain unresolved; neither representation silently wins on that
   projection. Independently agreed projections remain available to decide
   their own rows, including verdict movement for row 13.
   Supported projections absent from one representation are supplied by
   the other when available; an empty or partial carried object cannot
   hide a nonconflicting digest-matching resolved projection.
   An evidence object without an adapter identifier is still evaluated for
   independently decidable form and consistency violations.

5. **Observation composition and arity (§2, §6.1, §7, O1).** The reader
   recomputes each available named projection, verdict and fired-rule list,
   independently from the supplied observations. Verdict-only comparisons
   do not require fired-rule fields. Metadata identifiers do not constitute a
   projection. The named `error list` primitive is recompute-opaque under
   §§2.1 and 6.1, and §7.1 leaves record composition to the emitter. Its
   presence in declared moved does not create a subset/equality rejection
   or require machine recomputation: no rejection row reads it. Declared
   versus recomputed moved is compared only over machine-comparable verdict
   and fired-rule projections; recomputed comparable moved must still be
   contained in compared. Other unknown observation projections remain
   undecidable; opaque strings are not reverse-engineered into rules. An unknown projection
   cannot suppress a decidable mismatch in a known projection. `compared` and `moved`
   are sets; fired-rule lists preserve their list order because no shared
   unordered-list semantics is supplied. Delta paths and concrete before/
   after differences are read, but no one-field rejection is invented.
   Optional declared arity is nonauthoritative and ignored; its mere
   presence causes neither rejection nor uncertainty. The shared definition
   of one field remains open, but no implemented row depends on it.

6. **Evidence reference on possible-not-demonstrated (§1.3, row 11).** The
   text says no value is assertable without its artifact but does not
   explicitly say whether this particular value counts as an assertion.
   Absence of its reference is marked `cannot-tell`; demonstrated and
   foreclosed without references explicitly fire row 11.

7. **Carried/referenced counter (§5.3).** The text says the counter counts
   verdict records and is “disclosure and not rejection”. The case adapter
   stores observations in evidence objects. A single verdict record using
   unshared evidence of one carriage mode does not need an ambiguous
   mapping convention. The reader flags topology uncertainty only when an
   evidence object is actually shared across verdict records or a verdict
   record uses both carried and referenced observations. Missing/invalid
   counters remain unresolved. The reader does not import an observation-
   count formula or make this disclosure a rejection row. Each individual
   carried/referenced counter must be bounded by the number of relevant
   verdict records, independently of serialization or tree construction.
   A counter exceeding this population is explicitly flagged and never
   accepted: it yields `cannot-tell` on its own because §5.3 calls the
   counter “disclosure and not rejection” and supplies no rejection rule
   for the false disclosure. The upper bound does not assume that carried
   and referenced are disjoint, so no unsupported bound on their sum is
   imposed.

8. **Completeness algorithms (§5.2).** Population kinds and empty-population
   behavior are explicit and checked. No-void has an explicit satisfaction
   formula. Execution follows the explicit “every check ran” distinction.
   Complete satisfaction algorithms for accounting and evidence
   completeness are not specified and are marked `cannot-tell` after
   checking population requirements. All four fields are not mandated:
   the requirement is conditional on asserting a claim.

9. **Control binding (§5.4, §10).** The normative text requires the same
   revision and relevant configuration/constraints. Contradictory declared
   checker/constraint bindings reject. Each component is read independently:
   a missing component cannot suppress a mismatch in another supplied
   component. Missing bindings are unresolved:
   §10 itself reports that the candidate corpus does not reject a run with
   no declared binding, while saying the text governs. Equal supplied
   fixed-slot checker and constraint/configuration identities, including
   digest identifiers, establish the declared consistency binding and have
   a successful validation path. This is not independent provenance proof.
   No §5.5 fixture requirements or
   two-party reproduction rule are imposed, because they are not normative.

10. **Prior runs (§3, §5.4).** A prior negative result must resolve and
    establish relevant check identity and revision/configuration binding.
    The available envelopes do not carry a resolved prior report that
    establishes these facts; these claims are marked unresolved. A missing
    reference or a named unrelated witness is a direct §5.4 violation.
    Missing or unusable adapter-level `check-identity` with unresolved prior
    evidence is uncertainty, not an automatic rejection; the adapter field
    is not itself a normative schema requirement.
    No undocumented prior-run resolver key convention is invented.

11. **Scope of semantic validation.** Declarations are checked for the
    contradictions that the text defines. Arbitrary free-text `detail`
    explanations are not parsed into execution events, and a state cannot
    prove that a checker actually ran. Real provenance requires the pinned
    checker and artifacts, which are outside the allowed inputs. The text
    itself notes the limits of declaration-based consistency checks (§1.2).

12. **Conformance claim (§10, O2).** The appendix's binding corpus digest
    remains open and text takes precedence. This is a frozen specification-
    only prediction artifact, not a claim of passing the normative corpus.
    The named candidate's reported outcomes in the specification were not
    used as neutral-case expectations or programmed as counts.

## Exact requirement-ground convention

`§4 row N` is the numbered rejection-table row N (1–14).
Other labels name a requirement in the cited section, not an invented
extension of that numbered table. Examples: `§2 moved subset` is the
sentence rejecting moved outside compared; `§3 reading table` is the
resolved digest mismatch; `§4 run-level completeness count` is the
paragraph following the numbered table; `§5.4 negative verdict` is its
explicit requirement that the negative observation have state `fail`.

Order invariance applies to JSON object keys, check/evidence collections,
the sides of observation comparison, compared/moved sets and delta-change
order. It does not pretend that a sequence-valued projection or tree leaf
ordering is unordered. The latter construction remains unresolved.
