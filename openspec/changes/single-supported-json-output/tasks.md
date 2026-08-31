# Implementation Tasks: Single Supported JSON Output

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,600–2,200 semantic/no-rename lines, plus 7,983 no-rename lines attributable to four unavoidable physical rename-only slices (Git rename-aware view: 341 lines) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Tracker → planning correction → semantic contract/projection → semantic CLI/cache → semantic runtime/legacy cleanup → semantic examples/docs → rename exceptions (normative doc, projection tests, spec tests, schema) → final verification |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

## Maintainer-approved accounting and failed-attempt evidence

- Failed branch `feature/137-json-projection` at commit `13f63d6` is excluded from the active chain. It must not be used as a base or cherry-pick source.
- The native no-rename accounting for the physical rename work is **7,983 lines**, while Git's rename-aware accounting reports **341 lines**. Review notes must record both numbers; the exception budget is based on the native/no-rename number.
- Exact delete+add drivers are: normative document rename **3,779**, projection-test rename **1,372**, spec-test rename **1,265**, and schema rename **1,411** lines.
- The failed attempt also demonstrated the consumer-ordering gate: **31/58 CLI tests failed** and **2 dependent collection errors** because projection symbols/files changed before consumers migrated. One duplicate `project_bytes` lint error was introduced; named worker/test lint debt was pre-existing.
- Reset completed at revision `sha256:4632f38baef121e3814e5a7feee95a97ea5906b614643013621406c2a6e46c5b`. The first child of the active plan is the small planning correction `feature/137-json-budget-repartition`, based on `feature/137-json-planning-design`.

## Chain policy

Use a **Feature Branch Chain**. Semantic behavior slices must stay at or below **400 provider/no-rename changed lines**. Physical rename-only work may exceed 400 only through an explicitly named `size:exception` slice with a bounded no-rename budget below. Keep v2 filenames and test filenames during semantic implementation. Do not rename or delete a consumer's provider before all consumers have migrated and passed collection/import checks.

Each slice must state its start, finish, dependency, verification, and rollback boundary. Keep tests with the behavior they verify. Local commits/branches are allowed; pushing, opening PRs, and merging are not authorized. Preserve immutable external/persisted identity strings, including `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, and provider source IDs.

## Branch order and dependency diagram

1. `feature/137-single-json-output-tracker` — empty local ref at `main`; no implementation.
2. `feature/137-json-budget-repartition` — current child from `feature/137-json-planning-design`; this tasks-only planning correction.
3. `feature/137-json-contract-projection` — semantic contract/projection behavior, retaining v2 filenames.
4. `feature/137-json-cli-cache` — semantic CLI, configuration, and cache behavior, retaining v2 filenames.
5. `feature/137-json-runtime-cleanup` — semantic runtime cleanup and bounded legacy deletion, retaining filenames until consumers are migrated.
6. `feature/137-json-examples-docs` — semantic examples and active documentation updates.
7. `feature/137-json-rename-normative-doc` — `size:exception`; mechanical normative document rename only.
8. `feature/137-json-rename-projection-tests` — `size:exception`; mechanical projection-test rename only.
9. `feature/137-json-rename-spec-tests` — `size:exception`; mechanical spec-test rename only.
10. `feature/137-json-rename-schema` — `size:exception`; mechanical schema rename only.
11. `feature/137-json-final-verification` — residue, full-suite, native-Windows evidence, and accounting only.

```text
main
 └─ tracker
     └─ 📍 feature/137-json-budget-repartition (planning correction)
         └─ contract-projection
             └─ cli-cache
                 └─ runtime-cleanup
                     └─ examples-docs
                         └─ 📍 size:exception rename-normative-doc
                             └─ 📍 size:exception rename-projection-tests
                                 └─ 📍 size:exception rename-spec-tests
                                     └─ 📍 size:exception rename-schema
                                         └─ final-verification
