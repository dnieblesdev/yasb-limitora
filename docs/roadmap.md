# Product Roadmap 0.2

This is the product source of truth for the approved R1-R11 order. The 0.2
integration is exclusively `YASB CustomWidget -> yasb-limitora CLI / JSON v2 ->
Limitora public API`. R1-R10 are complete. R6 implementation and runtime
verification are complete at the exact pre-closeout integration candidate
`352e8f03c4f877a877de8b2e0b2d3b10e815fa27`; final publication is merged to
`main` at `30c94d00f780b597644c1494833d4dd50738556b`.
Later units remain out of scope until their ordered turn.

The complete `yasb-limitora` runtime is Windows-only. Both public CLI routes
share one early boundary: on non-Windows they return `2`, emit exactly
`yasb-limitora: unsupported_platform\n` on stderr, and emit no stdout bytes
before any product execution. Hermetic predicate injection in tests is not
runtime portability or Windows integration proof.

## Delivery order

| Order | Unit | Outcome | Status |
|------:|------|---------|--------|
| R1 | Product source of truth | Correct architecture, scope, CustomWidget limits, exclusions, and roadmap order | Complete |
| R2 | Normative contract and frozen v1 tests | Specify JSON v2, acceptance criteria, structural support, and byte-for-byte v1 fixtures | Complete |
| R3 | Preserve public quota snapshots and dimensions | Preserve provider outcomes, exact public state, freshness, timestamps, quota windows, quantities, resets, plans, and safe source context | Complete |
| R4 | Migrate rich Codex helper IPC | Migrate the rich snapshot boundary through the Codex helper process | Complete |
| R5 | Project and negotiate JSON v2 | Add the accepted JSON v2 projection and explicit CLI negotiation | Complete |
| R6 | Refine truthful presentation projection | Produce bounded compact, alternate, and tooltip fields from preserved evidence | Complete — merged to `main` at `30c94d0` |
| R7 | Resolve default Windows configuration | Add the accepted default Windows configuration resolution | Complete — merged to `main` at `2850169` |
| R8 | Add the cross-process execution guard | Add bounded guard acquisition, deadlines, and cleanup behavior | Complete — merged to `main` at `5bee184` |
| R9 | Package CustomWidget examples and static CSS | Package the CustomWidget examples and static presentation assets | Complete — merged to `main` at `2d529ae` |
| R10 | Prove pinned YASB integration on Windows | Validate the YASB CustomWidget integration on Windows | Complete — automated native CLI/JSON proof plus maintainer manual YASB acceptance |
| R11 | Release and smoke-test 0.2.0 | Complete release readiness and the final smoke test | Next, gated by #130 and the released Limitora dependency/manual OpenCode acceptance |

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
critical findings or warnings were reported. At the time of this R5 closeout,
R6 was the next authorized planning unit for presentation refinement. The R6
closeout is recorded below; R7 default-configuration resolution and R8
execution guard, deadline, and cleanup machinery remain future work.

## R6 closeout

R6 runtime implementation is complete on the exact pre-closeout integration
candidate `352e8f03c4f877a877de8b2e0b2d3b10e815fa27`. The closeout consists of
the three original reviewed slices plus final-review fix child PR #79, followed
by post-merge integration verification:

- The contract slice, commit `9ff3be2`, published the normative presentation
  grammar, mappings, bounds, and contract tests.
- The runtime slice, commit `8914881`, implemented the evidence-only,
  provider-local projection and focused runtime/v1 proof.
- The roadmap closeout slice, commit `00a395e`, recorded the verified
  integration state without claiming publication to `main`.
- Final-review fix child PR #79, commit `c10f52ce`, corrected the near-cap
  presentation-boundary regression so valid 65,535- and 65,536-byte provider
  snapshots retain canonical evidence while irreducible over-cap payloads
  retain the document-level `internal_error` fallback.
