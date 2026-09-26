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


- S11b now proceeds on chained branch `feat/s11b-transaction-closeout` from S11a commit `bd31f71`.
- PyInstaller **6.22.3** is installed in the active Python 3.10.5 environment; the earlier `pyinstaller_missing` record is stale and must not be used as the current blocker.
- Initial mapping found relative build-path/version-binding defects plus same-path new-uninstaller and owned `.failed` cleanup gaps; S11B-1/S11B-2 now cover and correct them.
- The reported S11a delimiter mismatch was reproduced as stale; `SetupAssistant.isi` required no S11b edit.
- Required native lifecycle proof is blocked by the safety audit, so S11b stays unchecked.

## S11b implementation evidence — S11B-1/S11B-2 complete

- The reported S11a delimiter mismatch was stale; `SetupAssistant.isi` remained unchanged.
- Strict-TDD RED: focused pytest produced **10 failed, 80 passed** before implementation.
- GREEN: `python -m pytest -q --strict-markers tests/test_inno_script.py tests/test_setup_assist_protocol.py` → **90 passed**; parent spot-check reproduced the same result.
- Ruff, `py_compile`, and `git diff --check` pass on the bounded implementation surfaces.
- The build driver now resolves caller-relative source/output paths, bounds/parses build-info JSON, and binds its version to `--app-version` before ISCC.
- Rollback now uses canonical-directory ownership rather than uninstaller-string inequality and removes only a transaction-owned `.failed` quarantine after prior-payload restoration.
- Conservative source+test footprint: **373/400** lines (25 additions + 5 deletions in Inno, 230-line new driver, 113 test additions).
- Native assessment was unavailable and therefore required an independent verifier; the required lifecycle proof is now blocked by the safety audit.

## S11b independent verification — safety audit BLOCKED

- Independent focused verification: **90 passed**; Ruff, `py_compile`, and `git diff --check` passed.
- Native Windows proof: **11 passed**.
- Full suite: **952 passed, 4 skipped**.
- Real PyInstaller 6.22.3 frozen build and frozen smoke passed for version `0.2.0`.
- Native ISCC compile passed and produced an **11,053,955-byte (old branch; must be produced by a rebuild on this branch and is not yet recorded)** temporary setup; the temporary compile directory/setup were removed, while ignored `build/frozen/` output remains.
- Before any harness construction or installer execution, a read-only safety audit ran. Verdict: **blocked**. The current runtime uses `SHGetKnownFolderPath` for Local AppData and hardcoded production uninstall-key bookkeeping for PATH/state cleanup; copied ISS/include/environment substitution cannot isolate explicit cleanup from real `%LOCALAPPDATA%\yasb-limitora` and the production uninstall GUID.
- No setup or uninstaller ran; the audit created no harness, build, or evidence artifacts. Production install/state/PATH/registry/processes were not modified.
- The user authorized a temporary isolated lifecycle harness with strict identity, stop-on-risk, evidence, rollback/preservation, and cleanup constraints. Safe installer scenarios may be conditionally isolatable, but they are not claimed or executed because the required stop condition applies when any required scenario cannot be isolated.
- S11B-3 and S11B-4 remain unchecked; the S11a/S11b OpenSpec checkboxes remain unchecked; S11 remains incomplete.

## Protocol correction decision — authorized

- The user selected bounded corrective slices before Hyper-V preparation.
- Mapping proved every current Inno-generated request invalid: Inno emits string operations plus forbidden top-level `choices`, while the runtime requires typed operation objects.
- Uninstall never emits `path-remove`; explicit cleanup is incorrectly coupled to optional PATH bookkeeping; the config checkbox cannot supply the required typed selection.
- The correction cannot fit S11b's remaining **27/400** lines without minification or weaker tests. It must precede S11b as separate ≤400-line slices.
- A sequential isolated worktree/branch from `bd31f71` is authorized to preserve the uncommitted S11b candidate. No parallel writers, VM execution, commit, merge, or publication is authorized by this decision.

## S11A-C1 correction evidence — complete, delivery pending

