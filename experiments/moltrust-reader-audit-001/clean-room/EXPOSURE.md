# Clean-room exposure record

The sole external task inputs allowed to this implementation are
the original temporary bundle's `SHA256SUMS`, `specification-v0.1.txt`, and
the neutral case JSON files named in that manifest under `cases/`.

Before reading the specification or cases, `shasum -a 256 -c SHA256SUMS`
succeeded for every listed input (166 files). The full per-file hash record
is preserved without modification as `INPUT-SHA256SUMS`.

- SHA256SUMS SHA-256: `585954b74ac5bfe4809cc59d3878e7949d40d9a963a853f1c0fab4fbb1665823`
- specification-v0.1.txt SHA-256: `8b0e9f66a1cc1ee5df3922e4057552dd365a927969ff79759fe43bf2aa418e3f`

The implementation workspace is the newly created directory
`/tmp/w3c-reader-clean.u8eJDp`. Only the permitted input bundle and files
created in this workspace will be inspected. No network requests, existing
repositories, other temporary directories, external implementation code,
expected outcomes, comparison data, or oracle files will be accessed.

The task instructions are procedural authority; the specification is the
sole authority for conformance behavior. Neutral case filenames are output
identifiers only. No case-specific verdicts, case IDs, or outcome counts
will be embedded in the reader or tests.

This record was created before reading the specification or case contents.
Any later exposure deviation must be appended explicitly before freezing.

## Final exposure audit

The permitted specification and all manifest-listed neutral case files
were read. `inspect_inputs.py` inventories only their representations;
`test_bundle.py` checks only their determinism and permutation properties.
No expected-verdict file, oracle, implementation repository, external
website, or comparison output was opened. No exposure deviation occurred.

Standard local Python, Git, SHA-256 and shell utilities were used as
execution infrastructure; no source or configuration of an external
implementation was inspected. Git initialization/commit commands disable
global/system configuration and templates. Final Python commands disable
environment overrides and site startup customization.

Exposure-sensitive work stops at the freeze commit. Subsequent oracle
comparison, if any, belongs to a separate reader and must not alter this
implementation or its recorded predictions.

## Authorized specification-only revision

The original freeze is retained at commit
`22fadbcd0126b66935a420b0e305e9619fe25f47`. After that freeze, the parent
authorized a revision using the same sanitized inputs and seven
specification-only review findings. Those findings are summarized in
`REVIEW-TDD.md`; they contained no neutral-case outcomes or comparison data.
The revision read only the previously permitted bundle and files created
inside this workspace. No oracle, comparison file, external implementation,
other temporary directory, or network source was accessed. The input
manifest and specification hashes remain unchanged.

## Further authorized specification-only revision

The second freeze is retained at commit
`d05b0d333927c084859e58b777988416d17c26cb`. The parent authorized four
further specification findings: independent checks of partial control
bindings, preservation of agreed observation projections despite a separate
projection conflict, and upper bounds on verdict-record disclosure counts.
The message identified a count already present in one allowed neutral input;
it did not provide an oracle verdict or comparison result. The final test
selects every applicable supplied input by its structural population bound,
not by a hardcoded case identifier. Only the same allowed bundle and this
workspace were read. No network, external implementation, oracle or
comparison data was accessed. The initial input hashes remain unchanged.

## Final authorized partial-carriage revision

The third freeze is retained at commit
`7fdc252c81692193e69c08da0d7eb0ef0fcad3a3`. The parent supplied one
additional specification-only finding: an empty or partial carried object
must not hide a nonconflicting projection in a digest-matching resolution.
The regression uses only synthetic data. The same original sanitized bundle
was used for regeneration and verification. No additional source, oracle,
comparison data, external implementation, or network was accessed.

## Authorized opaque-primitive revision

The fourth freeze is retained at commit
`c75beb06db71af7f9dd519bdf80cdb8bad7f0095`. On the parent's
specification-only instruction, lines 152–188 and 558–588 of the same
allowed specification were reread. They establish the recompute-opaque
error-list primitive, which no rejection row reads, and emitter-defined
record composition. Two synthetic regression tests were added before code
changes. Only the same permitted inputs and this workspace were accessed;
no oracle, comparison result, external implementation, or network source
was consulted.

## Post-freeze packaging

After the independent freeze and comparison were complete, the exact input
bundle was copied to the adjacent `inputs/` directory. Four temporary-path
references in tests and verification helpers were changed to repository-
relative paths. No reader decision logic, input byte, prediction, count, or
pre-comparison exposure claim was changed. The original independent freeze
is commit `24c54f14824f6a802572786ff6f7a58db341d760` in its isolated repository.
