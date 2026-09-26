# S11a — r3 disposable-VM proof identities

| Field | Value |
| --- | --- |
| Change | `release-and-smoke-test-0-2-0` |
| Result | **PASS** for the seven declared scenarios through the host gate, with the limits in §5 |
| Run date | 2026-09-25 (identities re-verified 2026-09-26) |
| TDD | Not applicable: documentation-only record. The r3 run itself is a lifecycle proof, not a test-driven code change. |

## 1. What this record is

The S11a r3 proof was executed by a disposable harness that lives in a git-ignored `build/` tree, so an external reader had no tracked place to check the identities or, more importantly, what the proof does not establish. This record fixes that gap: it states the identities, the scenario set, the gate results and the declared limits.

It records the proof. It does not replace the harness, re-run anything, or extend the verdict beyond what the run and its records show.

## 2. Identities

| Item | Value |
| --- | --- |
| Reviewed candidate | `8681dd2` (approved via `review-33481bc761a5dcdc` over `b363abe..8681dd2`), plus `5cc45b2` (CI test guard, approved via `review-079881b1ce5b5384`) |
| Production setup | `yasb-limitora-0.2.0-setup.exe` — 13,492,025 bytes, SHA-256 `683c123e1fb909a3971df99d4e7e8df179cf77c3dbf435ff865bb32066e38d58` |
| Data ISO | `s11a-inputs-r3.iso` — 13,641,728 bytes, SHA-256 `b4d323d17da42bb92994ca1da3e9b17226de0843682d2c3fc78475715f92a6da`, volume label `S11AINPUTS` |
| VM checkpoint | `clean-windows-running-watcher-s11a-v3` — id `89a47039-2230-4f0f-9c20-640e0163f40a`, frozen 2026-09-25 with the r3 media attached |
| Guest watcher | `guest/watch-scenarios.ps1` — SHA-256 `57d7ce68ece311e8c58b1c1d29c8899535182cb628c5e98b9737961ae018a95c` (the frozen stamp) |
| Installer runs | 8 `setup` run records, all carrying the production setup hash above |
| Uninstaller runs | 4 `uninstall` run records, all carrying the installed native uninstaller `02431245dfe2a60b55d16f6606929474ef5b8c432339afe73e9070862a390a8c` |
| Guest results | 7 `done.json` records, every `result: success`, none with `shutdownSkipped`, no non-zero step exit code |
| Guest exits | Every recorded exit code is `0` (12 per-run records) |

## 3. Scenario set and gate result

Seven scenarios ran unattended against the checkpoint above, reverted for every cycle:

`first-install`, `reinstall`, `locked-file`, `uninstall-preserve`, `explicit-cleanup`, `assist-request`, `owned-cleanup`.

The orchestrator reported `ORCHESTRATOR FINISHED SUCCESSFULLY (7 cycle(s))`, every cycle `success`, and the host gate `verify-evidence.py … --expected-executable 683c123e…` returned `VERDICT: PASS` (exit 0). A separate read-only pass verified coverage, media identity, exit codes, consent answers and locked-file tolerance.

## 4. What was re-verified on 2026-09-26

Offline, against the artifacts and records retained locally:

- Recomputed SHA-256 for the r3 ISO, the production setup, the guest watcher and the host orchestrator. The first three match the values in §2; every harness file's modification time precedes the run.
- The checkpoint named in §2 still exists on the disposable VM with the recorded id.
- Re-read all 12 per-run records: every `exitCode` is `0`, all 8 `setup` records carry the production setup hash, and all 4 `uninstall` records carry the installed uninstaller hash.
- Re-read all 7 `done.json` records: `result: success`, `shutdownSkipped: false`, and no non-zero step exit code.

One precision about the orchestrator: its retained copy hashes to `6dd4e0788bec5b04b36da4af5d12e0d12e3460f6162efa21a4e085d52219ed64` and was not modified before the run, but that hash was not recorded as a run-time identity when the run happened, so it supports rather than proves the run-time copy.

Recorded-only, not re-derivable today: the host gate's own output line, the guest timing bounds, and the state-capture contents. Those stay as recorded in the S11a task ledger; the evidence copies that carried them were hashed at copy time.

## 5. What the proof does not establish

1. **`config-apply` is unreachable in a silent run.** With no provider choice the installer emits only `{"operation":"discover"}`, so the run covers the request and exit-code transport, not a provider mutation.
2. **`assist-request` records no operation payload** — only the task selector and exit code `0`.
3. **The `explicit-cleanup` refusal cause is recorded nowhere.** The reason channel was removed for security, so the install log carries `assistant reported non-zero exit (code 1)` and the fixture state remains. That refusal is the ownership gate working as designed, but the evidence cannot state the reason.
4. **`owned-cleanup`'s attribution to the assist is an inference** from the after-capture: there is no positive assist line, only the absence of a failure line.
5. **The r3 ISO stays attached to the VM DVD drive by design.** The harness never attaches or detaches media and every cycle reverts the checkpoint, so "nothing left attached" holds for the host, not for the VM.

## 6. Gate status

The harness gates are advisory today; their defects are tracked in #304 (parked, not approved). Two consequences apply to this proof:

- The guest watcher's in-cycle failure test reads step results through `PSObject.Properties`, which never exposes the ordered-dictionary keys, so it cannot fail a cycle closed on a non-zero step exit. The `done.json` exit codes in §2 come from the record file; the in-cycle test did not gate them.
- `verify-evidence.py` checks per-run exit codes, the `done.json` flags and each setup record's executable hash. It does not check watcher stamps, ISO identity, guest state content or assist behaviour; a separate read-only pass covered those.

## 7. References

- #305 — the issue that requested this record (approved 2026-09-26).
- #304 — the disposable-VM gate defects (parked without `status:approved`).
- `odd/tasks/s11a-setup-assist-security.md` — task entries 20 and 21, the run record this document externalizes: [the S11a task ledger](../../../../odd/tasks/s11a-setup-assist-security.md).
- [The C5 evidence report](s11b-c5-silent-uninstall-state-root.md) — the sibling dynamic record for the S11b/B1 chain, a different candidate on a different branch.