- Branch/worktree: `fix/s11a-protocol-closeout` at the registered isolated worktree, based on `bd31f71`; the sibling S11b candidate remained untouched.
- Strict-TDD RED: the test-first protocol correction produced **4 failures** against the invalid string/`choices` implementation.
- GREEN focused: **82 passed** across `tests/test_inno_script.py` and `tests/test_setup_assist_protocol.py`.
- The actual Pascal builder expression is evaluated against the runtime validator; six exact typed operation sequences and all install/uninstall caller mappings are mutation-covered.
- Uninstall always dispatches `path-remove` before optional `state-cleanup`; config assistance emits no invalid operation or invented defaults and remains explicitly deferred to S11A-C3.
- The clean S11a branch no longer carries the out-of-slice static `scripts/build_setup.py` assertion; S11b will retain/reapply its driver tests in S11B-2R.
- Independent verification: Ruff clean, native Windows **11 passed**, full suite **944 passed / 4 skipped**, native ISCC 6.7.3 compile passed with one temporary **2,102,308-byte (old branch; must be produced by a rebuild on this branch and is not yet recorded)** setup, then removed.
- Source+test footprint: **288/400** changed lines (228 additions + 60 deletions). No installer ran, no commit or delivery occurred, and S11a/S11b remain unchecked.
- Native review `review-614e121c9da071c1` approved and was acknowledged for exact target `sha256:8d3e39bdc32ef64a85e342be7ca8de778a8a1a5ce2839cca27b6275a0936b16a`; its authority is burned. Informational follow-ups were the deferred config flag (already S11A-C3), hand-rolled Pascal test model, and JSON-fragment readability.

> **Branch note:** S11A-C2 (cleanup decoupled from PATH bookkeeping) was deliberately dropped by user decision on this branch. The S11a base on `feat/s11b-transaction-closeout-v2` retains the original cleanup behavior coupled to PATH bookkeeping. This section records historical work from the correction branch that is not present here.

## S11A-C2 cleanup-decoupling evidence — complete, delivery pending

- Sequential base: reviewed C1 local commit `6b87885` on `fix/s11a-protocol-closeout`.
- Strict-TDD RED: the new no-bookkeeping cleanup and protocol tests produced **7 failures / 54 passes** against the pre-C2 implementation.
- GREEN focused: **64 passed** across `tests/test_setup_assist_path.py` and `tests/test_setup_assist_protocol.py` with module provenance pinned to the correction worktree via `PYTHONPATH=src`.
- `cleanup_literal_state` now validates only the literal state path and delegates to the existing handle-bound native no-follow deletion; it cannot read, create, clear, or depend on PATH registry bookkeeping.
- `setup_assist` no longer constructs a registry for `state-cleanup`; standalone cleanup leaves injected/pre-existing PATH records untouched, while `path-add`/`path-remove` retain all PATH ownership behavior.
- Protocol tests inject empty registry/process discovery providers, so verification performs no host registry or process enumeration. Non-string and relative paths refuse before native deletion; native deletion failure remains a refusal.
- Independent verification: Ruff, `py_compile`, and diff checks clean; native Windows **11 passed**; full suite **947 passed / 4 skipped**.
- Source+test footprint: **162/400** changed lines (61 additions + 101 deletions). No installer, uninstaller, VM, real registry/PATH/AppData mutation, commit, or delivery occurred.
- Native review `review-06e304e582caaf70` approved and was acknowledged for exact target `sha256:4e4a38be6d57448e7858e53d38b243d72fa0f1b7ad7a2de11b471cc5a30c8286`; its authority is burned with no material findings.

> **Branch note:** S11A-C3 (truthful config assistance) was deliberately dropped by user decision on this branch. The nonfunctional installer option was not removed on this tree. This section records historical work from the correction branch that is not present here.

## S11A-C3 truthful config-assistance evidence — complete, delivery pending

