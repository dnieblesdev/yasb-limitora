# S11 residual proof — consented cleanup correction

## Candidate and scope

- Base candidate: `f2c27de`.
- Historical source-candidate evidence follows; it describes the original worktree, not this clean-delivery candidate. No invented commit, receipt, or delivery authority is asserted for this candidate.
- The product correction composes the exact adjacent `path-remove` + `state-cleanup` (`YES`) batch. Standalone operations remain unchanged.

## Defect and fail-closed invariants

The old uninstall batch consumed the shared ownership record during `path-remove`, so the following state cleanup refused with `state-record-missing`. The private composition keeps the live record until both operations succeed, revalidates the record and post-CAS PATH before native cleanup, clears bookkeeping once at the end, and conditionally restores PATH only when the expected post-CAS value is still live.

Missing records, changed PATH, CAS failure, concurrent record replacement, native cleanup refusal, restore CAS failure, and bookkeeping failure remain bounded refusals. Native state deletion is irreversible and is never reported as restored. PATH notifications are emitted for each actual PATH mutation, including partial failure recovery. No arbitrary caller path, provider, secret, YASB configuration, or public JSON field was added.

## Historical TDD evidence (original candidate only)

- RED: `.venv/Scripts/python.exe -I -m pytest -q --strict-markers tests/test_setup_assist_protocol.py::test_uninstall_batch_reuses_live_record_for_path_and_state_cleanup` — 1 failed against the old implementation because the second operation returned `state-record-missing`.
- GREEN: the same command — 1 passed after the correction.
- Triangulation: focused path/protocol suites cover success, missing record, changed PATH, CAS failure, record replacement, native refusal, conditional restore failure, bookkeeping failure, notification count, and unchanged standalone operations.
- Bounded verifier follow-up: corrected only new fixture literals to realistic Windows paths; added protocol coverage for native `delete_directory=False` (`partial`, per-operation sanitized refusals, conditional PATH rollback, ownership preservation, exit 1) and the canonical environment-carried request (exit 1, no JSON stdout). Findings #1/#2 remain pre-existing, and #4 remains intentional; no product code was changed.

## Historical verification and proof boundary (original candidate only)

- Focused: `.venv/Scripts/python.exe -I -m pytest -q --strict-markers tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py` — 86 passed.
- Full: `.venv/Scripts/python.exe -I -m pytest -q --strict-markers` — 1052 passed, 21 skipped in 98.27s; skipped tests were not promoted to proof.
- Ruff: `.venv/Scripts/python.exe -I -m ruff check .` — all checks passed (`ruff 0.16.9`).
- LSP diagnostics were unavailable in that agent surface; no LSP result is claimed.
- Historical source-candidate diffstat: 316 insertions / 1 deletion across four tracked product/test files, plus this new ODD record; this follow-up changed tests/ODD only, and pre-existing untracked `nul` was preserved and untouched.
- Four VM routes: **PENDING**.
- The original record referenced operator-specific VM/source proof identifiers; those identifiers are redacted here. No new VM receipt is claimed here.
- Full `R11` is **not complete**.
- Native installer, build, proof-harness, provider, secret, YASB, and VM/storage operations were not part of this work unit.

## Clean-delivery verification status

This sanitized record is part of the new clean-delivery candidate. Its checks must be run and reported independently; none of the historical results above establish current-candidate verification or native acceptance.
