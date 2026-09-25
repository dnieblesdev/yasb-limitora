# Zero-touch lifecycle cycle — manifest driver plus resident guest watcher

> **Branch reconciliation note.** This file was carried from the old branch
> (`feat/s11b-transaction-closeout-reconciled`, head `84ddcb3`). The setup hashes, checkpoint
> identities, watcher stamps, and payload references recorded below were produced on that tree and do
> not describe `feat/s11b-transaction-closeout-v2` (head `e0c2794`). A fresh disposable-VM cycle on
> an artifact rebuilt from this branch is pending; no proof is claimed for this tree until that
> rebuild and cycle complete. The historical record is preserved below for continuity.
>

## Goal

Remove the operator from the guest side of the S11b lifecycle loop. Today the host side is fully
automated (evidence disk creation, hot-add, checkpoint revert, extraction, hashing, cross-checks) and
the only manual work is typing harness commands inside the VM console, because the approved isolation
rules allow exactly one channel: the guest keyboard and screen. This work unit turns the evidence
volume into a declared two-way channel so the operator needs **one login in total** and nothing after
that.

## Design

### Channel

The evidence volume is already the sanctioned data path: the guest writes evidence to it and the host
reads it, offline, after hot-remove. The host can also **write before attaching**. That makes the
volume a declared two-way channel without touching a single isolation rule: no network adapter, no
PowerShell Direct, no Enhanced Session, no KVP/Data Exchange, no writable share, no clipboard.

### Manifest (host writes it into the evidence volume root, offline)

`scenario.json`, declared and content-hashed, one per scenario cycle:

```json
{
  "schema": "gentle-ai.yasb-limitora.s11b-scenario/v1",
  "scenario": "post-bookkeeping",
  "steps": [ ... ordered typed steps ... ],
  "dialogAnswers": [ { "match": "Remove the mutable configuration", "answer": "NO" } ],
  "shutdownWhenDone": true
}
```

Step kinds, each mapping onto a harness the project already trusts:

- `setup` — `run-setup-uninstall.ps1 -Kind setup` with the declared executable and argument list.
- `uninstall` — `run-setup-uninstall.ps1 -Kind uninstall` against the installed native uninstaller.
- `capture` — `capture-state.ps1` with optional `logFromPhase` / `holderRecordFromPhase` linkage.
- `fixture-state-root` — create the declared disposable state-root fixture with declared file content.
- `holder-start` — `hold-locked-file.ps1` with its declared evidence records, run as a child process.
- `holder-release` — create the declared release signal, which also ends the holder.
- `wait` — bounded settle, to let the guest lazy writer reach the disk.

### Watcher (guest, resident, captured in the checkpoint)

A PowerShell script that runs in the interactive session, started once by the operator and then
preserved by the checkpoint's saved RAM. Each cycle it:

1. resolves the fixed local volume whose label is exactly `S11BEVIDENCE`;
2. waits bounded for `scenario.json` at that volume's root;
3. refuses a manifest that is already recorded as run (its scenario directory exists) or that does not
   match the declared schema;
4. executes the steps in order through the existing harnesses, with the same fail-closed rules;
5. answers a dialog **only** when it matches a declared `dialogAnswers` entry, and aborts the cycle
   without shutting down when an undeclared dialog appears;
6. writes `done.json` with the executed steps, their exit codes and timestamps;
7. shuts the guest down cleanly.

Because the watcher lives in the checkpoint's saved memory, reverting the checkpoint restores the
running watcher, so the next attach is picked up with no logon.

### Dialog answering

Inno's dialogs are native `#32770` windows owned by the step's process. The watcher locates the
declared dialog by window class plus a declared text match, then answers it with
`PostMessage(hwnd, WM_COMMAND, <button id>, 0)` — `IDNO` = 7, `IDYES` = 6. This posts the exact button
the operator would have clicked, needs no focus, and cannot be confused by timing or by another
window stealing the foreground. An undeclared dialog, or a declared one that cannot be matched, is a
fail-closed stop.

