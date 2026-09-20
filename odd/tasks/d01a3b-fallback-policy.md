# D01a3b — Fallback policy and integration

## Goal
Implement the bounded fallback policy that unifies primary Guard and marker ownership without adding config reads, validation, snapshot, merge, write, backup, or state-root creation.

## Scope
- `src/yasb_limitora/_config_lock.py`
- `tests/test_config_lock.py`
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

## Contract
- Private typed `ConfigLease` unifies primary mutex and marker fallback ownership.
- One shared five-second `DeadlineContext` covers Guard and marker retries.
- Fallback is allowed only for `guard_acquisition_failed`; `guard_wait_timeout` remains `config-lock-busy`.
- Empty, partial, malformed, oversized, unverifiable, and own-process markers refuse as sanitized `config-lock-busy` and are never reclaimed.
- Only `ProcessTokenMissing` or a returned token mismatch permits reclaim; `ProcessTokenUnprovable` and equal tokens refuse.
- Cleanup failure maps to `config-lock-release-failed`.
- Fixed existing parent and literal marker name; no parent/state-root creation.
- Target: <=280 changed source+test lines; one rollback boundary.

## Tasks
1. [x] Map existing seams and preserve D01a3a1/a2a/a2b behavior.
2. [x] Add strict RED tests for fallback selection, marker ownership/reclaim refusal, deadline, race cleanup, and sanitized errors.
3. [x] Implement the smallest typed lease/fallback integration.
4. [x] Run focused, native, full, and Ruff checks; record evidence and review the exact candidate.

## Evidence
- Focused: 63 passed.
- Guard integration: 76 passed.
- Native: 11 passed.
- Full: 916 passed, 4 skipped.
- Ruff: clean.
- Independent verification: pass.
- Changed source+test budget: 278/280 (`src/yasb_limitora/_config_lock.py`: 178 changed lines; `tests/test_config_lock.py`: 100 changed lines).
- Remaining: D01b.

## Non-goals
No config document read/validation, snapshot, merge/write, backup, assist wiring, or provider selection.
