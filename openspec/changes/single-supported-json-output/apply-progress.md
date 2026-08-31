# Apply Progress: Semantic Slice 1 remediation

## Status

- **Change:** `single-supported-json-output`
- **Slice:** Semantic 1 — in-place contract/projection/cache compatibility
- **Branch:** `feature/137-json-contract-projection`
- **Base:** `feature/137-json-budget-repartition`
- **Remediation evidence:** `sha256:f364e65fe3237601c00e0a7d9766041859d9608a28b5ad9cf266a2315f71bcc5`
- **Delivery boundary:** feature-branch-chain / auto-chain; one local commit only, no push or PR
- **Provider/no-rename budget:** 141 semantic additions + deletions versus the base (205 including the 4 task lines and 60-line progress artifact); limit 400

## Completed tasks

- Updated current projection expectations for the exact root order `execution_state`, `execution_error`, `providers` with no root `version`.
- Removed root `version` from normal and document-failure projections in `projection_v2.py`.
- Updated the current schema and normative examples in place; retained v2 filenames and selector/v1 guidance for later slices.
- Updated all current CustomWidget JSON fixtures to the three-root contract.
- Set `CACHE_SCHEMA = 3`, removed cache root-version coupling, and retained cache filename, envelope order, single-flight behavior, public-only validation, bounds, and immutable identity strings.
- Added coverage for schema-2 cold miss/refresh and rejection of an inserted current-payload root `version`.
- Updated dependent v2-route assertions while preserving v1 output expectations.
- Marked only the completed RED and accounting checklist items in `tasks.md`.

## TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Updated dependent tests before production edits; `python -m pytest -q tests/test_json_v2_projection.py tests/test_json_v2_spec.py tests/test_contracts.py tests/test_v2_cache.py tests/test_cli_output_version.py tests/test_runtime_cli.py tests/test_customwidget_examples.py` | **35 failed, 232 passed**; failures were the expected root-version/schema-2 contract mismatches |
| GREEN | Implemented projection root removal, schema-3 cache contract, schema/docs/fixture updates, and dependent expectation changes | Focused dependent suite: **267 passed** |
| TRIANGULATE | Re-ran the complete required dependent file list after boundary and cache-corruption expectation updates | **267 passed** |
| TRIANGULATE / collection | `python -m pytest -q --collect-only` | **605 tests collected**, 0 collection errors |
| REFACTOR / diagnostics | `ruff check` on changed Python files only; compared with `HEAD` versions | No newly introduced Ruff findings. Existing findings in unchanged surrounding code remain out of scope. |

## Files changed

- `src/yasb_limitora/projection_v2.py`
- `src/yasb_limitora/v2_cache.py`
- `docs/specifications/json-v2.md`
- `docs/specifications/json-v2.schema.json`
- `examples/customwidget/fixtures/*.json`
- Required dependent tests under `tests/`
- `openspec/changes/single-supported-json-output/tasks.md`
- `openspec/changes/single-supported-json-output/apply-progress.md`

## Deviations from design

- No module, symbol, selector, CLI routing, v1 path, or physical filename was renamed or deleted. This is required by the Semantic Slice 1 boundary; CLI current-only routing and normalization remain follow-up slices.
- The existing v2 normative filenames and v2 implementation symbols remain unchanged.
- Byte-boundary test values were reduced by 12 bytes to reflect removal of the serialized `version` member.

## Remaining tasks

- Semantic 2: current-only CLI/configuration routing and cache integration cleanup.
- Semantic 3: bounded runtime cleanup and legacy-path removal.
- Semantic 4: current-only examples and active documentation.
- Later mechanical rename exception slices and final full/native verification.

## Workload / PR boundary

This attempt is limited to the contract/projection/cache compatibility slice on the current chain branch. It remains below the 400-line provider/no-rename budget. No commit has been created yet; commit only after the required verification remains green.

## Progress: bounded v1 golden artifact deletion child

### Status

- **Slice:** Semantic 3 prerequisite — remove v1-only golden tests and fixtures
- **Branch:** `feature/137-json-remove-v1-fixtures`
- **Base:** `feature/137-json-contract-projection`
- **Delivery boundary:** feature-branch-chain / auto-chain; one local commit only, no push or PR
- **Provider/no-rename budget:** 231 test/artifact changed lines versus the base; 280 including 3 task lines and 51 progress lines, below the 400-line limit

