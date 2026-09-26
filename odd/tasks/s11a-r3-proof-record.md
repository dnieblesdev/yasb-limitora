# S11a — r3 VM proof record (#305)

## Goal
Externalize the S11a r3 disposable-VM proof into a tracked document under `docs/release/0.2.0/evidence/`, so an external reader does not depend on the git-ignored `build/` harness tree, and states honestly what the proof does not establish.

## Scope and constraints
- One new evidence document plus the cross-reference that makes it discoverable from the S11a ledger.
- No source, test, harness, installer, workflow, or release change.
- The document must not include external filesystem paths, must not reference raw evidence outside the repository, and must not claim more than the run establishes.
- Keep `build/` ignored; no harness artifact is added or force-added.
- Push, PR, and merge remain user decisions.

## Tasks
1. [x] Author `docs/release/0.2.0/evidence/s11a-r3-vm-proof-identities.md`: identities, scenario set, gate result, the five limits, and the gate-advisory note.
2. [x] Cross-link it from `odd/tasks/s11a-setup-assist-security.md`, the ledger that carries the r3 run.
3. [x] Verify links, absence of external paths, absence of over-claiming, and `build/` absence from the diff; then one docs work-unit commit on `docs/s11a-r3-proof-record`.
4. [ ] Push and open the PR linking #305 (`type:docs`). User decision; not authorized in this task.

## Outcome

- Work-unit commit: `cd48b0479ff4087a3ebe8546bcbb0b4db48b7c86` (`docs(s11a): record the r3 VM proof identities and its limits`) on `docs/s11a-r3-proof-record`, three paths and 107 insertions: the evidence record, this task record, and one cross-reference line in the S11a ledger.
- Verification before the commit: both relative links resolve, the new documents carry no external filesystem path, and `build/` is absent from the staged diff.

## Evidence and verification (2026-09-26)
Re-verified offline against the retained artifacts and records before writing:

- `s11a-inputs-r3.iso` — 13,641,728 bytes, SHA-256 `b4d323d1…` (matches #305).
- `yasb-limitora-0.2.0-setup.exe` — 13,492,025 bytes, SHA-256 `683c123e…` (matches #305).
- `guest/watch-scenarios.ps1` — SHA-256 `57d7ce68…` (matches #305 and the frozen stamp recorded per scenario).
- `orchestrate-lifecycle.ps1` — SHA-256 `6dd4e078…`; every harness file's modification time precedes the run.
- Checkpoint `clean-windows-running-watcher-s11a-v3` exists with id `89a47039-2230-4f0f-9c20-640e0163f40a` (matches #305).
- All 12 per-run records: exit code `0`; 8 `setup` runs carry the production setup hash and 4 `uninstall` runs carry the installed uninstaller `02431245…`.
- All 7 `done.json` records: `result: success`, `shutdownSkipped: false`, no non-zero step exit code.

Recorded-only (not re-derivable today): the host gate's own output line, the guest timing bounds, and the state-capture contents.

## Related
- #305 — the issue this task closes (approved 2026-09-26).
- #304 — the harness gate defects; parked without `status:approved`.
- `odd/tasks/s11a-setup-assist-security.md` — task entries 20 and 21, the run record this document externalizes.