# Implementation Tasks: Single Supported JSON Output

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1,600–2,100 across planning artifacts, runtime, tests, examples, and docs; exact current planning footprint is 587 lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Tracker → planning 1 (config/proposal) → planning 2 (spec) → planning 3 (design/tasks) → behavior 1 (projection) → behavior 2 (CLI/cache) → behavior 3 (runtime) → behavior 4 (examples/docs) → final verification |
| Delivery strategy | auto-chain / resolved ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

## Chain decision and budget rule

Use a **Feature Branch Chain**. No `size:exception` is accepted. Local branches and local commits are authorized; push and PR creation are not authorized. Every tracker or child slice must remain at or below **400 additions plus deletions**, be reviewable in about 60 minutes, and have its own verification and rollback boundary. If a slice approaches 400, split it into another child in this same chain without asking again.

The planning footprint is counted explicitly, not treated as overhead:

| Existing artifact | Current lines | Planned slice |
|---|---:|---|
| `openspec/config.yaml` | 73 | Planning 1 |
| `openspec/changes/single-supported-json-output/proposal.md` | 75 | Planning 1 |
| `openspec/changes/single-supported-json-output/specs/json-output/spec.md` | 170 | Planning 2 |
| `openspec/changes/single-supported-json-output/design.md` | 147 | Planning 3 |
| `openspec/changes/single-supported-json-output/tasks.md` | 122 | Planning 3 |
| **Total current planning footprint** | **587** | **Distributed; no single planning diff exceeds 400** |

## Branch order and dependency diagram

1. `feature/137-single-json-output-tracker` remains an empty local ref at `main`, with zero changed lines and no commit; it carries no planning artifact, behavior, tests, or implementation.
2. `feature/137-json-planning-contract` branches from the tracker and makes the first actual commit, carrying `config.yaml` plus `proposal.md`.
3. `feature/137-json-planning-spec` branches from Planning 1 and carries `specs/json-output/spec.md`.
4. `feature/137-json-planning-design` branches from Planning 2 and carries `design.md` plus the full executable `tasks.md` artifact.
5. `feature/137-json-projection` branches from Planning 3 and implements the projection/schema contract.
6. `feature/137-json-cli-cache` branches from Projection and implements CLI/configuration and cache behavior.
7. `feature/137-json-runtime-cleanup` branches from CLI/cache and normalizes runtime names and removes obsolete paths.
8. `feature/137-json-examples-docs` branches from Runtime cleanup and updates examples and active documentation.
9. `feature/137-json-final-verification` branches from Examples/docs and records residue, full-suite, and native-Windows verification.

```text
main
 └─ 📍 tracker (empty ref at main): feature/137-single-json-output-tracker
     └─ 📍 planning 1: feature/137-json-planning-contract
         └─ 📍 planning 2: feature/137-json-planning-spec
             └─ 📍 planning 3: feature/137-json-planning-design
                 └─ 📍 behavior 1: feature/137-json-projection
                     └─ 📍 behavior 2: feature/137-json-cli-cache
                         └─ 📍 behavior 3: feature/137-json-runtime-cleanup
                             └─ 📍 behavior 4: feature/137-json-examples-docs
                                 └─ 📍 final: feature/137-json-final-verification
```

The tracker is only an empty local branch ref; creating any PR is out of scope. Later children target their immediate parent only; do not switch to stacked-to-main. Rebase or retarget polluted diffs before review.

## Slice boundaries