### Completed tasks

- Added a repository-hygiene assertion in `tests/test_contracts.py` covering the v1-only golden test path and `tests/fixtures/json_v1_*.json` paths.
- Deleted `tests/test_v1_golden_fixtures.py` and the four dedicated `tests/fixtures/json_v1_*.json` files.
- Left legacy production projection/coordinator code and all explicitly protected CLI, export, example, and active documentation surfaces unchanged.
- Marked only this bounded legacy-deletion child complete in `tasks.md`.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | `python -m pytest -q tests/test_contracts.py::test_v1_golden_artifacts_are_absent` while the v1 artifacts existed | **1 failed** on the existing `tests/test_v1_golden_fixtures.py` path |
| GREEN | Deleted only the v1 golden test and dedicated fixture files; reran the focused assertion | **1 passed** |
| TRIANGULATE | `python -m pytest -q tests/test_contracts.py` | **45 passed** |
| TRIANGULATE / collection | `python -m pytest -q --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR | Reviewed the bounded diff and confirmed no protected runtime/CLI/example/docs surfaces changed | No additional changes required |

### Files changed in this child

- `tests/test_contracts.py`
- `tests/test_v1_golden_fixtures.py` (deleted)
- `tests/fixtures/json_v1_safe_error.json` (deleted)
- `tests/fixtures/json_v1_success.json` (deleted)
- `tests/fixtures/json_v1_unavailable.json` (deleted)
- `tests/fixtures/json_v1_unicode_label.json` (deleted)
- `openspec/changes/single-supported-json-output/tasks.md`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None. This child intentionally does not remove legacy production projection/coordinator code or alter CLI behavior, exports, examples, active docs, or protected names.

### Remaining tasks

- Continue the remaining Semantic 3 runtime cleanup children and later current-only examples/docs and rename exception slices.
- Run the final full strict-marker suite and native Windows proof at the designated final verification boundary.

### Workload / PR boundary

This is one bounded deletion-only prerequisite child under the feature-branch chain. The provider/no-rename diff is 231 test/artifact changed lines versus the base (280 including task/progress artifacts), within budget. One local commit is authorized after verification; no push or PR.

## Progress: Semantic 1B native-version consumers

### Status

- **Slice:** Semantic 1B — update native proof consumers for the removed root `version`
- **Branch:** `feature/137-json-cli-cache`
- **Base:** `4e9fd29`
- **Delivery boundary:** feature-branch-chain / auto-chain; one local commit only, no push or PR
- **Provider/no-rename budget:** tiny test-only correction, well below the 400-line semantic limit

### Completed tasks

- Updated the two Windows native current-contract assertions to require the three-root document without a public `version` field.
- Preserved CLI invocation arguments and all production behavior; no source, fixture, rename, or unrelated test changes were made.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Independent verification on committed base `4e9fd29`: `python -m pytest -q` | **2 failed, 119 passed, 4 skipped**; both failures were the native default/launcher root `version` expectations; collection was clean at 590 |
| GREEN | Updated only `tests/test_windows_native_proof.py` after the recorded RED | `python -m pytest -q --strict-markers tests/test_cli_output_version.py tests/test_cli_platform_boundary.py tests/test_runtime_cli.py tests/test_v2_worker.py tests/test_windows_native_proof.py` → **121 passed, 4 skipped** |
| TRIANGULATE | `python -m pytest -q --strict-markers --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR | Reviewed the focused diff and protected edit surfaces | No additional changes required |

### Files changed

