# Product Roadmap 0.2

This is the product source of truth for the approved R1-R11 order. The 0.2
integration is exclusively `YASB CustomWidget -> yasb-limitora CLI / JSON v2 ->
Limitora public API`. R1-R4 are complete. R5 is the next authorized planning
unit; no R5 issue or implementation work exists yet. Later units remain out of
scope until their ordered turn.

## Delivery order

| Order | Unit | Outcome | Status |
|------:|------|---------|--------|
| R1 | Product source of truth | Correct architecture, scope, CustomWidget limits, exclusions, and roadmap order | Complete |
| R2 | Normative contract and frozen v1 tests | Specify JSON v2, acceptance criteria, structural support, and byte-for-byte v1 fixtures | Complete |
| R3 | Preserve public quota snapshots and dimensions | Preserve provider outcomes, exact public state, freshness, timestamps, quota windows, quantities, resets, plans, and safe source context | Complete |
| R4 | Migrate rich Codex helper IPC | Migrate the rich snapshot boundary through the Codex helper process | Complete |
| R5 | Project and negotiate JSON v2 | Add the accepted JSON v2 projection and explicit CLI negotiation | Next authorized planning unit |
| R6 | Add truthful presentation projection | Produce bounded compact, alternate, and tooltip fields from preserved evidence | Planned after R5 |
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
R2 passed. R3 and R4 are now delivered. R5 is the next authorized planning
unit; no R5 issue or implementation work exists yet. Later runtime, integration,
packaging, and release work must wait for each unit's ordered turn.

## Explicit exclusions for 0.2

The roadmap does not include native or upstream YASB work, fixed provider-window
assumptions, absent-as-zero behavior, Claude, Gemini, costs, tokens, history,
predictions, `usage`, or `rate_limit_reset_credits`. Later units must not be
implemented before their ordered turn.