| Slice | Scope and estimated changed lines | Start / finish, dependencies | Verification | Rollback |
|---|---|---|---|---|
| Tracker | Empty local ref at `main`, zero changed lines, no commit; 0 lines; ≤60 min | Start at `main`; finish with the tracker ref unchanged at `main`. No planning artifact, product behavior, tests, or implementation. | Confirm tracker points exactly to `main`, has no commit of its own, and has zero changed lines. | Delete/recreate the empty tracker ref from `main`. |
| Planning 1: contract proposal | `openspec/config.yaml` (73) and `proposal.md` (75), ~148 lines plus small normalization; ≤60 min | Start at the empty tracker; make the first actual commit with config and proposal, with no spec/design/code changes. | Markdown/YAML parse, link/path checks, and compare scope against the requested current-only JSON outcome. | Revert this planning child; the empty tracker ref remains usable. |
| Planning 2: normative spec | `specs/json-output/spec.md` (170), ~170–190 lines; ≤60 min | Start at Planning 1; finish with scenarios matching proposal/config and explicit three-root current contract. | Validate scenario headings, references, schema terminology, and proposal/spec consistency. | Revert the spec child without touching proposal/config. |
| Planning 3: design and executable tasks | `design.md` (147) plus the full `tasks.md` artifact (122 lines), ~230–250 lines; ≤60 min | Start at Planning 2; finish with design/spec alignment, the complete ordered task artifact, exact paths, and all later slice boundaries. | Cross-check design decisions against spec; lint task tables/links; verify each behavior task has dependency, verification, and rollback. | Revert design/task addition together; prior planning artifacts remain intact. |
| Behavior 1: projection/schema | `src/yasb_limitora/projection.py`, `projection_v2.py` removal/normalization, schemas, projection/spec/contract tests and fixtures; ~220–320 lines; ≤60 min | Start at Planning 3; finish with unversioned three-root projection, canonical order, one LF, and schema/tests green. | RED focused projection tests, GREEN, TRIANGULATE success/failure/not-run/malformed/order/size/redaction/LF, then REFACTOR. | Revert projector, schema, tests, and fixtures as one unit. |
| Behavior 2: CLI/config/cache | `src/yasb_limitora/cli.py`, `config.py`, `model.py`, cache module, CLI/config/cache tests; ~230–350 lines; ≤60 min | Start at Projection; finish with selector-free routing, strict parsing, precedence, one deadline, and schema-3 stale-cache rejection. | RED → GREEN → TRIANGULATE streams/exits, errors, sanitization, single-flight, bounds, and stale schema-2 behavior. | Revert this unit atomically; no migration or dual-output fallback. |
| Behavior 3: runtime cleanup | Active runtime module renames, coordinator deletion, imports/exports, worker/process/guard/deadline/platform tests; ~220–340 lines; ≤60 min | Start at CLI/cache; finish with importable unversioned paths and preserved lifecycle/security identities. | RED import/child-process coverage, GREEN focused runtime tests, TRIANGULATE lifecycle, deadlines, guard bytes, jobs, and spawn behavior. | Revert all rename/deletion changes together; never restore aliases alone. |
| Behavior 4: examples and active docs | `examples/customwidget/**`, active docs, roadmap superseding note, related tests/fixtures; ~220–340 lines; ≤60 min | Start at Runtime cleanup; finish with current-only user guidance and historical roadmap references preserved. | RED documentation/example tests, GREEN, TRIANGULATE links, schema paths, examples, and provider-source literals. | Revert examples/docs/tests as one user-facing unit. |
| Final verification | Residue checks, focused suites, strict-marker suite, native Windows proof record, and delivery diff accounting; ~80–180 lines; ≤60 min | Start at Examples/docs; finish only when all acceptance evidence is recorded. No new behavior. | Search forbidden active residue; run focused suites and `python -m pytest -q --strict-markers`; run native proof on Windows or record it as externally unrun. | Revert verification-only notes without reverting behavior slices. |

## Ordered implementation checklist

### RED → GREEN → TRIANGULATE → REFACTOR

- [ ] Add failing current-only CLI/config tests in `tests/test_cli_output_version.py` and `tests/test_runtime_cli.py`; remove selector expectations only with the behavior change.
- [ ] Make `src/yasb_limitora/cli.py`, `config.py`, and `model.py` selector-free and strict while preserving gating, precedence, deadlines, streams, exits, and provider isolation.
- [ ] Add failing three-root projection/schema assertions in `tests/test_json_v2_projection.py`, `tests/test_contracts.py`, and related fixtures.
- [ ] Normalize `src/yasb_limitora/projection.py` from the current implementation, remove root `version`, and update `docs/specifications/json-output.schema.json` and `.md`.
- [ ] Add failing schema-2 cache-staleness and root-version rejection tests in `tests/test_v2_cache.py` and runtime CLI coverage; rename `v2_cache.py` to `cache.py`, set schema 3, and remove compatibility aliases.
- [ ] Add failing runtime import/process/platform coverage, rename active `v2_*` modules and symbols to unversioned names, and delete `coordinator.py` and obsolete compatibility exports.
- [ ] Update examples and active documentation to use the current selector-free command and contract; preserve historical `docs/roadmap.md` content except for a dated superseding note.
- [ ] Rename current-only tests where appropriate, delete v1-only fixtures/tests/examples, and update dynamic imports, monkeypatch targets, `__all__`, and child targets.
- [ ] Search active source/tests/examples/docs/packaging for selectors, v1 artifacts, deleted names, and active versioned implementation names; exclude only designated historical text and immutable persisted identities.
- [ ] Record focused-suite results, strict-marker results, native Windows proof status, changed-line counts, and clean per-slice boundaries before delivery.

## Execution constraints

- Keep tests with the behavior they verify; do not add compatibility aliases for deleted active names.
- Preserve `Global\\yasb-limitora-v2-guard-*`, `quota-v2-cache.json`, and provider source IDs.
- Local commits may be created per slice using the repository’s conventional commit style. Do not push, open, or merge PRs.