### Completion detection

The watcher's clean shutdown is the completion signal. The host polls the VM state, needs no channel,
and therefore keeps the isolation model intact. A cycle that does not shut down within its bounded
budget is a failure: the host records it and leaves the guest up for inspection.

### Host loop per scenario

1. Assert the VM is `Off` (previous cycle) or `Running` (first cycle).
2. Revert the checkpoint, then `Start-VM` when the revert leaves the VM `Saved`.
3. Create and format the evidence volume, mount it on the host, write the manifest, dismount.
4. Hot-add the volume (the checkpoint's config has no evidence disk, so the revert above must come
   first).
5. Wait bounded for `Off`.
6. Hot-remove, mount read-only, extract, hash, cross-check guest-computed against host-recomputed
   hashes, dismount.

## Consent-scenario argument list (declared deviation)

The B1 fix makes `ConfirmStateCleanup` and `PromptManualClose` suppressible, so under
`/SUPPRESSMSGBOXES` the consent dialog no longer appears and the suppressed default is used. Scenarios
that exist **to answer that dialog** therefore cannot use the fully silent set any more:

- rollback and fault scenarios keep `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`;
- consent scenarios (the locked-file uninstall and both uninstall-preserve/cleanup scenarios) use
  `/VERYSILENT /NORESTART`, which is what a human running the uninstaller produces: the real dialog
  appears and is answered.

This is an intentional, documented deviation and must be stated in `README.md` next to the per-scenario
commands.

## Non-goals

- No product change: the installer script, the runtime, and their tests are untouched by this work unit.
- No relaxation of any isolation rule, and no new host-to-guest software channel.
- No change to the evidence format: the same harnesses write the same artifacts, so the existing
  integrity checks keep applying.
- No replacement for a human decision that the product is *supposed* to ask for: the declared answers
  are the operator's decision, recorded in the manifest and hashed.

## Constraints

- Every declared answer, fixture, and manifest must be labelled as a declared input, hashed, and
  reported as such, never presented as product-generated state.
- Fail closed everywhere: an unexpected dialog, an unmatched manifest, an already-used scenario
  directory, a missing volume, or a failed step stops the cycle without shutting the guest down.
- The watcher must never delete or modify anything outside the evidence volume and the paths the
  harnesses already own.
- Technical artifacts in English; no commit without explicit user authorization.

## Tasks

1. [x] Write the watcher with the manifest executor, the dialog answering, and the fail-closed stops.
2. [x] Write the host-side orchestrator that runs the whole scenario list unattended.
3. [x] Update the input-set README with the watcher, the manifest schema, the consent-scenario argument
   deviation, and the one-login requirement.
4. [x] Ask the operator for exactly one login: start the watcher, then freeze the new checkpoint that
   contains it running.
5. [x] Rebuild the input set for the fixed installer: frozen payload, four setups, ISO, manifest, checksum
   control, custody, and the observable roundtrip.
6. [x] Run the automated cycle for all eight scenarios and verify the extracted evidence independently.

## Evidence to record

- The manifest actually executed for each scenario, hashed, next to the evidence it produced.
- `done.json` per cycle with the step exit codes and timestamps.
- The host-side timing per cycle: attach, wait for shutdown, extraction, checkpoint revert.
- The verifier's verdict on the re-run evidence, including the declared programmatic consent answers.

## Z5 rebuild evidence — complete (post-B1-fix input set)

- Pre-fix generation archived outside the tree at
  `E:/10_VirtualMachines/yasb-limitora-s11b/s11b-69c7ff5-20260922-050224-606df2ed/superseded-inputs/pre-b1-fix/`
  (167 MB with `ARCHIVE-NOTE.md`). Before the ISO was replaced, the on-disk ISO was confirmed
  byte-identical to the archived copy (`ae5cd8ed…`), so no pre-fix byte was lost.