```

The failed `feature/137-json-projection@13f63d6` is excluded and is not in this graph. Rename exceptions are deliberately last, after consumer migration; use four exceptions because each named driver has a distinct review boundary and combining them would obscure rollback and reviewer accounting.

## Slice boundaries

| Slice | Scope and budget | Start / finish and dependency | Verification | Rollback |
|---|---|---|---|---|
| Planning correction | `tasks.md` only; small planning diff, well under 400 | Start from `feature/137-json-planning-design`; finish with this repartition, failed evidence, four explicit exception budgets, and ordered checklist. | Markdown/link sanity; confirm every branch and budget below is represented. | Revert the planning child; prior design remains unchanged. |
| Semantic 1: contract/projection | `src/yasb_limitora/projection_v2.py`, current schema/projection consumers, and their existing tests/fixtures; **≤400 no-rename lines**; retain v2 filenames | Start after planning correction; finish with three-root current-only contract, canonical ordering, LF output, and migrated consumers. No physical renames. | RED → GREEN → TRIANGULATE → REFACTOR for success/failure/not-run, malformed/order/size/redaction/LF cases; run dependent collection and focused projection/contract suites. | Revert this behavior unit without changing filenames or later slices. |
| Semantic 2: CLI/cache | `src/yasb_limitora/cli.py`, `config.py`, `model.py`, v2 cache implementation, and dependent CLI/cache tests; **≤400 no-rename lines**; retain v2 filenames | Start after Semantic 1 is green; finish with selector-free routing, strict parsing, precedence, one deadline, stream/exit behavior, single-flight/bounds, and schema-3 stale-cache rejection. | RED → GREEN → TRIANGULATE → REFACTOR; run CLI/config/cache suites and full collection to prevent the prior 31/58 failure pattern. | Revert the unit atomically; keep the projection contract intact. |
| Semantic 3: runtime and bounded legacy cleanup | Runtime imports/exports, worker/process/guard/deadline/platform consumers, and deletions of obsolete v1 paths in **≤400 no-rename lines per child**; retain v2 filenames until the final consumer check | Start after CLI/cache; finish with importable current behavior, preserved lifecycle/security identities, and no collection breakage. Split any deletion work into additional children rather than using rename exceptions. | RED → GREEN → TRIANGULATE → REFACTOR; focused imports/child-process/lifecycle/deadline/guard/jobs/spawn tests plus collection check. | Revert each bounded cleanup child independently; do not restore compatibility aliases. |
| Semantic 4: examples/active docs | `examples/customwidget/**`, active docs, roadmap superseding note, and related tests/fixtures; **≤400 no-rename lines per child** | Start after runtime cleanup; finish with selector-free current guidance while preserving historical roadmap text and immutable identity literals. | RED → GREEN → TRIANGULATE → REFACTOR; link/schema/example/provider-source checks and focused tests. | Revert the user-facing child without reverting runtime behavior. |
| `size:exception` 1: normative doc rename | Mechanical rename-only change for the normative document; **bounded exception: 3,779 no-rename lines**; Git rename-aware reference: part of 341 total | Start only after all semantic consumers and links are green; finish with path/name updates and no wording/behavior changes. | Prove rename-only diff, link/search checks, and focused documentation validation. | Revert only the document rename. |
| `size:exception` 2: projection-test rename | Mechanical projection-test filename/symbol/path rename only; **bounded exception: 1,372 no-rename lines**; Git rename-aware reference recorded | Start after exception 1; finish with collected tests and updated references, with no semantic test edits. | Prove rename-only diff; collect and run projection/contract tests. | Revert only projection-test rename. |
| `size:exception` 3: spec-test rename | Mechanical spec-test filename/path rename only; **bounded exception: 1,265 no-rename lines**; Git rename-aware reference recorded | Start after exception 2; finish with collected spec tests and references, with no behavior edits. | Prove rename-only diff; collect and run spec-related tests. | Revert only spec-test rename. |
| `size:exception` 4: schema rename | Mechanical schema filename/path rename only; **bounded exception: 1,411 no-rename lines**; Git rename-aware reference recorded | Start after exception 3; finish with all schema references updated and no contract changes. | Prove rename-only diff; schema/link validation and dependent collection. | Revert only schema rename. |
| Final verification | Verification records only; no new behavior or cleanup | Start after all rename exceptions; finish with no active v1/selector residue and complete evidence. | Run focused suites, `python -m pytest -q --strict-markers`, native Windows proof (or explicitly record externally unrun), import/collection checks, and both native and rename-aware diff accounting. | Revert verification-only notes without reverting behavior slices. |

## Ordered strict-TDD checklist

### Planning and accounting

- [ ] Add the planning correction first on `feature/137-json-budget-repartition`; do not use `13f63d6`.
- [ ] Record provider/no-rename counts for every semantic child and keep each at or below 400.
- [ ] Record the four exact rename-only exception budgets and Git rename-aware guidance; do not hide rename work in semantic slices.

### Semantic RED → GREEN → TRIANGULATE → REFACTOR

- [ ] RED: add/update current-only projection, schema, CLI, cache, runtime, and consumer tests while retaining v2 filenames.
- [ ] GREEN: implement contract/cache/CLI/runtime semantics in dependency order; migrate consumers before any provider rename or deletion.
- [ ] TRIANGULATE: run focused success, failure, not-run, malformed, ordering, size, redaction, LF, stream/exit, precedence, deadline, stale-cache, import, process, guard, jobs, and spawn checks; require collection to remain clean.
- [ ] REFACTOR: remove duplicate `project_bytes` and any behavior-slice lint debt introduced by the work; distinguish pre-existing named worker/test lint debt.
- [ ] RED/GREEN/TRIANGULATE/REFACTOR each bounded legacy deletion child at ≤400 no-rename lines.
- [ ] Update examples and active docs only after runtime behavior is green; preserve historical and immutable identity text.

### Mechanical rename exceptions and final gate

- [ ] After all consumers migrate, execute exactly the four reviewable rename exceptions (normative doc, projection tests, spec tests, schema), each with its stated no-rename budget.
- [ ] For every exception, prove no semantic edits, record native/no-rename and Git rename-aware counts, and run collection plus its scoped checks.
- [ ] Search active source/tests/examples/docs/packaging for selectors, v1 artifacts, deleted names, and active versioned implementation names; exclude only designated historical text and immutable persisted identities.
- [ ] Record per-branch test results, strict-marker results, native Windows status, collection status, rollback boundary, and clean final diff accounting before delivery.

## Non-negotiable constraints

- Keep tests with the behavior they verify and do not add compatibility aliases for deleted active names.
- Do not push, open, or merge PRs; do not create implementation artifacts outside this tasks file.
- Preserve `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, and provider source IDs exactly.
