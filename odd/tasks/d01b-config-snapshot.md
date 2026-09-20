# D01b — Immutable config snapshot and assist wiring

## Goal
Read and validate the fixed config exactly once under the D01a lease, expose an immutable snapshot to setup-assist consumers while ownership remains active, and preserve S08 reject-and-preserve behavior.

## Scope
- `src/yasb_limitora/setup_assist.py`
- `src/yasb_limitora/config.py` only if required for immutable snapshot typing
- `src/yasb_limitora/_config_lock.py` only for lease/context lifetime seam
- `tests/test_setup_assist_config.py`
- `tests/test_config_lock.py` only for lease lifetime coverage
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

## Contract
- Fixed path `%LOCALAPPDATA%\\yasb-limitora\\config.json`; no caller override invented.
- Missing parent returns `config-absent` before lock acquisition and creates no state root.
- Parent tri-state is present/absent/unsafe; unsafe/reparse/file/unreadable states refuse safely.
- Present config is read through handle-bound fstat/read under the owned D01a lease.
- `validate_config_document` runs exactly once under ownership.
- Snapshot is deeply immutable and contains original bytes, `LocalConfig | None`, immutable provider-error keys, and present/absent state.
- Snapshot/consumer lifetime ends before D01a releases the lease.
- Valid documents preserve current Gate 2 unavailable behavior; invalid documents remain byte-identical and unwritten.
- No backup, merge, write, state-root creation, or provider-selection changes.
- Target: <=350 changed lines; one rollback boundary.

## Tasks
- [x] Add RED tests for tri-state parent, fixed path, exactly-once validation, immutable snapshot, lease lifetime, and no-write behavior.
- [x] Implement the smallest snapshot/assist wiring and any lease lifetime seam.
- [x] Run focused, native, full, and Ruff checks; record evidence and review the exact candidate.

## Evidence
- Fixed-path reuse is enforced across parent checks, lock acquisition, and handle-bound config access.
- Parent tri-state is resolved before lock acquisition; present configs use handle-bound `fstat`/read operations.
- `validate_config_document` runs exactly once under the owned lease, and the resulting snapshot is deeply immutable.
- The setup-assist consumer finishes before lease release; the fallback owned lifecycle and guaranteed cleanup boundary are preserved.
- D01b performs no backup, merge, write, or state-root creation, and preserves S08 reject-and-preserve byte identity and absent/unsafe behavior.
- Verification: focused **85 passed + 1 skipped**; native **11**; full **922 passed + 4 skipped**; Ruff clean; independent verification passed.
- Budget: **228/350 changed source+test lines**.
- Rollback boundary: revert only D01b snapshot/assist-wiring changes and their tests/evidence; D01a3b and S08 remain intact.
- Remaining: D02 owned-field merge and atomic write, D03 rollback/reread verification, and D04 explicit provider selection state.

## Non-goals
D02 merge/write, D03 rollback, D04 provider selection, installer, or publication work.
