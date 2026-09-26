# S11 — Inno program transaction, assist invocation, and uninstall lifecycle

## Scope
Implement the S11 installer lifecycle in the bounded surfaces:
- `packaging/inno/yasb-limitora.iss`
- `packaging/inno/SetupAssistant.isi`
- `scripts/build_setup.py`
- `tests/test_inno_script.py`

## Split decision
The original S11 candidate exceeded the ≤400-line budget and lacked actual install/reinstall/upgrade/uninstall lifecycle proof. The user selected two bounded, sequential sub-slices; S11 remains unchecked until both are independently complete.

### S11a — Inno setup-assist transport and invocation
- **Depends on:** S04c/S05–S10/G1/G2a.
- **Budget and surfaces:** ≤400 lines; `packaging/inno/SetupAssistant.isi`, relevant `packaging/inno/yasb-limitora.iss` hooks, and focused tests.
- **Plan:** establish the exact nonce-derived transport, operations/choices-only request schema, bounded regular-file result schema, consent operations, exact cleanup ordering, and nonfatal post-commit invocation.

### S11b — Inno transaction closeout and setup build driver
- **Depends on:** S11a.
- **Budget and surfaces:** ≤400 lines; remaining lifecycle wiring, `scripts/build_setup.py`, and tests.
- **Plan:** complete transaction closeout, rollback/quarantine and uninstall wiring, then validate frozen input and ISCC invocation with native compile and lifecycle evidence.

## Acceptance
- Preserve G1 pre-install evacuation and rollback ordering, including `.failed` quarantine and captured registry restoration.
- Add nonce-derived assist transport with operations/choices-only requests, bounded schema-valid result validation before exact transport cleanup.
- Invoke assist after install commit as nonfatal; uninstall defaults to preserving state and only dispatches cleanup on explicit `YES` consent.
- Validate frozen onedir input and invoke ISCC with explicit version/source/output defines using bounded diagnostics.
- Focused and full tests pass, with any unrelated pre-existing failures recorded.
- Actual install/reinstall/upgrade/uninstall lifecycle proof is required for S11b and remains pending.

## Plan
1. Add RED tests for the S11a transport/invocation contract and the S11b lifecycle/build-driver contracts.
2. Implement and verify S11a within its ≤400-line budget.
3. Implement and verify S11b within its ≤400-line budget, including native compile and actual lifecycle proof.
4. Update OpenSpec progress/evidence; do not mark either sub-slice complete without its required evidence.

## Constraints
- No source runtime changes, release publication, or artifact promotion.
- No process termination; no state-root transport; no request target paths.
- Keep source+test authored changes within S11 budget (≤400 lines where measured by project ledger).

## Current evidence

- Implementation candidate present in the four S11 surfaces.
- RED: 7 failures / 26 passed.
- GREEN focused: 32 passed.
- Full suite: 942 passed / 4 skipped.
- Ruff: clean.
- Native ISCC 6.7.3 disposable compile passed using a temporary minimal frozen bundle.
- Actual install/reinstall/upgrade/uninstall lifecycle proof remains pending.
- No S11 task checkbox completion yet.

## Latest S11a evidence — pending

- `SetupAssistant.isi` is reduced to **249 lines**, within the S11a ≤400-line candidate budget.
- Focused verification: `python -m pytest -q --strict-markers tests/test_inno_script.py tests/test_setup_assist_protocol.py` → **80 passed**.
- Full suite: **942 passed, 4 skipped**.
- Ruff: clean.
- Disposable native ISCC **6.7.3** compile passed with a temporary minimal frozen bundle after correcting unsupported Inno APIs.
- S11a and S11b remain unchecked because real install/reinstall/upgrade/uninstall lifecycle proof is pending.
- The S11a/S11b split and the ≤400-line budget for each candidate are preserved.

## Latest S11b verification evidence — pending

- Build-driver static checks and Ruff pass.
- Full suite: **942 passed, 4 skipped**.
- Native ISCC **6.7.3** compile passes with a temporary minimal frozen bundle.
- `python scripts/build_frozen_bundle.py` cannot produce a real candidate because PyInstaller **>=6,<7** is not installed; it exits `2` with `pyinstaller_missing`.
- Therefore actual install/reinstall/upgrade/uninstall lifecycle proof remains pending, and S11b stays unchecked.
