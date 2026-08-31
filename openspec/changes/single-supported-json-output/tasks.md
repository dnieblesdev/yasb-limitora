# Implementation Tasks: Single Supported JSON Output

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,600–2,200 semantic/no-rename lines, plus 20,255 bounded no-rename lines for seven unavoidable physical rename-only slices (at least 341 Git rename-aware lines already evidenced, plus the added mechanical renames) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Tracker → planning correction → semantic contract/projection → semantic CLI/cache → semantic runtime/legacy cleanup → semantic examples/docs → rename normative doc → rename projection source/tests → rename cache source/tests → rename worker source/tests → rename guard/deadline/path sources/tests → rename spec tests → rename schema → final verification |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

## Maintainer-approved accounting and failed-attempt evidence

- Failed branch `feature/137-json-projection` at commit `13f63d6` is excluded from the active chain. It must not be used as a base or cherry-pick source.
- The native no-rename accounting for the physical rename work is **7,983 lines**, while Git's rename-aware accounting reports **341 lines**. Review notes must record both numbers; the exception budget is based on the native/no-rename number.
- Exact delete+add drivers are: normative document rename **3,779**, projection source plus projection-test rename **≤2,800** (including legacy projection replacement and import edits), cache source plus cache-test rename **≤4,500**, worker source plus worker-test rename **≤2,700**, guard/deadline/path sources plus guard/deadline/path/file-read tests **≤3,800**, spec-test rename **1,265**, and schema rename **1,411** lines.
- The failed attempt also demonstrated the consumer-ordering gate: **31/58 CLI tests failed** and **2 dependent collection errors** because projection symbols/files changed before consumers migrated. One duplicate `project_bytes` lint error was introduced; named worker/test lint debt was pre-existing.
- Reset completed at revision `sha256:4632f38baef121e3814e5a7feee95a97ea5906b614643013621406c2a6e46c5b`. The first child of the active plan is the small planning correction `feature/137-json-budget-repartition`, based on `feature/137-json-planning-design`.

## Chain policy

Use a **Feature Branch Chain**. Semantic behavior slices must stay at or below **400 provider/no-rename changed lines**. Physical rename-only work may exceed 400 only through an explicitly named `size:exception` slice with a bounded no-rename budget below. Keep v2 filenames and test filenames during semantic implementation. Do not rename or delete a consumer's provider before all consumers have migrated and passed collection/import checks.

Each slice must state its start, finish, dependency, verification, and rollback boundary. Keep tests with the behavior they verify. The user explicitly authorizes chained-PR publication, push, verification, merge, and issue/change closure; this child remains local until its bounded work unit is ready. Preserve immutable external/persisted identity strings, including `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, and provider source IDs.

## Branch order and dependency diagram

1. `feature/137-single-json-output-tracker` — empty local ref at `main`; no implementation.
2. `feature/137-json-budget-repartition` — current child from `feature/137-json-planning-design`; this tasks-only planning correction.
3. `feature/137-json-contract-projection` — semantic contract/projection behavior, retaining v2 filenames.
4. `feature/137-json-cli-cache` — semantic CLI, configuration, and cache behavior, retaining v2 filenames.
5. `feature/137-json-runtime-cleanup` — semantic runtime cleanup and bounded legacy deletion, retaining filenames until consumers are migrated.
6. `feature/137-json-examples-docs` — semantic examples and active documentation updates.
7. `feature/137-json-rename-normative-doc` — `size:exception`; mechanical normative document rename only.
8. `feature/137-json-rename-projection` — `size:exception`; mechanical `projection_v2.py` → active projection name plus projection-test rename and import/reference updates.
9. `feature/137-json-rename-cache` — `size:exception`; mechanical `v2_cache.py` and `test_v2_cache.py` active-name normalization plus import/reference updates.
10. `feature/137-json-rename-worker` — `size:exception`; mechanical `v2_worker.py` and `test_v2_worker.py` active-name normalization plus import/reference updates.
11. `feature/137-json-rename-guard-deadline-path` — `size:exception`; mechanical guard/deadline/path source and guard/deadline/path/file-read test normalization plus import/reference updates.
12. `feature/137-json-rename-spec-tests` — `size:exception`; mechanical spec-test rename only.
13. `feature/137-json-rename-schema` — `size:exception`; mechanical schema rename only.
14. `feature/137-json-final-verification` — residue, full-suite, native-Windows evidence, and accounting only.

```text
main
 └─ tracker
     └─ 📍 feature/137-json-budget-repartition (planning correction)
         └─ contract-projection
             └─ cli-cache
                 └─ runtime-cleanup
                     └─ examples-docs
                             └─ 📍 size:exception rename-normative-doc
                                 └─ 📍 size:exception rename-projection
                                     └─ 📍 size:exception rename-cache
                                         └─ 📍 size:exception rename-worker
                                             └─ 📍 size:exception rename-guard-deadline-path
                                                 └─ 📍 size:exception rename-spec-tests
                                                     └─ 📍 size:exception rename-schema
                                                         └─ final-verification
