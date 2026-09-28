# S11b issue #299 closeout

## Goal
Reconcile and complete the remaining acceptance criteria for issue #299 from the merged `main` baseline without overstating prior proof.

## Scope and constraints
- Worktree: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11b-299`.
- Branch: `feat/s11b-issue-299-closeout`, based on `main` at `d5a0506`.
- The ordered PR chain and B1/G1 implementation are already merged; preserve their commit identities and historical evidence.
- Keep `build/` out of Git and never execute installers on the host.
- Rebuild and compare the C5 artifact hash before deciding whether disposable-VM re-proof is required.
- Preserve C5 **PASS with caveats**, v7 `PASS_WITH_FINDINGS`, and existing C7/C10 status; do not claim zero prompts.
- Commits, pushes, PR creation, VM execution, and merge require explicit user authorization.

## Tasks
1. [x] Initialize CodeGraph in the new worktree and map the remaining #299 acceptance criteria against merged `main`.
2. [x] Define the bounded C5 rebuild/hash-comparison work unit and its verification plan.
3. [x] Execute the authorized local build/contract checks without running installers on the host; determine whether VM re-proof is required.
4. [x] Integrate the merged #304 reusable proof harness while preserving the untracked #299 record and historical evidence.
5. [x] Implement the #299-specific C5 runner, fixtures, and offline verifier test-first without changing the frozen bootstrap.
6. [x] Dry-run and independently verify the C5 host contract, then execute the authorized disposable-VM run through checkpoint v3; attempt5 evidence was recovered and verified.
7. [ ] Update only the evidence/status records justified by observed results, then complete record verification and native review.

## Evidence
- Issue #299: `feat(s11b): deliver transaction closeout with B1 and C5 evidence` (`status:approved`).
- Baseline: `main`/`origin/main` at `d5a05069169892c3b567922077aea0226e25a6a7`.
- Merged B1/G1 commits on current history: `3164104`, `743cbc1`, merge `3cd00a2`.
- Prior ordered delivery record: `odd/tasks/s11ab-ordered-pr-delivery.md`.
- C5 evidence record: `docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md`.

## C5 rebuild/hash work unit
1. Run the focused installer/setup-assist contract tests with `PYTHONPATH=<worktree>/src`.
2. Build the frozen bundle and compile setup into ignored `build/` output; do not execute the installer.
3. Compute the setup SHA-256 and compare it with the recorded C5 artifact `7ff33e5dc847e05b02f1d3789200c5c0c435af37b729247c0b9380a42eea8f35`.
4. If the hash differs, stop before VM execution and request explicit authorization for disposable-VM re-proof. If it matches, record that the existing C5 proof applies to the reproduced artifact.

## Rebuild evidence
- Focused contracts: `136 passed, 1 skipped` with `PYTHONPATH=<worktree>/src`.
- Frozen bundle build: passed for version `0.2.0`.
- Inno Setup 6.7.3 compile: passed; output `build/c5-rebuild/yasb-limitora-0.2.0-setup.exe` (ignored, 11,054,574 bytes).
- Produced SHA-256: `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394`.
- Recorded C5 SHA-256: `7ff33e5dc847e05b02f1d3789200c5c0c435af37b729247c0b9380a42eea8f35`.
- Historical verdict: mismatch; this led to the authorized disposable-VM C5 re-proof recorded below.
- Caveat: ambient pytest was 9.1.1 while the project pins `<9`; the focused suite passed despite this environment mismatch.

## Historical VM re-proof pause (superseded by attempt5)
Before attempt5, the user-authorized disposable-VM C5 re-proof was paused because the required one-login checkpoint preparation could not be completed at that time. The subsequent attempt5 used checkpoint v3 and is recorded below; the earlier pause is preserved as chronology, not as current status.

The zero-touch harness exists only under the ignored `build/s11b-lifecycle/` of sibling worktree `yasb-limitora-s11b-reconciled`, currently on stale branch `feat/s11b-transaction-closeout-v2` at `93a802e`. Before media preparation, switch that clean worktree to a new branch from `origin/main` and verify `HEAD=d5a0506` while preserving ignored harness files. Never build the candidate from the stale branch. Run a read-only storage/VM preflight before any VM mutation.

## C5 media preparation
- Applied the cross-session handoff first: sibling harness worktree `yasb-limitora-s11b-reconciled` now uses branch `build/c5-reproof` at `origin/main` / `d5a0506`; the ignored harness remained intact and the tracked tree is clean.
- Read-only VM/storage preflight passed: VM `s11b-69c7ff5-20260922-050224-606df2ed` is Off, SCSI 0/3 is free, the proposed checkpoint name has no collision, D: and F: report Healthy/OK, and no VM mutation occurred.
- Dedicated media: `build/s11b-lifecycle/s11b-c5-299-inputs.iso` (ignored sibling harness), 11,218,944 bytes, SHA-256 `2f0eb9b4ac502f1930623bcdad6413d762e0f3e2243445c4b6cfe16c94311c86`, label `S11BINPUTS`.
- Roundtrip identities: setup `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394`; watcher `57d7ce68ece311e8c58b1c1d29c8899535182cb628c5e98b9737961ae018a95c`; scenario 09 `8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93`.
- Independent verification passed: scenario validation exit 0, ISO roundtrip `PASS 8 / FAIL 0`, controls/custody consistent, historical S11b artifacts preserved, clean dismount, no installer execution, and no VM mutation.

## #304 integration and reusable C5 plan
- Fast-forwarded `feat/s11b-issue-299-closeout` from `d5a0506` to `origin/main` at `e2eb9e73e9c6869764e70b8823afe8e6fb0f64b0`; preserved this untracked task record byte-identically (pre/post SHA-256 `0cb28077c20de05b6f26ec8906f9597662468a4052b76f52bb726c73be865215`).
- Reusable checkpoint: `clean-windows-universal-bootstrap-v3`, Standard checkpoint ID `3842be2c-a8a3-4cdb-98e2-0905179b999a`.
- Frozen bootstrap remains unchanged. C5 needs a per-run `runner.ps1`, minimal reusable scenario, deterministic expected-artifact manifest, versioned C5 step data, and a dedicated offline semantic verifier.
- Test-first plan: observe missing-contract RED; implement guest runner/fixtures; implement positive and negative verifier cases; update source custody/README; run focused and full checks; dry-run host orchestration; then perform the authorized VM run and verify extracted evidence.
- Writable-input fallback limitation remains explicit: pre/post tree integrity cannot detect transient tamper that is reverted before final hashing.

## C5 reusable implementation evidence
- Test-first implementation observed initial RED (`15 failed, 5 passed`), then GREEN; correction regressions also observed RED before GREEN.
- Final independent pre-live verification: focused C5 `20 passed`, source custody `5 passed`, full proof-harness `68 passed`, Windows native `11 passed`, PowerShell 5.1 and pwsh AST `BAD=0`, source manifest 18/18 identities valid, and `git diff --check` clean.
- Frozen bootstrap SHA-256 remains `35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7` and is not modified.
- Real host stager dry-run completed with `result: planned` and created no VHDX/directory. Independent review found and corrected a root-scenario schema contradiction, archive input/evidence layout mismatch, PowerShell array-binding defect, and record-level dialog fail-open omission before live execution.

## Live attempt evidence
- Attempt 1 (`20260928T084422Z-939f515b333940b8ba03b34ee2a538f5`) failed before guest execution with Hyper-V `0x800705AA`: 8,192 MiB static RAM could not be allocated. Event 51 was mapped to temporary virtual disk 6 during harness VHDX formatting, not physical D:/F:/C:; no installer ran.
- Before recovery, the failed-run records, both staged VHDX, checkpoint-v3 VMRS/vmcx/vmgs, live VMRS, and event exports were copied to physical disk G: under `yasb-limitora-evidence/issue-299-c5/failed-20260928T084422Z-0x800705AA/`; 24 files were marked read-only and all manifests/hashes verified.
- Attempt 2 restored checkpoint v3 successfully with stable identity and no RAM error, but exposed a candidate defect before setup execution: `run-c5-silent-uninstall.ps1` referenced undefined `$Evidence` instead of `$EvidenceRoot` under StrictMode. The runner exited 1, `shutdownRequested=false`, the host timed out after 600 seconds, both run disks were detached, evidence was preserved, and no setup or uninstaller executed. The defect was corrected test-first; independent verification passed 21 focused / 69 full harness tests, custody, AST, and dry-run gates. The VM was then shut down gracefully and checkpoint/evidence identities remained unchanged.
- Attempt 3 used the corrected runner but again failed before guest execution during checkpoint restore: Hyper-V `0x8007000E` could not initialize the 8,192 MiB static VM even though preflight commit headroom was 9.419 GiB. This proved the 9 GiB gate insufficient under volatile host pressure. No setup or uninstaller executed.
- Attempt 4 ran after Zen was closed (14.53 GiB physical free, 18.85 GiB commit headroom). Checkpoint restore and guest bootstrap succeeded; setup exited 0 with the exact `1d58f361...` artifact and the before capture proved the two fixture files plus app/uninstall registration were present. The uninstaller process returned and self-deleted normally, then the runner failed because it attempted `Get-Item unins000.exe` after process exit. The VM was shut down gracefully. The detached evidence VHDX was mounted read-only, 11 files were recovered and verified byte-for-byte, and the VHDX hash was unchanged by inspection. No uninstall exit record or after capture exists; at that point C5 remained unproved.
- The self-delete defect was corrected test-first by capturing executable path/size/hash before launch and using those stable values in the post-wait record. Independent verification passed 23 focused / 71 full proof-harness tests, custody, both PowerShell ASTs, diff check, and a fresh attempt5 dry-run; frozen bootstrap remains unchanged.

## Attempt 5 current-tree evidence — PASS with caveats
- Recovered attempt5 evidence from the disposable VM `s11b-69c7ff5-20260922-050224-606df2ed` recorded setup `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394` (11,054,574 B), uninstaller `02431245dfe2a60b55d16f6606929474ef5b8c432339afe73e9070862a390a8c`, and both 32-byte fixtures `e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795`.
- Checkpoint v3 was `3842be2c-a8a3-4cdb-98e2-0905179b999a`; bootstrap `35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7`; runner `386fd6c3cc859f54c02c6c7db67c27153dba2f91e71ae0416dff805c13d04bc2`; input tree `3b614966581e3d6f8f182ed122c58687dd69f00938a9cf98c8558b184475380b`; evidence VHDX `8cf289225044fd389ce61c8616557f01d67f107ca75ad0244273c09f06545207` was unchanged before/after read-only mounting.
- Install and uninstall both exited `0`; app and uninstall key were present before and absent after; both fixtures survived byte-identically; `dialogAnswerAttempted=false`; no `dialogObserved` claim is made. `done.json` reported success, runner exit `0`, `inputUnchanged=true`, `shutdownRequested=true`; VM Off and run disks detached.
- The generic verifier printed `VERDICT: PASS`; the dedicated verifier printed `C5 VERDICT: PASS scenario=silent-uninstall-with-state-root`. Read-only mount recovery, a short-path copy, 14/14 evidence comparisons, 9/9 input comparisons, and offline verifiers supplied the current-tree PASS.
- Host provenance remains `overall=failed` because the original MAX_PATH extraction reached 275 nested-path characters. This provenance failure and the required workaround are preserved, not rewritten as a clean host orchestration result.
- Caveats remain: writable-input pre/post hashing cannot detect transient tamper restored before post-hash; there is no zero-dialog claim; the uninstaller hash was observed but not pre-pinned; v7 `PASS_WITH_FINDINGS` and C7/C10 remain unchanged; and full S11a/S11b lifecycle scenarios were not rerun, so their OpenSpec completion boxes remain unchecked.

## Current state
Attempt5 establishes **C5 PASS with caveats on the current tree**. The disposable VM is Off with run disks detached. Task 7 remains pending through final record-slice review and remote delivery. Three local work-unit commits exist; no push, PR, merge, or issue mutation has been performed for #299.

## Selected stacked-to-main delivery plan
The candidate is split into a three-PR stack targeting `main`; remote delivery is not claimed here. Every committed slice was verified from a clean detached worktree.

1. **Slice 1 — guest runner:** commit `b084a04`, 385 changed lines. Includes the guest runner, C5 fixtures, and runner-focused tests; it does not import or require the semantic verifier.
2. **Slice 2 — semantic verification and custody:** commit `6c72690`, 668 changed lines. Includes the semantic verifier, verifier-focused tests with independent helpers, source custody, and the proof-harness README contract. The user explicitly approved `size:exception` for this PR because the semantic verifier and its fail-closed regression suite are one atomic review unit. Native review found and the bounded correction closed two deterministic gaps by hashing the archived scenario and fixture bytes; focused/full checks then passed.
3. **Slice 3 — evidence records:** this commit, 264 changed lines before this delivery-plan update. Includes evidence, ODD, and OpenSpec records that document the justified outcome and preserve existing caveats and historical claims.

No slice has been pushed, opened as a PR, merged, or remotely delivered yet. Native reviews for slices 1 and 2 are approved and acknowledged; slice 3 retains its own review and required-CI gate.