- Both fault variants regenerated from the B1-fixed production ISS. Production ISS and both variants now
  hold `SuppressibleMsgBox` count 2 / plain `MsgBox` count 0, with the fault markers
  (`S11B_FAULT_REGISTRY_PHASE_MARKER`, `S11B_FAULT_POST_BOOKKEEPING_MARKER`) intact. Fault ISS sha256
  `56e7c5af…` (registry-phase, 16,314 B) and `0358c0cc…` (post-bookkeeping, 16,056 B).
- Four setups recompiled from the B1-fixed sources against the unchanged frozen payload (the `69c7ff5` payload identity is from the old branch and does not describe this tree):
  production `7ff33e5d…` 11,052,514 B (old branch; must be produced by a rebuild on this branch and is not yet recorded); synthetic 0.1.0 `608ba3df…` 11,052,522 B; fault-registry-phase
  `d5583527…` 11,052,627 B; fault-post-bookkeeping `25f11751…` 11,052,571 B. The payload was deliberately
  not rebuilt, so all 109 payload entries keep their payload identities (the `69c7ff5` build commit is from the old branch) and the manifest's setup/README
  declarations state that split explicitly (`source_commit` was `69c7ff5` on the old branch; on this branch it must be determined by a rebuild).
- README updated for the set identity (payload (the `69c7ff5` payload identity is from the old branch), B1 fix `355838f`, `packaging/inno/` identical at
  HEAD `49d43a0`, B1-fixed production ISS) and corrected for the checkpoint requirement: a **new**
  checkpoint must be frozen with the watcher running, because the pre-watcher
  `clean-windows-running-69c7ff5 (old branch checkpoint; not valid on this branch)` does not contain it. New identity `8661a842…`, 19,794 B.
- Re-staged with byte-equality asserts: the watcher (`451b6e30…`, 38,442 B, LF as authored), the README and
  the four setups; every staged file equals its root counterpart, and the watcher plus all six harnesses
  parse with 0 errors under Windows PowerShell 5.1 (`Desktop`, 5.1.26100.9444) with no .NET Core-only
  `GetRelativePath` usage (the only occurrence is a comment).
- Manifest regenerated from the persisted structure with a serializer fidelity proof (byte-identical
  round-trip before mutation) and a full self-audit: **262** `generated` entries (+2 root/staged watcher)
  and **10** `iso_contents` entries (+1 watcher), every one verified against actual bytes; `manifest.json`
  `e2a23e14…`, 122,968 B, both copies identical.
- Checksum control regenerated from the staging tree, sorted by hash, CRLF: 10 entries (`2751fc51…`,
  996 B), both copies identical.
- ISO rebuilt with `build-data-iso.ps1 -StagingRoot iso-staging -OutputIso s11b-inputs.iso`:
  `be2bedefd8cc…`, 44,494,848 B, label `S11BINPUTS`, 12 members.
- `validate-guest-paths.ps1` PASS; observable roundtrip PASS: 12/12 expected == actual members, 12/12
  byte-equal to staging, 10/10 checksum entries valid, ISO manifest copy identical, `FINAL_ATTACHED=False`.
- `custody.json` updated to the new seven artifact identities (`a728a094…`); independent read-only set
  re-check after all writes (custody artifacts, manifest entries, ISO member set, checksums, and no stale
  pre-fix identity in any control) passed with 289 checks.
- No setup, uninstaller, product executable, guest harness, or VM ran; only the host wrote the staged tree
  and mounted the rebuilt ISO read-only.

### H1 correction — evidence-volume wait must not carry a frozen deadline (supersedes the identities above)