```

The failed `feature/137-json-projection@13f63d6` is excluded and is not in this graph. Rename exceptions are deliberately last, after consumer migration. Source and corresponding test renames are combined only when collection remains valid and the diff is mechanical; unrelated normative, spec-test, and schema drivers retain separate rollback and accounting boundaries.

## Slice boundaries

| Slice | Scope and budget | Start / finish and dependency | Verification | Rollback |
|---|---|---|---|---|
| Planning correction | `tasks.md` only; small planning diff, well under 400 | Start from `feature/137-json-planning-design`; finish with this repartition, failed evidence, seven explicit exception budgets, and ordered checklist. | Markdown/link sanity; confirm every branch and budget below is represented. | Revert the planning child; prior design remains unchanged. |
| Semantic 1: contract/projection | `src/yasb_limitora/projection_v2.py`, current schema/projection consumers, and their existing tests/fixtures; **≤400 no-rename lines**; retain v2 filenames | Start after planning correction; finish with three-root current-only contract, canonical ordering, LF output, and migrated consumers. No physical renames. | RED → GREEN → TRIANGULATE → REFACTOR for success/failure/not-run, malformed/order/size/redaction/LF cases; run dependent collection and focused projection/contract suites. | Revert this behavior unit without changing filenames or later slices. |
| Semantic 2: CLI/cache | `src/yasb_limitora/cli.py`, `config.py`, `model.py`, v2 cache implementation, and dependent CLI/cache tests; **≤400 no-rename lines**; retain v2 filenames | Start after Semantic 1 is green; finish with selector-free routing, strict parsing, precedence, one deadline, stream/exit behavior, single-flight/bounds, and schema-3 stale-cache rejection. | RED → GREEN → TRIANGULATE → REFACTOR; run CLI/config/cache suites and full collection to prevent the prior 31/58 failure pattern. | Revert the unit atomically; keep the projection contract intact. |
| Semantic 3: runtime and bounded legacy cleanup | Runtime imports/exports, worker/process/guard/deadline/platform consumers, and deletions of obsolete v1 paths in **≤400 no-rename lines per child**; retain v2 filenames until the final consumer check | Start after CLI/cache; finish with importable current behavior, preserved lifecycle/security identities, and no collection breakage. Split any deletion work into additional children rather than using rename exceptions. | RED → GREEN → TRIANGULATE → REFACTOR; focused imports/child-process/lifecycle/deadline/guard/jobs/spawn tests plus collection check. | Revert each bounded cleanup child independently; do not restore compatibility aliases. |
| Semantic 4: examples/active docs | `examples/customwidget/**`, active docs, roadmap superseding note, and related tests/fixtures; **≤400 no-rename lines per child** | Start after runtime cleanup; finish with selector-free current guidance while preserving historical roadmap text and immutable identity literals. | RED → GREEN → TRIANGULATE → REFACTOR; link/schema/example/provider-source checks and focused tests. | Revert the user-facing child without reverting runtime behavior. |
| `size:exception` 1: normative doc rename | Mechanical rename-only change for the normative document; **bounded exception: 3,779 no-rename lines**; Git rename-aware reference: part of 341 total | Start only after all semantic consumers and links are green; finish with path/name updates and no wording/behavior changes. | Prove rename-only diff, link/search checks, and focused documentation validation. | Revert only the document rename. |
| `size:exception` 2: projection source/tests rename | Rename `src/yasb_limitora/projection_v2.py`, its projection test file(s), active projection symbols, and import/reference spellings only; **bounded exception: ≤2,800 no-rename lines**, including legacy projection replacement and small import edits | Start after exception 1 and consumer migration; finish with collected projection tests and unchanged assertions/behavior. | Prove rename-only/collection diff; run scoped projection and contract tests. | Revert only the projection source/test rename. |
| `size:exception` 3: cache source/tests rename | Rename `src/yasb_limitora/v2_cache.py`, `tests/**/test_v2_cache.py`, active cache symbols, and import/reference spellings only; **bounded exception: ≤4,500 no-rename lines** | Start after exception 2; finish with collected cache tests and unchanged cache semantics. | Prove rename-only/collection diff; run scoped cache and dependent CLI tests. | Revert only the cache source/test rename. |
| `size:exception` 4: worker source/tests rename | Rename `src/yasb_limitora/v2_worker.py`, `tests/**/test_v2_worker.py`, active worker symbols, and import/reference spellings only; **bounded exception: ≤2,700 no-rename lines** | Start after exception 3; finish with collected worker tests and unchanged process behavior. | Prove rename-only/collection diff; run scoped worker/process tests. | Revert only the worker source/test rename. |
| `size:exception` 5: guard/deadline/path sources/tests rename | Rename `src/yasb_limitora/v2_guard.py`, `src/yasb_limitora/v2_deadline.py`, `src/yasb_limitora/v2_path.py`, `tests/**/test_v2_guard.py`, `tests/**/test_v2_deadline.py`, `tests/**/test_v2_path.py`, `tests/**/test_v2_file_read.py`, active guard/deadline/path symbols, and import/reference spellings only; **bounded exception: ≤3,800 no-rename lines** | Start after exception 4; finish with collection and unchanged lifecycle, deadline, path, and file-read behavior. | Prove rename-only/collection diff; run scoped guard/deadline/path/file-read tests. | Revert only this grouped source/test rename. |
| `size:exception` 6: spec-test rename | Mechanical spec-test filename/path rename only; **bounded exception: 1,265 no-rename lines**; Git rename-aware reference recorded | Start after exception 5; finish with collected spec tests and references, with no behavior edits. | Prove rename-only diff; collect and run spec-related tests. | Revert only spec-test rename. |
| `size:exception` 7: schema rename | Mechanical schema filename/path rename only; **bounded exception: 1,411 no-rename lines**; Git rename-aware reference recorded | Start after exception 6; finish with all schema references updated and no contract changes. | Prove rename-only diff; schema/link validation and dependent collection. | Revert only schema rename. |
| Final verification | Verification records only; no new behavior or cleanup | Start after all rename exceptions; finish with no active v1/selector residue and complete evidence. | Run focused suites, `python -m pytest -q --strict-markers`, native Windows proof (or explicitly record externally unrun), import/collection checks, and both native and rename-aware diff accounting. | Revert verification-only notes without reverting behavior slices. |

## Ordered strict-TDD checklist

### Planning and accounting

- [ ] Add the planning correction first on `feature/137-json-budget-repartition`; do not use `13f63d6`.
- [x] Record provider/no-rename counts for every semantic child and keep each at or below 400. Semantic Slice 1: 141 changed lines, within the 400-line budget.
- [ ] Record the seven bounded rename-only exception budgets (normative doc, projection, cache, worker, guard/deadline/path, spec tests, schema) and Git rename-aware guidance; do not hide rename work in semantic slices.

### Semantic RED → GREEN → TRIANGULATE → REFACTOR

- [x] RED: add/update current-only projection, schema, CLI, cache, runtime, and consumer tests while retaining v2 filenames.
- [x] Strict config grammar child: make the current `from_mapping` parser sole, isolate provider errors, reject string timeouts, and migrate direct consumers.
- [ ] GREEN: implement contract/cache/CLI/runtime semantics in dependency order; migrate consumers before any provider rename or deletion.
- [ ] TRIANGULATE: run focused success, failure, not-run, malformed, ordering, size, redaction, LF, stream/exit, precedence, deadline, stale-cache, import, process, guard, jobs, and spawn checks; require collection to remain clean.
- [ ] REFACTOR: remove duplicate `project_bytes` and any behavior-slice lint debt introduced by the work; distinguish pre-existing named worker/test lint debt.
- [x] Bounded legacy-deletion child: add the v1-artifact absence assertion, then remove `tests/test_v1_golden_fixtures.py` and `tests/fixtures/json_v1_*.json`; focused GREEN and collection pass.
- [x] Bounded CLI orchestrator-only child: remove the reachable `RuntimeCoordinator` injection/fallback seam, migrate direct CLI/runtime consumers to the orchestrator seam, and retain coordinator.py for the later deletion child.
- [x] Bounded coordinator/projection deletion child: prove the legacy module paths and exports are absent, then delete both modules and coordinator-only/v1 projection-only test seams.
- [ ] RED/GREEN/TRIANGULATE/REFACTOR each remaining bounded legacy deletion child at ≤400 no-rename lines.
- [x] Update examples and active docs only after runtime behavior is green; preserve historical and immutable identity text.
- [x] CustomWidget examples/docs child: selector-free `yasb-limitora`, current-only fixture/docs assertions, exact provider paths, and immutable source IDs preserved.
- [x] Normative current-contract child: update title, root shape/order, projection/cache/runtime wording, examples, schema metadata, and coupled spec expectations while retaining v2 filenames and identities.
- [x] Bounded normative CLI/configuration child: replace the legacy selector/configuration block with one current invocation grammar, precedence, strict config rules, invalid former-selector behavior, and the current stream/exit matrix.

### Mechanical rename exceptions and final gate

- [x] `size:exception` 1: mechanically rename the normative document and migrate only active path references; preserve document bytes, schema/test identities, and roadmap history.
- [ ] After all consumers migrate, execute exactly the seven reviewable rename exceptions (normative doc, projection source/tests, cache source/tests, worker source/tests, guard/deadline/path sources/tests, spec tests, schema), each with its stated no-rename budget.
- [ ] For every exception, prove rename-only/no semantic edits, record native/no-rename and Git rename-aware counts, and run collection plus its scoped checks; combined source/test slices are permitted only when branch collection remains valid.
- [ ] Search active source/tests/examples/docs/packaging for selectors, v1 artifacts, deleted names, and active versioned implementation names; exclude only designated historical text and immutable persisted identities.
- [ ] Record per-branch test results, strict-marker results, native Windows status, collection status, rollback boundary, and clean final diff accounting before delivery.

## Non-negotiable constraints

- Keep tests with the behavior they verify and do not add compatibility aliases for deleted active names.
- Chained-PR publication, push, verification, merge, and issue/change closure are authorized by the user; this apply child must only create its bounded local commit and must not publish yet.
- Preserve `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, and provider source IDs exactly.
