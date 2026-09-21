# D02 — Owned-field merge and atomic write

## Goal
Consume the D01b immutable config snapshot under the same D01a lease, apply only explicitly selected owned fields, validate the final document, atomically replace the fixed config, and verify the result.

## Scope
- `src/yasb_limitora/setup_assist.py`
- `tests/test_setup_assist_config.py`
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

## Decision
`request.json` is extended in D02: `config-apply` entries carry exactly a `selection` object containing only explicitly selected owned paths. This keeps the protocol complete rather than introducing an internal-only temporary API.

## Contract
- Owned paths only: `deadline_seconds`, `codex.enabled`, `codex.runner`, `codex.timeout_seconds`, `opencode_go.enabled`, `opencode_go.timeout_seconds`.
- Preserve every unowned contract-valid field and insertion order.
- Gate 1 invalid documents remain byte-identical and receive no backup/temp/write.
- Final merged document is validated before mutation.
- Existing configs are backed up in the fixed state-root backup directory with bounded retention; absent configs use create recovery.
- Write uses a same-directory temporary file, flush/fsync, and atomic replace.
- Re-read, parse, validate, and compare owned/unowned fields after replacement.
- Failure restores the backup or deletes a newly created config and removes temporary state.
- Snapshot consumption and all mutation remain inside the owned lease.
- Target: <=250 changed source+test lines; one rollback boundary.

## Tasks
- [x] Add RED tests for owned selection/merge, order and unowned preservation, atomic write, reread verification, backup/create recovery, and failure restoration.
- [x] Implement the smallest D02 merge/write path and request schema for explicit selections.
- [x] Run focused, native, full, Ruff, and independent review checks; record evidence and review the exact candidate.

## Evidence
- `request.json` decision: extend `config-apply` entries with exactly one `selection` object containing only explicitly selected owned paths; this keeps the protocol complete instead of adding an internal-only temporary API.
- Implementation contract: consume the immutable D01b snapshot under the same D01a lease; merge only the six owned paths; preserve unowned fields and insertion order; validate before mutation; write through a same-directory temporary file with flush/fsync and atomic replace; reread, validate, and compare the final document.
- Verification: focused **73 passed + 1 skipped**; native **11 passed**; full **926 passed + 4 skipped**; Ruff **clean**; diff-check **clean**.
- Budget: **247/250 source+test changed lines**.

## Rollback boundary
Revert only D02 merge/write code, request-schema changes, tests, and D02 evidence. D01a/D01b and S08 remain intact; D03 rollback/reread expansion and D04 provider-selection semantics remain outside this boundary.

## Non-goals
D03 rollback/reread failure expansion, D04 provider selection semantics, installer, or publication work.
