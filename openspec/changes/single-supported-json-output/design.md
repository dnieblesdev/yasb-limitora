# Design: make the current JSON document the only supported output

The runtime will become one current-contract pipeline: configuration resolution → bounded execution → sanitized projection → optional public-only cache → stdout. The legacy v1 pipeline, selector, and compatibility exports are deleted rather than preserved behind aliases. The only intentional wire change is removal of the root `version` member; current provider values, ordering (after that removal), safety behavior, and operational identities remain unchanged.

## Quick path

1. Write failing current-contract tests that prove selector-free precedence, no root `version`, selector rejection, and previous-schema cold refresh.
2. Rename the active current-contract modules and symbols, merge their behavior into the unversioned path, then delete v1 modules, routing, fixtures, tests, and aliases.
3. Update schema, examples, normative/operator documentation, and contract tests together; run focused tests, full strict-marker pytest, and native Windows proof when available.

## Architecture and data flow

```text
YASB CustomWidget
  -> yasb-limitora CLI (early non-Windows gate)
  -> config resolution: --config/-c -> YASB_LIMITORA_CONFIG -> %LOCALAPPDATA% default
  -> bounded current execution and cleanup
  -> current projection (sanitized UTF-8 JSON + exactly one LF; no root version)
  -> current-schema public-only cache/single-flight (when eligible)
  -> stdout; bounded diagnostics only on stderr
  -> Limitora public API
```

The direction remains one-way: YASB invokes the CLI and consumes its JSON; this repository owns local configuration, process/guard/cache bounds, redaction, and projection; Limitora retains provider selection, authentication, transport, and provider-specific interpretation. No provider behavior moves into this repository.

### Decisions