- Sequential base: reviewed C2 local commit `0646725` on `fix/s11a-protocol-closeout`.
- User-selected disposition: remove the nonfunctional installer option rather than invent configuration defaults or ship a checkbox that cannot produce typed selection.
- Strict-TDD RED: **2 failed / 33 passed** while `configassist` and `ConfigWizardConsent` were still present.
- GREEN focused: **84 passed** across `tests/test_inno_script.py` and `tests/test_setup_assist_protocol.py`; targeted four-way install mapping plus uninstall/config-removal triangulation passed **4 tests / 31 deselected**.
- Removed `configassist`, `ConfigWizardConsent`, placeholder config parameter/logging, and all forwarding. `InvokePostCommitAssist` now accepts exactly the supported PATH/environment choices.
- Python runtime `config-apply` remains unchanged for a future genuine typed UI; the current installer emits no config operation or invented defaults.
- Independent verification: Ruff, `py_compile`, and diff checks clean; native Windows **11 passed**; full suite **948 passed / 4 skipped**; native ISCC 6.7.3 compile produced one temporary **2,102,323-byte (old branch; must be produced by a rebuild on this branch and is not yet recorded)** setup, then removed.
- Source+test footprint: **44/400** changed lines (29 additions + 15 deletions). No installer, uninstaller, VM, registry/PATH/AppData/process access, commit, or delivery occurred.
- Native review `review-84b6d969b819aa1f` approved and was acknowledged for exact target `sha256:dd373a6d5fab6867c213699ab4aa61bb7c378f7b3acd93f0f2686f5cbff90e22`; its authority is burned with no material findings.

> **Branch note:** On this branch, the S11a base has the typed operations, the provider page, and the registry ownership gate. Only C1's uninstall `path-remove` fragment (commit `d4b4013`) was carried from the correction slices; C2 and C3 were deliberately dropped. The S11B-2R reconciliation below ports the transaction closeout and build driver onto this corrected base.

## S11B-2R reconciliation evidence — implementation complete, lifecycle pending

- Corrected base: reviewed C3 local commit `a50335c`; fresh registered worktree `yasb-limitora-s11b-reconciled` on `feat/s11b-transaction-closeout-reconciled`.
- The original uncommitted S11b worktree remains preserved with its pre-existing `.pi/`, `NUL`, product/test/docs, and untracked build driver.
- Strict reconciliation RED: **11 failed / 84 passed** after porting tests onto the corrected base and before product/driver changes.
- GREEN focused: **95 passed**; rollback/build triangulation **11 passed** and setup-assist protocol **49 passed**.
- Ported only canonical-directory ownership for the same-path new uninstaller, fail-closed post-restoration `.failed` cleanup, the bounded absolute-path/version-bound setup driver, and their tests.
- Corrected S11a behavior remains intact: typed requests, unconditional uninstall `path-remove`, host-isolated discovery tests. **Correction for this branch (2026-09-25):** the same sentence also asserted cleanup/PATH decoupling and no installer config-assistance surface, and neither holds here. The S11a base keeps `cleanup_literal_state(registry, state_dir)` and the `state-record-missing` refusal, which is the ownership gate kept by user decision when the S11b C2 commit was dropped, and it deliberately carries the `configassist` opt-in and the tri-state provider page from commit `93aa649`, so the provider surface exists and only the dropped C3 commit would have removed it.
- Independent non-lifecycle verification: Ruff, `py_compile`, and diff checks clean; native Windows **11 passed**; full suite **959 passed / 4 skipped**; frozen build and frozen smoke passed for `0.2.0`.
- Native ISCC compile through the reconciled driver produced exactly one temporary **11,053,956-byte (old branch; must be produced by a rebuild on this branch and is not yet recorded)** setup, then removed it without execution. The compiler identified itself as Inno Setup 6 but did not expose a patch version through the shim.
- Source+test footprint: **390/400** lines (25 additions + 5 deletions in Inno, 230-line new driver, 130 test additions).
- No installer/uninstaller ran and no registry/PATH/AppData mutation occurred. S11B-3 lifecycle proof remains mandatory, so S11b and S11a stay unchecked.

## Route and next step

- Next: native review/delivery decision for the bounded S11B-2R candidate, then prepare the identity-isolated Hyper-V preflight for S11B-3. No installer execution may occur before the preflight is presented and approved.

## S11B-3 lifecycle execution evidence — eight scenarios run, two blocking findings

