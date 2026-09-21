# D04 — Explicit provider selection state

## Goal
Keep provider `enabled` state controlled only by explicit selection while reporting missing readiness requirements as advisory warnings that never veto a valid commit.

## Scope
- `src/yasb_limitora/setup_assist.py`
- `tests/test_provider_enabled_state.py`
- `tests/test_setup_assist_config.py` (compatibility isolation only)
- `odd/tasks/d04-provider-selection-state.md`
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

## Contract
- Only an explicit `selection` entry may change a provider's `enabled` value.
- Without an explicit enabled-state selection, the existing value remains unchanged.
- Missing `LIMITORA_OPENCODE_API_KEY` and a missing configured Codex runner file produce bounded name-only warnings.
- Readiness warnings never alter `enabled`, veto a runtime-valid merge, or expose secret values.
- Unowned valid fields retain their original order and values.
- Target: <=200 changed source+test lines.

## Decisions
- Codex readiness treats a configured absolute runner path that is not an existing regular file as a missing external prerequisite.
- Warning records use stable reason codes and requirement names; they carry no values or user paths.

## Route
Delegated direct implementation through `gentle-ai-worker`; multi-file write trigger applies because source and a new focused test file are required. TDD source: `openspec/config.yaml`. Exact focused runner: `python -m pytest -q --strict-markers tests/test_provider_enabled_state.py tests/test_setup_assist_config.py`.

## Forecast
Expected source+test change: 110–160 authored lines. Delivery strategy: ask-on-risk. No commit is authorized by the current user request.

## Tasks
- [x] Add focused RED tests for explicit/no-selection state and advisory readiness warnings.
- [x] Implement bounded readiness warnings without changing merge or validation gates.
- [x] Run focused/full/Ruff verification and record candidate evidence.
- [x] Update OpenSpec progress after verified implementation.

## Candidate evidence
- Strict TDD RED: initial focused run had 2 missing-warning failures; correction RED produced `AssertionError: secret value inspected`.
- Final focused verification: **35 passed, 1 skipped**; final full verification: **936 passed, 4 skipped**.
- Ruff was clean on all three changed source/test files; `git diff --check` was clean.
- Independent verification completed and confirmed all D04 contract points.
- Native `gentle_review assess` was unassessable because the native command returned empty output; no native review closure is claimed.
- Budget: **166 source+test diff lines** (160 additions, 6 deletions), within the ≤200-line limit.
- No commit or delivery authorization exists.

## Rollback boundary
Revert only D04 readiness-warning code, provider-state tests, and D04 evidence. D01–D03 config snapshot/merge/rollback behavior remains intact.

## Non-goals
Provider authentication, transport, secret-value reads, discovery redesign, installer wiring, publication, or unrelated config validation changes.