| Topic | Decision |
| --- | --- |
| Supported contract | The current document is the sole contract. Its root order is `execution_state`, `execution_error`, `providers`; there is no root `version`. Provider and nested canonical orders do not change. |
| CLI | Remove `_output_version` and parse only the existing allowed configuration forms. A former `--output-version` argument is ordinary invalid invocation input, returns the current sanitized invocation-invalid document/diagnostic behavior, and never dispatches v1. |
| Configuration | Every supported selector-free invocation resolves explicit config, then non-empty `YASB_LIMITORA_CONFIG`, then the per-user default. It uses strict current parsing and provider-scoped error overlay; there is no `from_v2_mapping` branch or legacy permissive fallback. |
| Execution | `ExecutionOrchestrator` is the only execution path. Remove `RuntimeCoordinator`, `ProviderCoordinator`, and legacy projection/loader routing rather than retaining injectable compatibility paths. Preserve the current worker, shared deadline, guard/job/process cleanup, and child-spawn importability. |
| Error model | Merge the former `V2SafeErrorCode` members into `SafeErrorCode`; `SafeError` then has one code enum. Values and projected codes are unchanged. |
| Cache | Increment `CACHE_SCHEMA` from `2` to `3`. Schema mismatch is a cache miss and invokes the ordinary bounded refresh/single-flight flow; do not migrate, rewrite eagerly, or serve previous-schema bytes. Remove root-version validation and reconstruct canonical public bytes from the three current root fields. |
| Operational identities | Do not change byte strings for `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, provider IDs (`codex-app-server-v2`, `opencode-go-api`), or cache/coordination literals that identify shared work. These are identity literals, not contract-version labels. |
| Documentation history | Replace active guidance with current-only language. Retain historical v1/v2 material in `docs/roadmap.md`, prefaced by a dated/superseding note that the current JSON contract is now the sole supported output. |

## Active-name normalization map

Rename files with `git mv` and update static imports, dynamic imports, monkeypatch strings, `__all__`, test imports, and child-process targets in the same work unit. These are exact active names, not compatibility aliases.

| Existing active name | New active name | Notes |
| --- | --- | --- |
| `projection_v2.py` | `projection.py` | Delete the existing v1 `projection.py` first/within the same atomic rename; it is not retained. |
| `V2ProjectionInput` | `ProjectionInput` | |
| `project_v2_document`, `project_v2_bytes`, `project_v2_failure_bytes`, `project_v2_not_run_bytes` | `project_document`, `project_bytes`, `project_failure_bytes`, `project_not_run_bytes` | Current projection becomes the only producer. |
| `v2_cache.py` | `cache.py` | Preserve cache/marker filename and suffix literals. |
| `V2QuotaCache` | remove alias; use `RefreshCoordinator` | `RefreshCoordinator` is already the concrete unversioned lifecycle type. No alias remains. |
| `v2_guard.py` | `guard.py` | |
| `V2Guard` | `Guard` | Preserve default name prefix exactly. Remove `NamedMutexGuard` compatibility alias/export. |
| `v2_deadline.py` | `deadline.py` | `DeadlineContext` remains `DeadlineContext`. |
| `v2_path.py` | `path.py` | |
| `V2PathError`, `V2FileError`, `V2DeadlineError` | `PathError`, `FileError`, `DeadlineError` | Update exception handling and child imports. |
| `canonicalize_v2_path`, `read_v2_config` | `canonicalize_path`, `read_config` | Preserve bounds and lookup-free/bounded behavior. |
| `v2_worker.py` | `worker.py` | |
| `V2ExecutionOrchestrator`, `V2ExecutionRecord` | `ExecutionOrchestrator`, `ExecutionRecord` | `RefreshAttempt`, `OpenCodeWorkerProcess`, and lifecycle semantics remain. |
| `V2SafeErrorCode` | remove; merge members into `SafeErrorCode` | No wire-value change. |
| `CodexConfig.from_v2_mapping`, `OpenCodeGoConfig.from_v2_mapping`, `LocalConfig.from_v2_mapping` | `from_mapping` | Make the strict current grammar/provider-isolation behavior the one implementation; delete legacy mapping behavior. |
| `docs/specifications/json-v2.md`, `json-v2.schema.json` | `json-output.md`, `json-output.schema.json` | Update `$id`, title, description, links, and normative heading to describe the current JSON contract. |
| `test_json_v2_projection.py`, `test_json_v2_spec.py` | `test_json_projection.py`, `test_json_output_spec.py` | Rename current-contract tests and their helper imports. |
| `test_v2_cache.py`, `test_v2_guard.py`, `test_v2_file_read.py` | `test_cache.py`, `test_guard.py`, `test_file_read.py` | Rename all active test symbols/descriptions from `v2` to current/unversioned terminology. |

Apply the same boundary rule to remaining active test names and assertions (for example `test_v2_*` runtime, deadline, transport, configuration, and platform labels): rename them to describe the behavior, not a supported version. Do **not** rename literal provider IDs, guard/cache names, historical roadmap references, or frozen historical commit/PR descriptions.

## Migration and deletion plan

### 1. Establish the current-only CLI seam

`cli.main` keeps its ordering: early non-Windows rejection occurs before argv, environment, clock, configuration, freeze-sensitive product execution, or provider activity; `multiprocessing.freeze_support()` remains immediately after the Windows gate. The internal helper sentinel remains private and is handled before normal invocation parsing.

After the private-helper check, validate only the config grammar. Resolve exactly one path using the existing precedence and read it through the renamed bounded file API. Construct the one deadline, execute through `ExecutionOrchestrator`, retain cache eligibility/single-flight behavior, overlay provider-scoped configuration errors, then project through the unversioned current projector. Every invocation/configuration/runtime/projection failure must emit the current redacted envelope and established stream/exit behavior; no branch may instantiate `RuntimeCoordinator` or serialize the deleted v1 shape.

### 2. Make the producer, model, and cache agree

Remove `"version": 2` from normal, failure, and not-run projection constructors. Update the current schema's required/properties/order definition, documentation examples, fixture objects, and contract constants together. Change cache `_public_document_json`, `_presentation_candidate`, and `_validate_document` from the four-field root tuple to `("execution_state", "execution_error", "providers")`. Cache envelope order remains `schema`, `cached_at`, `fingerprint`, `document`.

`CACHE_SCHEMA = 3` is the acceptance boundary. A persisted schema-2 entry fails before document validation/public-byte reuse and proceeds through the normal fresh producer under the existing deadline. New cache documents have no root `version`; validation still rejects noncanonical ordering, duplicate/unsafe keys, secret/path leakage, oversized content, invalid presentation, non-public provider evidence, or non-cacheable outcomes.

### 3. Delete the obsolete path completely

Delete:

- legacy `projection.py` content before replacing that filename with the renamed current projector;
- `coordinator.py`, its `RuntimeCoordinator`/`ProviderCoordinator` public aliases and legacy test seams;
- `_output_version`, legacy `_load`/`_load_path`/`_load_explicit` behavior, `_LEGACY_READ_CONFIG`, and version-conditioned branches;
- v1 config grammar/timeout coercion and version-only model distinctions;
- `tests/test_v1_golden_fixtures.py`, `tests/fixtures/json_v1_*.json`, v1 hashes/assertions in CustomWidget tests, and v1-only selector tests;
- v1-only docs/examples and any v1 compatibility/export aliases.

Delete rather than move a v1 artifact into an `archive` directory: Git history and retained roadmap history are the historical record. Before finalizing, search source, tests, examples, packaging metadata, documentation (excluding designated historical roadmap text), dynamic import strings, and monkeypatch targets for obsolete module/symbol/selector names. A remaining active import or alias is a defect, not a compatibility feature.

## File and test update map

| Area | Expected changes | Required evidence |
| --- | --- | --- |
| `src/yasb_limitora/cli.py` | One config/worker/projector/cache pipeline; delete v1 imports/branches. | Selector-free explicit/env/default precedence; removed selector rejection; same streams/exits/redaction. |
| `src/yasb_limitora/config.py`, `model.py` | Strict current mapping becomes `from_mapping`; consolidate safe codes. | Provider-local invalid config remains isolated; top-level config fails closed; no legacy coercion contract. |
| renamed projector/cache/guard/deadline/path/worker modules | Apply map above and update imports including lazy child imports. | Exact JSON without root version, cache schema-2 cold refresh, byte-for-byte operational identities, deadlines/guards/cleanup/single-flight unchanged. |
| deleted `coordinator.py` and old projector | Remove code and references. | Import/monkeypatch search finds no active legacy coordinator/projection path. |
| `tests/test_cli_output_version.py` → behavior-named CLI test | Replace version routing cases with selector rejection plus current output/precedence/error matrix. | Removed selector cannot select any legacy document and does not bypass sanitization. |
| current projection/spec/cache/runtime tests | Rename and adjust root-order/schema/fixture assertions; retain outcome, presentation, canonicalization, cache bounds, concurrency, lifecycle and child-spawn coverage. | No expected document contains root `version`; canonical bytes end in one LF. |
| `tests/test_cli_platform_boundary.py`, native proof, process/job/helper tests | Update imports/monkeypatch strings and selector parameters. | Non-Windows gate remains before product side effects; Windows native lifecycle proof still exercises current modules. |
| `examples/customwidget/**` and `tests/test_customwidget_examples.py` | Remove root `version`, make `run_cmd` `yasb-limitora` (no selector), delete v1 fixture digest assertions. | Examples validate the sole document and retain provider-source literals/YASB paths. |
| `docs/specifications/*`, `docs/windows-json.md`, `README.md`, `docs/architecture/README.md` | Rename active normative files, remove dual-contract claims, selector commands, and root-version language; document break/cache invalidation/unchanged identities. | Documentation contract tests follow renamed files and examples. |
| `docs/roadmap.md` | Add only a superseding note; keep prior historical content verbatim. | Historical v1 references remain readable and visibly superseded. |

## Strict-TDD implementation sequence

Each work unit follows **RED → GREEN → TRIANGULATE → REFACTOR**, with no implementation edit before its focused failing test is observed and recorded in the apply artifact.

1. **CLI contract RED:** Convert selector/version-route tests into current-only tests: selector-free explicit/env/default configuration produces the same root shape without `version`; every former selector spelling is invalid and cannot load/run legacy code; invalid/config/runtime/projection errors retain current stream/exit/redaction behavior. GREEN with the single CLI path, then refactor imports/names.
2. **Projection/schema RED:** Change root-order/document/schema/example assertions to reject `version` and require exactly the three roots. GREEN by removing it from normal/failure/not-run producers and schema. Triangulate successful, unavailable/not-run, safe-error, malformed provider, byte-size, ordering, and LF paths.
3. **Cache RED:** Add a schema-2 serialized cache entry test that proves no cached bytes are served and the producer is called once; add a current schema-3 round-trip test that rejects inserted `version`. GREEN by incrementing schema and changing the canonical/validation root tuple. Re-run single-flight, bounds, corrupted-cache, marker, and public-only tests.
4. **Rename/deletion RED:** Update imports, dynamic imports, monkeypatch strings, and public-export assertions to use the normalization map; add absence tests/search checks where repository conventions permit. GREEN using atomic renames and deletions, not aliases. Re-run child-spawn, guard, deadline, process/job cleanup, and platform-boundary tests because imports are exercised across process boundaries.
5. **Docs/examples RED:** Update documentation/fixture contract tests first for renamed normative paths, selector-free `run_cmd`, root field set, and roadmap supersession. GREEN by updating docs/examples and deleting v1 artifacts. Confirm no active docs promise compatibility.
6. Run relevant focused tests after each GREEN/REFACTOR phase, then `python -m pytest -q --strict-markers`. Run `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` on native Windows; otherwise record it as external verification still required.

## Compatibility, security, and rollout

This is a deliberate pre-stable break. Consumers must remove reads of root `version`, remove `--output-version`, and invoke the selector-free command with the existing config precedence. There is no dual document, compatibility alias, migration adapter, cache migration, or claim that private consumers do not exist.

The rollout is source/release atomic: package, schema, examples, and operator docs change together. Existing schema-2 caches safely cold-refresh under schema 3; guard/cache/provider identity strings remain stable so this does not fragment coordination or provider recognition. Preserve secret rejection, redacted exceptions/paths/payloads, public-only cache acceptance, bounded child environments, deadline reserve, cleanup retry/retention, and early platform gate throughout the refactor.

## Risks and controls

| Risk | Control |
| --- | --- |
| Rename misses dynamic/monkeypatch/child imports | Update literal import targets with the rename; focused child-spawn/process tests plus final obsolete-name search. |
| Root removal creates inconsistent bytes | Test projector, schema, fixtures/examples, and cache canonical root tuple as one contract unit. |
| Old cache is served or migrated | Explicit schema-2 cold-refresh test; schema mismatch precedes reuse; no migration code. |
| Guard/cache identity split | Treat identity literals as immutable regression assertions, even though module/class names change. |
| Coordinator deletion changes safety behavior | Preserve and run platform, streams/exits, deadline, guard/job/process cleanup, and redaction matrices against the sole worker path. |
| Documentation accidentally erases history | Limit roadmap edit to the superseding note and verify historical references remain. |

## Rollback and work units

Rollback is a source/release revert to the prior supported tree, including its prior schema handling if operationally required. Do not add a permanent fallback or migrate caches in either direction. A rollback may discard schema-3 cache data and refresh cold; restoring the old schema behavior is part of the reverted code, not a live compatibility bridge.

Suggested reviewable commits keep tests with behavior and docs with the user-visible break:

1. `test(cli): specify current-only JSON contract and cache invalidation`
2. `refactor(json): make current projection and runtime the sole path`
3. `refactor(names): normalize active current-contract modules and tests`
4. `docs(json): document single output contract and preserve roadmap history`

If the combined diff exceeds the review budget, keep these as chained work units, each independently testable and revertible.