Executed in disposable VM `s11b-69c7ff5-20260922-050224-606df2ed` (Windows 11 Pro, standard `Users` account `s11b-lab`, zero network adapters, no Enhanced Session, immutable inputs from the read-only data ISO). No installer, uninstaller, or cleanup ran on the host, and no host registry, PATH, or AppData was touched.

- **Checkpoint strategy (user-approved, new).** One running Standard checkpoint `clean-windows-running-69c7ff5 (old branch checkpoint; not valid on this branch)` (saved state 1,330,925,568 bytes) is restored hot between scenarios, so no scenario needs a guest boot or login. Measured reverts: 126.7 / 103.8 / 100.6 / 90.6 / 103.9 s. Evidence disks are hot-added, hot-removed, extracted read-only on the host, hashed, and dismounted. Reverting the offline checkpoint from a running VM is the clean way to close the matrix: the VM ends **Off**. Restoring a running checkpoint while the VM is Off yields state `Saved`, which `Start-VM` resumes without booting or logging in.
- **Integrity guard.** Each `run-record.json` stores the guest-computed SHA-256 of its owned log, stdout, and stderr. Recomputing them on the host after hot-remove matched for every file of every accepted run, which is what makes the hot-remove path safe rather than assumed.
- **Matrix, independently verified (`gentle-ai-verify`, read-only).** 01 first-install PASS and 02 reinstall PASS (assessed earlier); 03 upgrade `0.1.0`→`0.2.0` PASS; 04 registry-phase fault PASS; 05 post-bookkeeping fault PASS; 06 locked-file PASS; 07 uninstall-preserve (`NO`) PASS with the state root byte-identical; 08 explicit-cleanup (`YES`) PASS with the state root remaining (on this branch, state-cleanup requires the registry ownership proof and refuses with state-record-missing; the installer logs assistant reported non-zero exit (code 1)). Scenario 7 and 8 used the same declared fixture (`config.json` and `quota-v2-cache.json`, both `{"fixture":"s11b-state-root/v1"}`), so the only variable between them is the recorded consent answer.
- **Consent-prompt observation.** `ConfirmStateCleanup` (`packaging/inno/yasb-limitora.iss (line reference from old tree; not valid on this branch)`) is a plain non-suppressible `MsgBox` with default `NO`, reached from `InitializeUninstall`. It surfaced during scenario 5's fault rollback (129.446 s) and in all three uninstall runs (06 14.74 s, plus 07 and 08). Recorded answers: 05 `YES` (provably inconsequential — no state root existed), 06 attempt 1 `YES`, 06 attempts 2–3 `NO`, 07 `NO`, 08 `YES`.
- **B2 correction (input-set change, re-verified).** `guest/hold-locked-file.ps1` is now `d68fed7ecb337646908ad7b300c69d5adaf8de83c71a04511ac021c7c8c973f0` (8,319 B) and writes declared `holder-start.json`/`holder-end.json` records naming the locked file, its size and SHA-256, the delete-denying sharing mode, the holder PID, the release signal and its digest, and the start/release times. `guest/capture-state.ps1` is now `322abe17d17d238484c973065aa4cd0d32e1e1fdfc5f1c69dca4b510546407a4` (10,948 B), records `holderRecords` like the existing owned-log pattern, and raises its capture schema to `v3`. Regenerated set identity: custody `f406b54e9afffd162af1a47f6b20c34a28e8ebc7f390855ed43f6fbb5070027b`, ISO `ae5cd8ede6e5de46660aad5406b3129ec43264cfe3819bb57188ed8780fff6e2` (44,441,600 B), manifest `8c34320f165b066e97aaafdd4e24b4f4f86466b4723c85864b672dbb62070311`, SHA256SUMS `f1549e3c12d48e7d2e1746048842bfed92df46448511f9755d93485caf791dd6`; the four setup hashes are unchanged. `validate-guest-paths.ps1` passed and an observable ISO roundtrip passed (label `S11BINPUTS`, drive type `CD-ROM`, 11/11 members byte-equal to staging, 9/9 checksum entries valid, ISO manifest copy identical, `FINAL_ATTACHED=False`).
- **Preserved attempts.** `04-registry-phase-attempt1` (caller omitted `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, so interactive wizards ran; unverified), `06-locked-file-attempt1` (no holder artifact; superseded), `06-locked-file-attempt2` (invalid: the release signal was written 56.84 s before the uninstall, so no lock was held and the uninstall deleted everything). Attempt 2 was detectable **only** because the correction records holder times.
- **Input-set gaps found during execution.** The README does not specify the cleanup-prompt answer for the fault rollback in scenario 5 or for scenario 6; scenario 6's operation selection was left to the operator (the installed native uninstaller was chosen); nothing in the set creates the state root, so scenarios 7 and 8 had to use a declared fixture instead of product-generated state (and the user reports `quota-v2-cache.json` is legacy and slated for removal); and the README was **not** updated when the harness gained the holder records even though the README ships inside the ISO, so any future run must first ship a README-consistent input set with a new custody identity.
- **Blocking findings.** **B1 (product defect, OPEN)** — the G1 rollback Execs the uninstaller with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` (`yasb-limitora.iss (line reference from old tree; not valid on this branch)`) while `ConfirmStateCleanup` is a non-suppressible `MsgBox`, so an unattended failed upgrade hangs indefinitely in rollback; evidenced by the 129.446 s block in scenario 5's fault log against 62 ms on the registry-phase path that never reaches the uninstaller. The correction cannot have altered it because every setup and uninstaller byte is unchanged. **B2 (evidence gap, CLOSED)** — the holder precondition is now proven by declared records, a temporal chain that brackets the whole uninstall, a matching surviving-file hash, and a capture-to-record hash link; the re-check verified all six claims and refuted none.
- **Non-blocking follow-ups.** Exit code 0 despite the `RaiseException` in `CurStepChanged(ssPostInstall)`; exit code 0 with `Removed all? No` and one orphaned file after the uninstall key had already been deleted, leaving no re-install entry point; the PATH digest is identical across all 26 captures and therefore non-discriminating; `holder-end.json` is covered only by the checksum control because it necessarily appears after the last capture; the capture schema `v2`→`v3` delta is additive at output level but the source-level diff is unverifiable because `build/` is gitignored and the pre-correction bytes are gone; the root `SHA256SUMS.txt` entries resolve only against `iso-staging` and are CRLF, so plain `sha256sum -c` fails there; empty residue directories are invisible to the tree capture; the ISO interior was independently spot-checked by raw ISO9660 parse rather than by mounting.
- **End state.** VM **Off**, both checkpoints intact, no evidence disk attached, zero network adapters, evidence preserved as eight accepted evidence VHDXs plus three archived attempts. Host `EnableEnhancedSessionMode` was already `False` before S11b (user-confirmed), so nothing needed restoring; VM deletion remains unauthorized.
- **Route.** S11b stays **INCOMPLETE**. B1 requires its own bounded work unit (make the rollback's consent gate non-interactive, or make the exit code reflect the `ssPostInstall` failure) with TDD and native review. This lifecycle work unit changed only gitignored build artifacts plus this ledger, so the ledger update is the committable artifact; the artifact set itself is bound by the custody hash above, not by a commit.

## S11B-3 lifecycle re-run — zero-touch cycle COMPLETE, independent verification PASS_WITH_FINDINGS

**Status on this branch: historical, not evidence for this tree.** Every result in this section was produced on payloads built from the old branch, so it establishes nothing for `feat/s11b-transaction-closeout-v2`. A fresh disposable-VM cycle on an artifact rebuilt from this branch is pending, and the record is kept for provenance only.

Date: 2026-09-23 (local). This section supersedes the "S11b stays INCOMPLETE" route above.

- **Design (user-approved).** The guest side is unattended: the host writes a declared `scenario.json` into the evidence volume before hot-attaching it; a resident watcher inside the guest executes the declared typed steps through the existing harnesses, answers only declared dialogs programmatically, writes `done.json` plus `watcher.log`, and shuts the guest down as the completion signal. The operator's cost is exactly one login: start the watcher, then freeze the saved-RAM checkpoint `clean-windows-running-watcher-v7-69c7ff5 (old branch checkpoint; not valid on this branch)` that every cycle reverts.
- **In-band build gate.** The orchestrator writes `expected-watcher.sha256` into each evidence volume; the watcher logs its own script SHA-256 and fails closed on a mismatch. This closes the stale-CD-ROM-cache failure mode that produced two earlier invalid runs (v4 and v5 below).
- **Artifact identity (r8).** ISO `43b6f036d2a3ca2775d906a25b42153631bcf11d4d50b7a0beb8f78ca312bbca` (44,507,136 B), watcher `57d7ce68ece311e8c58b1c1d29c8899535182cb628c5e98b9737961ae018a95c` (48,261 B), manifest `05bfd91476ad699fee1a2d0320c9bb760d6684cdd3c77e79cd88c4f32467ad7b`, `SHA256SUMS.txt` `78ba6e5a30d0dd550f83736e582d6b5b647f5c791f823dca4690ff3da9aa2c3e`, custody `6a50f08e7ff5d97d2fa57e0fc1e7f050272e81c847db55719b143c4e9e3633fa`; the four setup hashes are unchanged from the earlier rebuild. Roundtrip PASS (12/12 members byte-equal, 10/10 checksum entries, `FINAL_ATTACHED=False`), `validate-guest-paths.ps1` PASS, read-only set re-check PASS (289 checks).
- **Run.** Eight declared scenarios, all `success`, about 26 minutes in the disposable VM, evidence extracted to `D:\01_System_Images\Virtual_Machines\s11b-zero-touch-run-v7\` with a per-scenario cross-check pass: first-install 178.2 s, reinstall 191.2 s, upgrade 212.7 s, fault-registry-phase 193.6 s, fault-post-bookkeeping 235.0 s, locked-file 211.9 s, uninstall-preserve 200.0 s, explicit-cleanup 193.1 s. `ORCHESTRATOR FINISHED SUCCESSFULLY (8 cycle(s))`.
- **Programmatic consent (the zero-touch claim).** `uninstall-preserve`'s uninstall step records `dialogAnswered: true`, its watcher log shows `answering declared dialog (button=7)`, its uninstaller log shows the prompt at 22:15:53.757 and `User chose No.` at 22:15:54.499 (0.742 s), and the state-root fixture survives in the `after` capture. `explicit-cleanup` shows button 6, `User chose Yes.` 0.621 s after the prompt, and the fixture remaining (on this branch, state-cleanup requires the registry ownership proof and refuses with state-record-missing; the installer logs assistant reported non-zero exit (code 1)). No human touched either dialog.
- **Declared failures.** `fault-registry-phase`'s fault setup exited 1 and the cycle still succeeded (the new `expectFailure` declaration), with `S11B_FAULT_REGISTRY_PHASE_MARKER` and `..._EXCEPTION.` in its setup log; `fault-post-bookkeeping` carries its marker and exception with exit code 0.
- **Clean baseline.** `first-install` started from an app root with zero files and ended with 111 files plus the uninstall key, so this run's first install is a true first install (the two earlier invalid runs started from a dirty chain).
- **Locked file.** `holder-start.json`/`holder-end.json` record the locked file, its SHA-256, the delete-sharing-denied mode, the holder PID, the release signal digest, and `heldSeconds = 7.737` with `exitPath = normal-exit-after-explicit-signal`; the uninstaller log shows `Failed to delete the file; it may be in use (32)` at an instant inside the hold window and `Removed all? No`.
- **Independent verification (read-only, `gentle-ai-verify`).** Verdict `PASS_WITH_FINDINGS`: C2, C3, C4, C6, C8, C9 clean; C1 and C7 pass on the facts with wording/bracket caveats; **C5 FINDING** — this run alone does not dynamically prove the B1 fix, because its post-bookkeeping fault never reaches the uninstaller rollback (the pre-fix 129.446 s block came from that path), so B1's dynamic proof still needs a scenario that runs the installed uninstaller silently with a state root present; **C10 FINDING** — the run log carried no orchestrator hash or set identity.
- **Findings disposition.** C10: the orchestrator now writes a startup identity header (its own SHA-256, the VM, the checkpoint, the required watcher hash, the scenario directory) before any cycle runs, and the v7 run root carries a declared post-run `run-custody.json` annotation with the identities of that run (orchestrator `f4f7faa44f5b4a2b43e55b3c98cb70e5d38fa09b7e82506e21411f9fa97afcac` as it ran, the r8 set identity, the run summary, the verification verdict), explicitly labelled as an annotation and not as part of the extracted evidence. C5: **PASS with caveats (2026-09-24)** — the `silent-uninstall-with-state-root` scenario ran 1/1 successfully in 208.1 s against the v7 checkpoint with the r8 watcher stamp, proving that the B1-fixed installed uninstaller under `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` completes without a blocking prompt and preserves the declared state-root fixture via the expected safe suppressed default; evidence and caveats in [the C5 evidence report](../../docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md). The original v7 `PASS_WITH_FINDINGS` verdict is unchanged; C5 was a follow-up gap, not a v7 reversal. The B1 correction itself remains proven **on the old branch** by its contract tests, its reviewed commit `355838f` (which is not on this branch: the B1/G1 work still has to be carried here) and the compiled setup identity recorded in `odd/tasks/g1-rollback-consent-gate.md`.
- **Harness defects fixed during this closeout (H1–H12).** Recorded in `odd/tasks/s11b-zero-touch-cycle.md` (Z6 section): a saved-RAM checkpoint freezing an absolute wait deadline; caption-only dialog matching; the PS 5.1 PSMethod-to-delegate cast; `Write-Output` swallowing logs inside a function whose value is assigned; StrictMode on optional manifest properties plus `WaitForExit` polluting step results; `ArrayList` to `List<DialogAnswerSpec>`; `MSFT_DiskImage.Number` versus `DiskNumber`; a failed cycle leaving its evidence disk attached; fault steps needing a declared `expectFailure`; a stalled `Get-VM` in a wait loop; an Inno uninstaller re-executing from a temporary copy so its dialog has no process-tree owner; and the checkpoint-carried CD-ROM cache that made a stale guest build look like a harness failure.
- **Host-disk incident.** The host volume `E:` (WDC WD5000AVDS, 67,831 power-on hours) began failing large *new* allocations with `The drive cannot find the sector requested (0x8007001B)` while SMART reported zero errors and the volume reported `Healthy`: `Checkpoint-VM` RAM saves failed four times, `Remove-VMCheckpoint` merges failed, and `Move-VMStorage` failed reading a chain parent delta. After the operator freed space and defragmented the volume, a 2 GB sequential write passed again; the VM and all ten checkpoints were moved intact with `Move-VMStorage -DestinationStoragePath` to `D:\01_System_Images\Virtual_Machines\` (19.4 min), and this run produced its evidence there. The two checkpoints the earlier lifecycle proof names remain intact, and the clean base image was never merged into.
- **End state.** VM `Off` after the final cycle, checkpoint `clean-windows-running-watcher-v7-69c7ff5 (old branch checkpoint; not valid on this branch)` intact, no evidence disk attached, zero network adapters, evidence plus the custody annotation preserved. No host registry, PATH, or AppData was touched outside the disposable guest.
- **Route.** S11B-3 is complete (the lifecycle re-run and its independent verification happened) and S11B-4 is complete for the ledger and OpenSpec update, both carrying the two declared findings above. S11a and S11b are NOT marked complete on this branch; the lifecycle proof was run on the old branch and a fresh disposable-VM cycle on an artifact rebuilt from this branch is pending. C10 is mitigated for forward-looking runs by the orchestrator identity header and post-run custody annotation (the original v7 extracted log retains its historical identity limitation; the post-hoc annotation is not part of the extracted evidence); C5 was **PASS with caveats** on 2026-09-24 **on the old branch** by the `silent-uninstall-with-state-root` dynamic proof (evidence and caveats in [the C5 evidence report](../../docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md), which on this branch reads "Not yet verified"); on this branch the C5 dynamic proof is pending a fresh rebuild and cycle. The committable artifacts of this work unit are this ledger, the OpenSpec task/progress updates, and the untracked spec `odd/tasks/s11b-zero-touch-cycle.md`; nothing is committed without explicit user authorization.