- `tests/test_windows_native_proof.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None. This correction only migrates native proof consumers to the already-implemented three-root contract and does not change CLI behavior or production code.

### Remaining tasks

- Continue the remaining Semantic 2/3/4 implementation and later rename-exception slices.
- Run the final full strict-marker suite and native Windows proof at the designated final verification boundary.

### Workload / PR boundary

This is the assigned Semantic 1B consumer correction: one focused test/progress work unit, far below the 400-line budget. Commit locally after verification; do not push, open, or merge a PR.

## Progress: v2 cache typing blocker slice

### Status

- **Slice:** Mandatory auxiliary Pyright diagnostic remediation in `v2_cache.py`
- **Branch:** `feature/137-json-cache-typing`
- **Base:** `feature/137-json-cli-cache` at `2094ec0`
- **Delivery boundary:** feature-branch-chain / auto-chain; assigned blocker work-unit slice, no commit, push, PR, or rename
- **Provider/no-rename budget:** 101 additions + 51 deletions in the permitted source file; below the 400-line slice limit

### Completed tasks

- Narrowed validated cache text, quantity units, window identity fields, provider keys/outcomes, source IDs, presentation metadata, and snapshot metadata at their validation boundaries.
- Added small structural Protocols for key leases/guards so cleanup calls are typed without changing the lifecycle contract.
- Narrowed the process-token owner result, made the refresh-marker read's existing missing-file result explicit, and initialized the Windows cleanup handle before the guarded call.
- Narrowed marker owner PID before comparison; cache schema 3, three-root document handling, canonical bytes, bounds, security checks, single-flight, cleanup, deadlines, and persisted identities are unchanged.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Supplied automated diagnostic list reporting 22 auxiliary Pyright errors in `v2_cache.py`; local `pyright` executable/module was unavailable | Type-narrowing blockers reproduced by the parent gate; authoritative LSP remains pending |
| GREEN | Added precise local annotations/helpers/Protocols only at already-validated boundaries | Parent authoritative LSP: primary clean and no auxiliary findings; runtime behavior unchanged |
| TRIANGULATE | `python -m pytest -q tests/test_v2_cache.py tests/test_runtime_cli.py` | **91 passed** |
| REFACTOR | `python -m py_compile src/yasb_limitora/v2_cache.py` and `git diff --check` | Passed; no unrelated files changed |
| LINT | `ruff check src/yasb_limitora/v2_cache.py` before and after the slice | Existing findings decreased from 29 to 25; no new Ruff findings introduced |

### Files changed

- `src/yasb_limitora/v2_cache.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None. This is a typing-only blocker remediation; no tests, CLI, docs, names, schema values, or persisted identities were modified.
- The repository's standalone Pyright command was unavailable; parent authoritative LSP supplied the required primary and auxiliary diagnostic evidence.

### Remaining tasks

- Continue remaining SDD semantic/rename slices after this blocker is accepted.

### Workload / PR boundary

This is the assigned `feature/137-json-cache-typing` blocker slice under the auto-chain delivery path. It stays below 400 changed provider/no-rename lines and is intentionally left uncommitted for the parent.

## Progress: JSON worker lint blocker slice

### Status

- **Slice:** Mandatory diagnostic remediation in `v2_worker.py`
- **Branch:** `feature/137-json-worker-lint`
- **Base:** `feature/137-json-cache-typing` at `d238394`
- **Delivery boundary:** feature-branch-chain / auto-chain; assigned work-unit slice, no commit, push, PR, or rename
- **Provider/no-rename budget:** 158 additions + 120 deletions in the permitted source file; below the 400-line slice limit

### Completed tasks

- Sorted imports and moved `Callable` to `collections.abc`.
- Replaced the bootstrap devnull open with managed lifetime handling and explicit safe fallbacks.
- Replaced swallowed cleanup `try`/`except` paths with captured-call fallback state while preserving retry ownership and cleanup ordering.
- Replaced constant `setattr` cleanup markers with direct assignment under reviewed suppression and combined nested conditionals.
- Changed the invalid process PID failure to `TypeError`, matching the diagnostic without changing fail-closed behavior.
- Preserved child authorization, job/process/queue/Event closure order, shared deadlines, bounded cleanup, retained owners, and frozen Windows spawn behavior.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | `ruff check src/yasb_limitora/v2_worker.py` before edits | **42 findings**, including I001, UP035, SIM115, S110/BLE001 cleanup paths, B010, SIM102, and TRY004 |
| GREEN | Refactored only `src/yasb_limitora/v2_worker.py` and reran Ruff | `ruff check src/yasb_limitora/v2_worker.py` → **All checks passed** |
| TRIANGULATE | `python -m pytest -q tests/test_v2_worker.py tests/test_runtime_cli.py tests/test_windows_native_proof.py` | **58 passed** |
| TRIANGULATE / collection | `python -m pytest -q --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR | `git diff --check` and final Ruff run; focused worker suite rerun after cleanup indentation correction | Passed; worker suite **21 passed**; no noqa/type-ignore added |

### Files changed

- `src/yasb_limitora/v2_worker.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None. The worker lifecycle and safety design remains unchanged; the implementation uses a small captured-call helper to express ordinary exception fallbacks without empty handlers or broad diagnostic suppressions.
- The focused command included `tests/test_windows_native_proof.py`; it completed with 58 passed and no reported skips.

