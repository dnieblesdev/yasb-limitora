# Product Roadmap 0.2

This is the product source of truth for the approved R1-R11 order. The 0.2
integration is exclusively `YASB CustomWidget -> yasb-limitora CLI / JSON v2 ->
Limitora public API`. R1 and R2 are the only local review units authorized in
this worktree.

## Delivery order

| Order | Unit | Outcome | Status |
|------:|------|---------|--------|
| R1 | Product source of truth | Correct architecture, scope, CustomWidget limits, exclusions, and roadmap order | This review unit |
| R2 | Normative contract and frozen v1 tests | Specify JSON v2, acceptance criteria, structural support, and byte-for-byte v1 fixtures | This review unit |
| R3 | JSON v2 runtime | Implement the accepted v2 model, projection, and CLI selection | **BLOCKED** until the R2 gate passes |
| R4 | Public Limitora quota adapter | Preserve provider outcomes, exact public state, freshness, windows, quantities, resets, plans, and safe source context | Planned after R3 |
| R5 | Execution safety | Apply the cross-process execution guard, one absolute deadline, bounded IPC, and eventual cleanup | Planned after R3 |
| R6 | v2 CLI and configuration | Add explicit v2 selection, v2-only config fallback, diagnostics, and exact exit semantics | Planned after R3 |
| R7 | Presentation projection | Produce bounded compact/alternate/tooltip text and the per-provider depleted-window heuristic | Planned after R4 |
| R8 | Deterministic fixture integration | Exercise the real CLI seam with partial, stale, window changes, invalid JSON, and overlap fixtures | Planned after R4-R6 |
| R9 | Pinned YASB validation | Validate real YASB CustomWidget v2.0.5 deterministically, then run separate live-provider smoke | Planned after R7-R8 |
| R10 | Packaging and installed-artifact proof | Verify package contents, pinned runtime dependencies, and native Windows distribution behavior | Planned after R9 |
| R11 | Release readiness | Final security, reliability, acceptance, documentation, and technical review gate | Planned after R10 |

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
- The R1-R11 order and the R3 block are visible from this document.
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

Until this gate passes, the product state is **R3 BLOCKED**. No runtime v2
implementation, implementation issue, branch, commit, or release work is
authorized by R1 or R2.

## Explicit exclusions for 0.2

The roadmap does not include native or upstream YASB work, fixed provider-window
assumptions, absent-as-zero behavior, Claude, Gemini, costs, tokens, history,
predictions, `usage`, `rate_limit_reset_credits`, or R3 implementation before
the R2 gate.