- **Defect found before Z4, while preparing the one-login step.** `Wait-ForEvidenceVolume` used an
  absolute 600 s deadline computed when the watcher started. The watcher is captured in a checkpoint's
  saved RAM, so every revert resurrects that process with the deadline already frozen in memory, and this
  VM has Hyper-V Time Synchronization `enabled=True`: on resume the guest clock jumps to host time, the
  deadline is already past, the loop exits and the watcher throws, leaving the guest up. Every cycle
  starting more than ~10 minutes after the one login would fail, and the eight cycles take far longer
  than that.
- **Fix.** The evidence-volume wait is now intentionally unbounded: 2 s polling with one log line every
  30 s of guest-active time. The removed `EvidenceWaitTimeoutSeconds` had no other use. Bounded budgets
  stay where a live cycle owns them (`scenario.json` 300 s, dialog 120 s, holder/dialog waits per step,
  host shutdown wait 600 s), and the watcher `.NOTES` header now documents the resident-wait semantics:
  the host owns the per-cycle budget.
- **Re-verification of the whole set after the fix.** Windows PowerShell 5.1 AST parse of the watcher: 0
  errors, no .NET Core-only API. Re-staged (byte-equality asserts), manifest and checksum control
  regenerated and fully self-audited, ISO rebuilt, custody updated, `validate-guest-paths.ps1` PASS,
  observable roundtrip PASS (12/12 expected == actual members, 12/12 byte-equal, 10/10 checksum entries,
  ISO manifest copy identical, `FINAL_ATTACHED=False`), and the read-only set re-check passed with 289
  checks.
- **Final identities** (these replace the watcher, manifest, checksum-control, ISO and custody values
  listed above; the four setups, the README, the payload entries and the 10-entry checksum control stay
  as declared there): watcher `42c972c73a93e818550bb263cce15830b4d718c5de189a0169b61fa8cac67050`
  (39,271 B); manifest `0f5167a80c988afd88da901049514c1f9249291edda4afe6c1cebc8a332a8669` (122,968 B);
  `SHA256SUMS.txt` `297e180ac9c3e0b5e92713d7b002a3d599b681cd91ebb243388f5033259976d0` (996 B); ISO
  `bcfc003a7dc51cf459ad92b9f7725d06247a5693a6de57795975281c8ccdbbbf` (44,496,896 B); custody
  `6815f1be429357c0fcd95f183e0de6669521c89d9c58f0ce33109ab605ac1251`.
- **Z4 started.** The VM was restored from `clean-windows-running-69c7ff5 (old branch checkpoint; not valid on this branch)` (`Saved` → `Running`, no boot,
  no logon) and the final ISO was ejected/re-inserted so the resumed guest cannot serve a stale CD-ROM
  directory; the DVD drive stays at 0/2 pointing at the rebuilt ISO.

### H2/H3 correction — dialog answering would have failed every cycle (supersedes the identities above)

- **H2 (dialog match read the wrong text).** `EnumCallback` matched a declared `dialogAnswers[].match`
  against `GetWindowText` of the `#32770` window only, i.e. the dialog's caption — for an Inno message box
  that is the setup/uninstall title, not the message body. The declared answers name the body
  (`"Remove the"`), so the consent scenarios (7, 8) would either be flagged as an undeclared dialog
  (fail-closed) or, if the caption were empty, be ignored and hang until the 15-minute step timeout.
- **H3 (PowerShell 5.1 cannot cast a PSMethod to a delegate).** `Scan-ForDialogs` built its callback with
  `[S11B.WatcherNative+EnumWindowsProc]($scanner.EnumCallback)`; under Windows PowerShell 5.1 that raises
  `Cannot convert the "... EnumCallback(...)" value of type "System.Management.Automation.PSMethod" to
  type "S11B.WatcherNative+EnumWindowsProc"`. The cast sits outside the `try` that tolerates an
  `EnumWindows` failure, so the first `setup` or `uninstall` step of every cycle would have failed with
  that exception. A static parse check cannot see this class of defect; it needs execution.