### Remaining tasks

- Parent authoritative LSP/lens diagnostics passed: primary clean and no auxiliary findings.
- No source or test changes remain assigned in this slice.

### Workload / PR boundary

This is the assigned `feature/137-json-worker-lint` blocker slice under the auto-chain delivery path. The 326-line total no-rename diff is below the 400-line budget, and no files outside the two allowed surfaces were modified.

## Progress: JSON test diagnostics slice

### Status

- **Slice:** Test-only lint/type diagnostic remediation
- **Branch:** `feature/137-json-test-diagnostics`
- **Base:** `feature/137-json-worker-lint` at `9b31ed7`
- **Delivery boundary:** feature-branch-chain / auto-chain; uncommitted handoff, no push, PR, rename, or production edit
- **Provider/no-rename budget:** 266 changed lines across four tests before this progress entry; remains below 400 including this entry

### Completed tasks

- Added explicit optional-error and validated-record/model narrowing in runtime and native proof tests.
- Added deliberate casts at adversarial CLI/coordinator/factory seams and protocol-compatible native fake signatures.
- Fixed JSON spec import, regex, Decimal, `zip(strict=True)`, and multi-statement diagnostics without changing assertions or contract behavior.
- Fixed all Ruff findings in the four assigned test files, including native launcher proof formatting and subprocess `check=False`.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Supplied actionable LSP/type diagnostics plus initial `ruff check` | 37 Ruff findings and reported test-file type findings; environment-only pytest imports excluded |
| GREEN | Targeted test/lint/type remediation; `ruff check tests/test_json_v2_spec.py tests/test_cli_platform_boundary.py tests/test_runtime_cli.py tests/test_windows_native_proof.py` | All checks passed; Pyright reports only four unresolved environment-only `pytest` imports |
| TRIANGULATE | `python -m pytest -q tests/test_json_v2_spec.py tests/test_cli_platform_boundary.py tests/test_runtime_cli.py tests/test_windows_native_proof.py` | **64 passed, 4 skipped** |
| TRIANGULATE / collection | `python -m pytest -q --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR | `python -m py_compile` on all four files and `git diff --check` | Passed; no production files changed |

### Files changed

- `tests/test_json_v2_spec.py`
- `tests/test_cli_platform_boundary.py`
- `tests/test_runtime_cli.py`
- `tests/test_windows_native_proof.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None; only test diagnostics, typing boundaries, and formatting were changed. Runtime behavior and adversarial proof intent are preserved.

### Remaining tasks

- Parent authoritative LSP found only four environment-resolution false positives for installed `pytest`; each was recorded explicitly. No actionable findings remain in this slice.

### Workload / PR boundary

This is one assigned test-only diagnostic work unit. The total 309-line no-rename diff remains under the 400-line budget. Parent LSP disposition is complete; no push, PR, or production edit.

## Progress: remaining five test diagnostics

### Status

- **Slice:** Test-only lint/type diagnostic remediation
- **Branch:** `feature/137-json-test-diagnostics-2`
- **Base:** `feature/137-json-test-diagnostics` at `81d4498`
- **Delivery boundary:** feature-branch-chain / auto-chain; uncommitted handoff, no push, PR, rename, or production edit
- **Budget:** 326 changed lines before this progress entry; remains below the 400-line no-rename limit after this entry

### Completed tasks

