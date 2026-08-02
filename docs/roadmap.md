# Product Roadmap 0.2

This is the product source of truth for the approved R1-R11 order. The 0.2
integration is exclusively `YASB CustomWidget -> yasb-limitora CLI / JSON v2 ->
Limitora public API`. R1-R5 are complete. R6 is the next authorized planning
unit; later units remain out of scope until their ordered turn.

## Delivery order

| Order | Unit | Outcome | Status |
|------:|------|---------|--------|
| R1 | Product source of truth | Correct architecture, scope, CustomWidget limits, exclusions, and roadmap order | Complete |
| R2 | Normative contract and frozen v1 tests | Specify JSON v2, acceptance criteria, structural support, and byte-for-byte v1 fixtures | Complete |
| R3 | Preserve public quota snapshots and dimensions | Preserve provider outcomes, exact public state, freshness, timestamps, quota windows, quantities, resets, plans, and safe source context | Complete |
| R4 | Migrate rich Codex helper IPC | Migrate the rich snapshot boundary through the Codex helper process | Complete |
| R5 | Project and negotiate JSON v2 | Add the accepted JSON v2 projection and explicit CLI negotiation | Complete |
| R6 | Refine truthful presentation projection | Produce bounded compact, alternate, and tooltip fields from preserved evidence | Next authorized planning unit |
| R7 | Resolve default Windows configuration | Add the accepted default Windows configuration resolution | Planned after R6 |
| R8 | Add the cross-process execution guard | Add bounded guard acquisition, deadlines, and cleanup behavior | Planned after R7 |
| R9 | Package CustomWidget examples and static CSS | Package the CustomWidget examples and static presentation assets | Planned after R8 |
| R10 | Prove pinned YASB integration on Windows | Validate the pinned YASB CustomWidget integration on Windows | Planned after R9 |
| R11 | Release and smoke-test 0.2.0 | Complete release readiness and the final smoke test | Planned after R10 |

## Official architecture

YASB uses the existing `CustomWidget`; it does not load a native
`yasb-limitora` widget. The CLI is the sole process boundary. Limitora remains
the only owner of provider logic and authentication.

CustomWidget 0.2 supports compact and alternate labels, multiline tooltips,
static CSS, periodic refresh, and manual/callback refresh. It does not support
dynamic state CSS, an intermediate refreshing result, a native popover or tabs,
interactive progress, or termination of a running YASB subprocess. Roadmap
units must not promise those capabilities.

## R1 acceptance

- The repository claims CustomWidget as the official integration path.
- Native YASB widget work, upstream contribution, maintainer approval, official
  extension research, and native popover work are removed from expected
  roadmap scope.
- Limitora remains a public-API dependency only.
- The R1-R11 order and completed R1-R3 units are visible from this document.
- Immutable Open Design exports are not changed.

## R2 acceptance gate

R2 is accepted only when all of the following are reviewable and passing:

- The English normative JSON v2 specification closes the requirements in
  [`docs/specifications/json-v2.md`](specifications/json-v2.md).
- The structural support file is valid JSON and agrees with the documented
  envelope and closed vocabularies.
- The v1 golden fixtures compare exact UTF-8 bytes, including the terminating
  newline, for success, unavailable, safe-error, and Unicode-label cases.
- Acceptance criteria are traceable to schema, tests, or a documented manual
  proof.
- A final technical review confirms the R2 contract does not require R3 code to
  be present.

This gate passed before R3 implementation began, so R3 remained blocked until
R2 passed. R3, R4, and R5 are now delivered. Later runtime, integration,
packaging, and release work must wait for each unit's ordered turn.

## R5 closeout

R5 is complete through merged implementation PRs #63, #66, and #68 under
parent issue #61. The delivered boundary is an isolated, schema-complete JSON
v2 projection over preserved evidence, with deterministic bounded UTF-8
serialization, required bounded presentation fields, safe mappings and
redaction, and explicit `--output-version 2` / `--output-version=2`
negotiation. Selector-free and explicit-v1 invocation remain frozen,
including exact bytes, configuration forms, streams, exits, and no-default
configuration behavior.

Final evidence is 59 focused tests passed; 265 full-suite tests passed with 4
skipped; native-proof succeeded for all three implementation PRs; and no
critical findings or warnings were reported. R6 is the next authorized planning
unit for presentation refinement. This closeout authorizes R6 planning only;
it does not imply R6 implementation, R7 default-configuration resolution, or
R8 execution guard, deadline, and cleanup machinery.

## Explicit exclusions for 0.2

The roadmap does not include native or upstream YASB work, fixed provider-window
assumptions, absent-as-zero behavior, Claude, Gemini, costs, tokens, history,
predictions, `usage`, or `rate_limit_reset_credits`. Later units must not be
implemented before their ordered turn.
