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