- Added optional snapshot/window narrowing and honest optional helper annotations in projection tests.
- Converted enabled-provider inputs to `frozenset`, typed provider-error sets, and used targeted casts for adversarial invalid model/config inputs.
- Preserved frozen-dataclass, invalid-object, cache, and redaction semantics while making fake cache guards/callbacks protocol-compatible.
- Fixed import ordering, `zip(strict=True)`, Decimal literals, managed cache reads, and multi-statement formatting; removed stale deleted-v1 fixture hash assertions.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Supplied actionable diagnostics plus initial `ruff check` | **32 Ruff findings** and the reported auxiliary test typing findings; environment-only `pytest` resolution excluded |
| GREEN | Targeted casts, narrowing helpers, protocol-compatible fakes, formatting, and stale-fixture assertion cleanup | Required focused suite: **220 passed**; Ruff all five: **All checks passed** |
| TRIANGULATE | `python -m pytest -q --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR | `python -m py_compile` on all five files and `git diff --check` | Passed; no production edits, renames, ignores, or commits |

### Files changed

- `tests/test_json_v2_projection.py`
- `tests/test_contracts.py`
- `tests/test_customwidget_examples.py`
- `tests/test_cli_output_version.py`
- `tests/test_v2_cache.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Remaining tasks

- Parent authoritative LSP found only installed-`pytest` environment false positives plus three stale/misaligned CustomWidget Pyright locations; all were recorded explicitly. No actionable findings remain in this slice.

### Workload / PR boundary

Assigned test-only remediation slice; the 381-line total no-rename diff remains within the 400-line budget. Parent LSP disposition is complete; no production changes, selector behavior changes, push, or PR.

## Progress: CLI import-format blocker

- **Branch:** `feature/137-json-cli-imports`
- **Base:** `feature/137-json-test-diagnostics-2` at `4d823fa`
- **RED:** Ruff reported four formatting/style findings in `src/yasb_limitora/cli.py`.
- **GREEN:** Ruff auto-fix applied behavior-equivalent import wrapping, `re.IGNORECASE`, and redundant suppression cleanup; `ruff check` passed.
- **TRIANGULATE:** CLI/platform/runtime tests: **89 passed, 4 skipped**; diff check passed.
- **Budget:** 24 insertions + 6 deletions, below 400.
- **Scope:** `src/yasb_limitora/cli.py` only; no selector behavior change, rename, push, or PR.

## Progress: intermediate CLI current-default slice

### Status

- **Slice:** Semantic 2 intermediate — selector-free current routing and explicit-v1 rejection
- **Branch:** `feature/137-json-cli-default-current`
- **Base:** `feature/137-json-cli-imports` at `be5e06f`
- **Delivery boundary:** feature-branch-chain / auto-chain; one local commit only, no push or PR
- **Provider/no-rename budget:** 35 additions + 31 deletions before this progress entry; under the 400-line limit including the bounded progress update

### Completed tasks

- Made `_output_version` select the current (v2) contract when no selector is supplied.
- Rejected explicit `--output-version 1` and `--output-version=1` before configuration or coordinator execution.
- Kept explicit v2 selector spellings as a temporary no-op compatibility seam for this intermediate child.
- Updated only directly affected assertions in `tests/test_cli_output_version.py` for current-contract invalid output and selector-free current routing.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | Updated selector-free/current and explicit-v1 tests first; `python -m pytest -q tests/test_cli_output_version.py -k 'explicit_v1_is_rejected_with_current_contract or selector_free'` | **5 failed, 53 deselected**; failures were the expected legacy v1 routing/shape mismatches |
| GREEN | Implemented the bounded selector seam and current invalid-invocation envelope in `src/yasb_limitora/cli.py`; `python -m pytest -q tests/test_cli_output_version.py` | **59 passed** |
| TRIANGULATE | `python -m pytest -q --strict-markers tests/test_cli_output_version.py tests/test_cli_platform_boundary.py` | **63 passed, 4 skipped** |
| TRIANGULATE / runtime current path | `python -m pytest -q --strict-markers tests/test_runtime_cli.py -k 'v2'` | **14 passed, 12 deselected** |
| TRIANGULATE / required dependent command | `python -m pytest -q --strict-markers tests/test_cli_output_version.py tests/test_cli_platform_boundary.py tests/test_runtime_cli.py` | **6 failures** in un-migrated selector-free legacy expectations in `tests/test_runtime_cli.py`; no edits made there per handoff scope |
| TRIANGULATE / collection | `python -m pytest -q --strict-markers --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR / diagnostics | `ruff check src/yasb_limitora/cli.py tests/test_cli_output_version.py`, `python -m py_compile ...`, and `git diff --check` | Passed; no new diagnostics |

### Files changed

- `src/yasb_limitora/cli.py`
- `tests/test_cli_output_version.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- This is intentionally an intermediate compatibility slice: v2 filenames, symbols, legacy coordinator/serializer code, and explicit v2 selector spellings remain unchanged for later children.
- Remaining selector-free legacy expectations in `tests/test_runtime_cli.py` are intentionally not migrated in this child, so the complete three-file dependent command is not yet green; the current v2 subset and directly affected CLI tests are green.
- No task checkbox was changed because no existing broad task item is fully completed by this bounded slice.