- The integration candidate `352e8f03c4f877a877de8b2e0b2d3b10e815fa27`
  preserves the final-review child commit `c10f52ce` source/contract/focused-
  test trees with no merge drift, while earlier slices remain in ancestry. The
  R6 implementation scope remains four files:
  `docs/specifications/json-v2.md`, `tests/test_json_v2_spec.py`,
  `src/yasb_limitora/projection_v2.py`, and
  `tests/test_json_v2_projection.py`; the roadmap closeout is recorded in this
  document.

Post-merge evidence at that candidate is 61 focused tests passed; 282
full-suite tests passed with 4 skipped; `py_compile`, `compileall`, and
`git diff --check` passed; and all 9 required R6 scenarios are compliant.
Canonical v2 schema/model ordering and frozen v1 output remain unchanged, and
no R7+ behavior is included.

This entry records the verified integration boundary and its subsequent
publication to `main`. Post-`352e8f03` history is not uniformly non-runtime:
child commit `023e65d` changed runtime identity rendering plus its
specification and focused tests. Its runtime/contract/test tree was integrated
and verified at `d562e04`, with 62 focused tests passed and 283 full-suite tests
passed with 4 skipped. Later roadmap-only provenance corrections are docs-only; they do not
alter the already-verified runtime/contract/test tree or make a
self-referential final-head claim. Optional Full-4R R2-002 (the unreachable
snapshot fallback) and R2-003 (the long positional presentation helper) are
non-blocking and wont-fix for this closeout; neither is addressed here.
PR #75 was merged to `main`; the final `main` HEAD is
`30c94d00f780b597644c1494833d4dd50738556b`. Tracker #37 was updated with the
R6 completion comment, and the applicable R6 issues (#70, #71, #73, #76, #78,
#80, #82, #84, and #86) were closed. R7 remained unstarted at that point.

## R7 closeout

R7 is complete through issue #89 and merged implementation PR #90 under parent
tracker #37. The delivered boundary is v2-only configuration resolution with
explicit precedence, fail-closed configuration errors, safe diagnostics, and
frozen v1 behavior.

- Issue #89 defined and approved the R7 child work with `status:approved`.
- PR #90, merged to `main` at `2850169`, contains commits:
  - `a1e7f1b` — `feat(cli): resolve v2 Windows configuration sources`;
  - `23cc45a` — `test(cli): prove v1 and runtime configuration compatibility`;
  - `a9559a5` — `test(windows): add native default-path read proof`;
  - `2f6fcc8` — `docs(windows-json): document v2 config resolution`.
- The accepted v2 precedence is: explicit `--config`/`-c`, then non-empty
  `YASB_LIMITORA_CONFIG`, then `%LOCALAPPDATA%\\yasb-limitora\\config.json`.
- Empty or whitespace-only `YASB_LIMITORA_CONFIG`, absent/empty/whitespace
  `LOCALAPPDATA`, and selected missing/unreadable/invalid files all fail closed
  as `configuration_invalid` with exit `2`. No fallback, auto-creation,
  migration, or file mutation occurs.
- v1 selector-free and explicit-v1 invocations continue to ignore
  `YASB_LIMITORA_CONFIG` and `%LOCALAPPDATA%`, preserving exact bytes, streams,
  exits, and explicit-config forms.
- Diagnostics remain redacted: stdout is the versioned safe envelope; stderr
  contains only the fixed taxonomy token; no path, environment value, file
  content, credential, workspace ID, or runner path is emitted.
- Bounded I/O, device/UNC rejection, path canonicalization, 32,767 UTF-16 length
  cap, 16,384-byte file-size bound, cross-process guard, deadlines, locks, and
  cleanup remain deferred to R8.

Post-merge evidence is 293 full-suite tests passed with 5 skipped (the 5 skips
are the existing native Windows proofs that run only on Windows); focused CLI,
v1 golden-fixture, runtime, and Windows-native-proof tests all pass;
`compileall` and `git diff --check` pass; and the diff is 292 insertions and
25 deletions across 6 files, within the 400-line review budget.

Tracker #37 was updated to mark R7 complete, and issue #89 was closed. R8 is
the next authorized unit; it is not started and its scope (cross-process
execution guard, deadlines, and cleanup) was not introduced by R7.

## R8 closeout

R8 is complete through issue #92 and merged implementation PRs #93-#103 under
parent tracker #37. The delivered boundary is v2-only execution safety: a
cross-process execution guard, one absolute CLI-entry deadline, and bounded v2
configuration path/file limits.

- Issue #92 defined and approved the R8 child work with `status:approved`.
- Implementation PRs, all merged to `main`:
  - PR #93, merged at `80cb9fc` — v2 deadline context, `deadline_seconds`
    grammar, and lexical path canonicalization (slice A).
  - PR #94, merged at `03d41a8` — bounded v2 local-file I/O (slice B).
  - PR #95, merged at `c2890ad` — opaque named Win32 mutex guard (slice C).
  - PR #96, merged at `c730dd3` — guarded worker integration, result
    model/projection matrices, and cleanup-complete predicate (slice D).
  - PR #97, merged at `4c11ece` — native two-process/abandonment proof and the
    zero-skip workflow gate (slice E).
  - PR #98, merged at `4e28b45` — absolute deadlines threaded through the v2
    transport/protocol (remediation round 1).
  - PR #99, merged at `2669457` — v2 supervisor/helper and Job cleanup deadline
    propagation (remediation round 1).
  - PR #100, merged at `a3390a6` — worker boundary, cleanup ordering, bounded
    I/O, and native sentinel remediation (remediation round 1).
  - PR #101, merged at `dc84a37` — v1 explicit device retention and integrated
    v2 runtime matrices (remediation round 2).
  - PR #102, merged at `5087c08` — closeout Judgment Day round 1 severity
    fixes.
  - PR #103, merged at `5bee184` — closeout Judgment Day round 2 fixes
    (JDC-B-003 end-to-end, stale-supervisor cleanup, descriptor closure).
- The delivered v2 boundary: the guard scope is the opaque SHA-256 hash of the
  process-token SID bytes plus the canonical effective configuration path in a
  `Global\\` named mutex; acquisition uses `CreateMutexW` and a bounded
  `WaitForSingleObject(min(250ms, remaining-after-reserve))`; `WAIT_OBJECT_0`
  and `WAIT_ABANDONED` establish ownership, timeout maps to
  `guard_wait_timeout`, and create/open/identity failure to
  `guard_acquisition_failed`; the owner always attempts release and handle
  close in an outer `finally`, and a release/close fault maps to sanitized
  `cleanup_failed` while preserving provider outcomes. The absolute `T0`
  deadline starts at CLI entry and is never reset; providers run behind a hard
  worker-process/Job boundary, so a provider not started at expiry is
  `not_run: deadline_exhausted` and a started overrun is `provider_timeout`.
  v2 configuration paths are canonicalized lexically
  (`GetFullPathNameW`-equivalent, no existence/network lookup), device and UNC
  paths are rejected before open, normalized paths are capped at 32,767 UTF-16
  code units, and the selected file must be a regular local file of at most
  16,384 UTF-8 bytes read through a bounded 16,385-byte probe.
- v1 remains byte-for-byte frozen: CLI bytes, streams, exits, selectors, and
  explicit-config behavior are unchanged; v1 never enters the R8 deadline,
  guard, or canonicalization paths.
- Post-merge evidence is 354 full-suite tests passed with 8 skipped (the 8
  skips are the Windows-native proofs that run only on Windows), exit 0, with
  the v1 golden fixtures byte-frozen; the native "Windows proof" workflow run
  `31159008178` concludes `success` at `5bee184` with zero skipped proof tests
  and checkpoint 9 satisfied.
- No new dependency was added (`pyproject.toml` unchanged) and no schema or
  specification edit was made (`docs/specifications/*` unchanged).

Issue #92 is closed. The parent tracker #37 records this completion during the
orchestrator closeout. R9 followed as the next authorized unit and is now
closed out below; its scope (packaging the CustomWidget examples and static
CSS) was not introduced by R8.

## R9 closeout

R9 is complete through approved child issue #105 and merged PRs #106, #107,
and #108 under parent tracker #37. The delivered boundary is additive,
copy-ready YASB v2.0.5 CustomWidget YAML, static CSS, English documentation,
eleven JSON v2 validation fixtures, and deterministic tests. No runtime,
provider, guard, JSON-v2 contract, packaging, R10, or R11 behavior changed.

- PR #106 delivered the baseline YAML, CSS, README, and seven fixtures.
- PR #107 delivered four edge fixtures, exact semantic/runtime metadata tests,
  and the fixture LF checkout rule.
- PR #108 corrected the final fixture semantics: all-snapshot partial and
  missing-data documents use `execution_state: complete`, while stale
  presentation uses `public_state=available` with `freshness=stale`.
- Verified R9 artifact HEAD: `2d529ae5d436608a5625edde0d79003940d9eedf`.
- R9 documentation closeout PR #109: `d9d7b93dfde06f76c22b385063054807a2047b9b`.
- R9 closeout-record correction PR #110: `a75c7d49a4300c9d86e090f2406fed98779eaf59`.
- Final SDD verification passed all 4 requirements and 5 scenarios. Focused
  tests passed 8; the full suite passed 362 with 8 skipped and 4 warnings.
  Native repository proof run `31278200496` passed 9 selected checks and the
  full Windows suite (370 passed). This is repository/native proof, not R10
  real YASB or live-provider proof.
- Planning, Slice A, Slice B, and final fixture Judgment Day gates are
  approved after bounded corrections, with no open BLOCKER or CRITICAL.

## R10 closeout

R10 is complete through approved parent issue #124, merged implementation PRs
#128 and #131, and the maintainer's manual acceptance record. The closeout has
two explicit proof boundaries, and makes no automated YASB rendering claim:

- Automated native Windows proof owns the installed `yasb-limitora` CLI and JSON
  v2 contract. PR #128 established the native contract boundary at merge
  `a1e25a8`. PR #131 fixed the live Codex execution boundary at merge
  `2254c66`; native CI run [31660883600](../../actions/runs/31660883600)
  passed the selected 10 checks and the full suite (379 passed, 4 skipped),
  retained checkpoint 9, and confirmed clean process-tree termination and
  streams.
- Real YASB behavior was accepted manually by the maintainer in [#124](../../issues/124#issuecomment-5275489518)
  using YASB v2.0.6, an accepted minor-version deviation from the original
  v2.0.5 plan. Primary label, alternate label, multiline tooltip, static CSS,
  120-second refresh, and disabled fallback all passed from a clean `main`
  installation. The final configuration returned both providers to disabled.

This closeout does not claim automated YASB rendering, an external YASB E2E
harness, or OpenCode real-provider acceptance. The earlier unsupported
automation harness remains historical context only. OpenCode Bearer API
migration #130 is the next R11 dependency and must be completed and manually
accepted in real YASB before R11 release readiness; #62 remains the broader
release and smoke-test gate.

## Current gate

R1-R10 are complete. R11 is next, gated by the released Limitora 0.2.0 dependency,
approved OpenCode migration #130, and separate manual OpenCode acceptance in a
real YASB installation. No R11 release claim is made here.

## Explicit exclusions for 0.2

The roadmap does not include native or upstream YASB work, generic fixed
provider-window assumptions, absent-as-zero behavior, Claude, Gemini, costs,
tokens, history, predictions, `usage`, or `rate_limit_reset_credits`. The
approved OpenCode 0.2 contract is the explicit fixed-slot exception: its
`available` and `partial` snapshots use `five_hour`, `monthly`, and `weekly`
commercial slots, while `rate_limited` is technical-only. Limitora #55's
v0.3.0 per-window signal is upstream context and is not consumed until
yasb-limitora #133. Later units must not be implemented before their ordered
turn.
