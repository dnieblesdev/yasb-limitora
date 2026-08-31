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