### Remaining tasks

- Migrate remaining selector invocations and selector-free legacy test expectations in the later CLI/runtime child.
- Eventually remove selector 2 and the legacy routing/coordinator/projection paths in the designated follow-up slices.
- Run final full strict-marker and native Windows verification at the final chain boundary.

### Workload / PR boundary

This child contains only the current-default/v1-rejection behavior and directly affected output-version tests. The no-rename diff remains below 400 changed lines. Explicit v2 selectors are temporary and must not be described as final selector removal. One local commit is authorized after the focused green tests and collection evidence; no push or PR.

## Progress: corrective runtime expectation slice

### Status

- **Slice:** Corrective gate remediation for `semantic-cli-default-current`
- **Branch:** `feature/137-json-cli-default-current`
- **Base:** `5168402` (`feat(cli): default selector-free output to current contract`)
- **Delivery boundary:** feature-branch-chain / auto-chain; one corrective local commit, no push or PR
- **Allowed edit surfaces:** `tests/test_runtime_cli.py` and this progress artifact only
- **Cumulative no-rename count:** 193 changed lines versus `be5e06f` after this progress entry; below the 400-line limit

### Completed tasks

- Updated the six stale selector-free runtime expectations/fixtures to the current document envelope and current provider outcome semantics.
- Preserved all production code and the explicit-v2 temporary no-op selector tests.
- Added current-default configuration fixtures for injected coordinator cases so selector-free calls exercise the implemented current path.

### TDD cycle evidence

| Cycle | Evidence | Result |
|---|---|---|
| RED | `python -m pytest -q --strict-markers tests/test_cli_output_version.py tests/test_cli_platform_boundary.py tests/test_runtime_cli.py` on `5168402` | **6 failed, 83 passed, 4 skipped**; failures were the three parameterized invalid-argument cases plus missing-cookie, runtime-safe-error, and config/runtime-redaction legacy expectations in `tests/test_runtime_cli.py` |
| GREEN | Updated only `tests/test_runtime_cli.py` expectations and current-default fixtures | Required dependent command: **89 passed, 4 skipped** |
| TRIANGULATE / collection | `python -m pytest -q --strict-markers --collect-only` | **590 tests collected**, 0 collection errors |
| REFACTOR / diagnostics | `ruff check tests/test_runtime_cli.py` and `git diff --check` | All Ruff checks passed; diff check passed |

### Files changed

- `tests/test_runtime_cli.py`
- `openspec/changes/single-supported-json-output/apply-progress.md`

### Deviations from design

- None. This correction changes only stale test expectations/fixtures; production behavior, selector handling, explicit-v2 no-op coverage, names, and persisted identities remain unchanged.

### Remaining tasks

- Parent chain may continue with the remaining semantic/runtime cleanup and later rename-exception slices.
- Final full strict-marker suite and native Windows proof remain for the designated final verification boundary.

### Workload / PR boundary

This is the assigned corrective work unit for the failed current-default gate. The branch cumulative no-rename count is within the 400-line budget, and this commit boundary contains no production edits or renames. Commit locally after the recorded green, collection, Ruff, and diff checks; do not push or create a PR.