- **Fix.** `WatcherNative.CollectDialogText` walks the dialog and every descendant window
  (`EnumChildWindows`) and matches the declared fragment case-insensitively against the combined caption +
  message text; `Scan-ForDialogs` now binds the callback with
  `[System.Delegate]::CreateDelegate([S11B.WatcherNative+EnumWindowsProc], $scanner, $scanner.GetType().GetMethod('EnumCallback'))`.
  The `.NOTES` header and the README's declared-fixture note state both semantics.
- **Behavioral verification on the host (no VM, no product).** The watcher's C# block compiles via
  `Add-Type`; against a real `#32770` MessageBox (caption `Setup`, body `Remove the mutable configuration…`)
  the declared fragment matched with button id 7 and `PostMessage(WM_COMMAND, 7)` made the message box
  return `IDNO` = 7; an unrelated dialog was flagged undeclared with its body text captured; a dialog
  outside the step's process tree was ignored. PowerShell 5.1 AST parse: 0 errors.
- **Final identities** (these replace the watcher, README, manifest, checksum-control, ISO and custody
  values listed above): watcher `442acbbece10c59a253e4db673ba7e39a3d60291c28a8b0438d273174b3a8198`
  (41,027 B); README `b22f0b28c2e0eb54f8c3811df33fb07221bcbd501972c8e77dfd2a8fd5839f52`; manifest
  `422f4598c2ccf206893f3bd57073315cb8d0641b3d90b812f79d593fb4d5f81d` (122,968 B); `SHA256SUMS.txt`
  `36f75558c6183d266500b3d61279e4e1896fb126ba7b28da8ba4aba6c5ee3fe8` (996 B); ISO
  `9555b015e0835d1050c566f82f4af9c76cd63fcf77aca33739d9db4a9f1a3e24` (44,498,944 B); custody
  `88c6df3d6aa460712a62977ade75bc1478d0a180c56955360c53959dcf321cf6`. Re-run checks after the fix:
  `validate-guest-paths.ps1` PASS, observable roundtrip PASS (12/12 members byte-equal, 10/10 checksum
  entries, ISO manifest copy identical, `FINAL_ATTACHED=False`), read-only set re-check 289 checks PASS.
- **Checkpoint supersession.** The already-frozen `clean-windows-running-watcher-69c7ff5 (old branch checkpoint; not valid on this branch)` contains the
  pre-H2/H3 watcher in its saved RAM, so it is kept only as a checkpoint parent; after the watcher is
  restarted from the final ISO, a new checkpoint is frozen and used for the cycle.

## Z6 execution evidence — two partial runs, a host-disk blocker, and the verified gates

**Status: S11b remains INCOMPLETE.** The zero-touch mechanism is built, corrected and verified stage by
stage, and the first full automated cycles ran — but the run that must prove the *programmatic* consent
answers (scenarios 7 and 8) has not completed, and it is now blocked by a failing host disk, not by the
harness.

### What ran

- **Run v4 (build r6, `expectFailure` declared): 8/8 cycles success** in ~31 min
  (`first-install 155.7s`, `reinstall 151.3s`, `upgrade 337.3s`, `fault-registry-phase 284.9s`,
  `fault-post-bookkeeping 234.3s`, `locked-file 201.8s`, `uninstall-preserve 286.4s`,
  `explicit-cleanup 235s`), with a cross-check pass on every scenario. **Not valid for the consent
  premise:** the operator answered the cleanup dialog by hand in cycles 7 and 8 and in cycle 7 the
  human answer contradicted the declared one (`uninstall.log`: `Message box ... Remove the mutable
  configuration ...` at 05:27:26, `User chose Yes.` at 05:29:03; `done.json` `dialogAnswered: false`;
  the `after` state capture no longer contains `config.json`/`quota-v2-cache.json`, i.e. the state root
  was cleaned instead of preserved). Root cause H11: an Inno uninstaller re-executes itself from a
  temporary copy, so its dialog belongs to no process in the step's tree and the watcher ignored it.
