# D03 — Config rollback and reread verification

## Goal
Prove and harden rollback after replacement/final-validation/reread failures, including deletion of newly created configs, while verifying selected owned paths and preserving unowned fields.

## Scope
- `src/yasb_limitora/setup_assist.py`
- `tests/test_setup_assist_config.py`
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

## Contract
- Injected write, final-validation, reread, and comparison failures restore the original bytes or delete a newly created config.
- Rollback remains lease-bound and verifies restored state before reporting failure recovery.
- Reread verification proves selected owned paths equal the request and unowned fields equal the original document.
- S08 invalid-document byte identity remains unchanged.
- Target: <=200 changed source+test lines.

## Tasks
- [x] Add RED tests for post-replace failure, owned/unowned reread tampering, absent-config cleanup, and rollback verification.
- [x] Implement the smallest verified rollback/reread path.
- [ ] Run native and independent review checks to closure; record final evidence.

## Candidate evidence
- Source/test diff: 96 authored lines (52 source, 48 tests with 4 deletions), within the <=200 budget.
- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_config.py` -> 30 passed, 1 skipped.
- Full: `python -m pytest -q --strict-markers` -> 931 passed, 4 skipped.
- Ruff: `python -m ruff check src/yasb_limitora/setup_assist.py tests/test_setup_assist_config.py` -> clean.
- LSP diagnostics: no reported findings; confirmation timed out/unavailable for the two servers.
- Native review: started with explicit session authorization, but reviewer capture binding was rejected before any reviewer mutation; no review closure or commit is claimed.


## Rollback boundary
Revert only D03 rollback/reread verification code and tests. D01a/D01b, D02 merge/write, S08 validation, and D04 provider-selection semantics remain intact.

## Non-goals
Provider selection semantics, installer, publication, or unrelated config-lock changes.