- **Run v5 (build r7): 7/8 cycles success**, cycle 8 failed after the 600 s shutdown wait. The consent
  dialog appeared again in cycle 7 and the operator answered **No** (matching the declaration, but human),
  and cycle 8 hung on the unanswered dialog (`uninstall.log` 0 bytes, no `done.json`). Diagnosis from the
  evidence: the watcher in that run logged no `answering declared dialog` line and tolerated a non-zero
  fault exit **without** the `expectFailure` WARN, which identifies it as build r5 — i.e. the guest was
  executing a **stale CD-ROM view** cached in the checkpoint's saved RAM (H12), while the host served r7.
- **Corrections landed after those runs.** H9 (`expectFailure` + `Test-StepFailure`, validated by a
  6-case unit gate), H11 (declared answers matched by text over any top-level `#32770` dialog, verified by
  `DIALOG_PATH_TEST_V2` cases A–E, including a foreign-PID dialog answered with `IDNO`=7), and H12
  (the watcher now logs its own script SHA-256 and fails closed when it disagrees with the
  `expected-watcher.sha256` stamp the orchestrator writes into the evidence volume). Gates that ran green
  on build r8: real validator against all eight manifests, `Test-StepFailure` semantics, the dialog-path
  test, a host rehearsal of a full `capture` step (exit 0, 296 KB `state-capture.json`), and two smoke
  cycles in the VM with a clean programmatic shutdown.

### The host-disk blocker

While trying to freeze the checkpoint that carries the new build, `Checkpoint-VM` failed with
`The drive cannot find the sector requested (0x8007001B)` while saving RAM. Subsequent checks:

- A plain 2.5 GB sequential write to `E:` failed with the same error, with dozens of `disk` event id 51
  (`paging operation`) warnings at the same second.
- `Remove-VMCheckpoint` failed the same way (the delta merge writes), `Move-VMStorage` failed reading a
  chain parent delta, and `Set-VM -CheckpointFileLocation` is not a parameter on this host (the supported
  spelling is `Set-VM -SnapshotFileLocation`); `Move-VMStorage -VirtualMachinePath` failed at 0.6 s with
  `Failed to get VHD ('...os_4A6DB4C6....avhdx') parent: 0x8007001B` in the VMMS log.
- SMART counters for that disk (`WDC WD5000AVDS`, 67,831 power-on hours, volume `E:` labelled `LAB_465`)
  report no read errors and no reallocations; free space was 39–58 GB throughout. The evidence points to a
  physical region that the drive can no longer write (and now cannot reliably read) rather than to a
  filesystem or capacity problem: allocations of *new* large files (each checkpoint RAM save is ~3 GB,
  each merge grows a delta) hit it, while appends inside already-allocated files kept working.
- Consequence: the approved design's per-cycle RAM checkpoint cannot be created on `E:` right now, and the
  checkpoint chain cannot be migrated or cleaned from `E:`. The two checkpoints the ledger names
  (`clean-windows-offline-69c7ff5 (old branch checkpoint; not valid on this branch)`, `clean-windows-running-69c7ff5 (old branch checkpoint; not valid on this branch)`) were left intact; my intermediate
  checkpoints could not be deleted (every merge failed) and no evidence was modified.
- Salvage planned once the operator finishes freeing space on that disk: verify the disk's behaviour with a
  bounded write test, copy the extracted evidence to a different physical disk (`D:`, `TOSHIBA HDWD110`),
  and then either retry the RAM checkpoint on `E:` or rebuild the lab VM on `D:` around the clean base
  `os.vhdx` image. The clean baseline for scenario 1 is that base image, which is why the offline
  checkpoint must not be merged into it.

### Verified harness gates (independent of the runs)

- Real validator extracted from the watcher against the eight declared manifests: all VALID.
- `Test-StepFailure`: six cases PASS, including non-zero declared (WARN, continue) and non-zero
  unexpected (fail the cycle).
- Dialog path with the watcher's real functions: empty declared set flags the dialog undeclared; a declared
  answer matches a real `#32770` MessageBox and `PostMessage(IDNO)` returns 7; a dialog outside the step
  tree is answered when declared and ignored when not; `Wait-AndAnswerDialogs` against a child process
  answers and the child's box returns 7.
- Host rehearsal of a full `capture` step (evidence volume + ISO mounted): exit 0 and a 296 KB
  `state-capture.json`.
- Two in-VM smoke cycles (checkpoint → revert → volume with a `wait` scenario): the resurrected watcher
  runs, writes `done.json`, and shuts the guest down cleanly.
- Set identity and custody after every rebuild: roundtrip PASS (12/12 members byte-equal, 10/10 checksum
  entries, `FINAL_ATTACHED=False`), `validate-guest-paths` PASS, read-only set re-check PASS (289 checks).

### Z6 result — final run and independent verification

The blocker was cleared by the operator freeing space on `E:` and defragmenting it: a 2 GB sequential write
passed again, a read probe of the previously failing chain delta succeeded, and the whole VM (with all ten
checkpoints intact) moved to `D:\01_System_Images\Virtual_Machines\` with
`Move-VMStorage -DestinationStoragePath` in 19.4 minutes. The guest was then cold-booted from the offline
checkpoint, so scenario 1 ran from a genuinely clean baseline and the guest's CD-ROM view was fresh.

- **Run v7: 8/8 success** in about 26 minutes with the `expected-watcher.sha256` stamp armed and evidence on
  the healthy disk: first-install 178.2 s, reinstall 191.2 s, upgrade 212.7 s, fault-registry-phase 193.6 s,
  fault-post-bookkeeping 235.0 s, locked-file 211.9 s, uninstall-preserve 200.0 s, explicit-cleanup 193.1 s.
- **Every scenario's `watcher.log`** shows `watcher script sha256=57d7ce68…` and `watcher build matches the
  declared stamp (57d7ce68…)`, so all eight ran the declared build with in-guest proof.
- **Consent is programmatic:** `uninstall-preserve` answered `button=7` with `User chose No.` 0.742 s after
  the prompt and preserved the fixture; `explicit-cleanup` answered `button=6` with `User chose Yes.`
  0.621 s after the prompt and removed it. No human touched either dialog.
- **Fault scenarios** show their markers and exceptions; `fault-registry-phase` exited 1 and the cycle still
  succeeded through the declared `expectFailure` path.
- **Independent verification** (`gentle-ai-verify`, read-only) returned `PASS_WITH_FINDINGS`: consent,
  build identity, fault handling, clean baseline, and per-cycle integrity are clean; the B1 dynamic
  attribution (C5) and the run log's missing self-identity (C10) are the two declared findings, the latter
  mitigated for forward-looking runs by an orchestrator identity header plus a post-run `run-custody.json`
  annotation in the v7 run root (the original v7 extracted log retains its historical identity limitation;
  the post-hoc annotation is not part of the extracted evidence). The ledger section "S11B-3 lifecycle re-run" carries the full record. C5 was subsequently **PASS with caveats**
  (2026-09-24) by the `silent-uninstall-with-state-root` dynamic proof (evidence and caveats in [the C5 evidence report](../../docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md)); the original v7 `PASS_WITH_FINDINGS` verdict is unchanged.

## Risks

- The watcher holds a resident PowerShell process inside the guest. It is a declared fixture, must be
  named in the evidence documentation, and must not be mistaken for product residue.
- Posting `WM_COMMAND` to a dialog is a real answer, but it is programmatic: the correctness of each
  scenario now depends on the consented answer being declared correctly in the manifest.
- If the operator's one login happens before the watcher is started, the checkpoint would capture a
  guest without it; the setup step must verify the watcher process is alive before freezing.