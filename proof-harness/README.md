# Versioned reusable VM proof harness source

This subtree is the minimal authored source baseline for the reusable VM proof harness. It is a custody-preserving migration from ignored build inputs; it is not VM evidence and does not contain a setup executable, ISO, VHDX, checkpoint, guest state, or runtime log.

## T3 universal guest bootstrap contract

`guest/bootstrap-watch.ps1` is a new scenario-independent watcher installed on the guest OS disk exactly once before checkpoint freeze. It does not replace or invoke the historical `guest/watch-scenarios.ps1`, and no runner, scenario, setup executable, ISO, or media is captured in checkpoint RAM. After restore, the host attaches two fresh, distinct fixed volumes and the watcher resolves them by exact labels only:

- `S11BINPUTS`: read-only-by-policy input volume containing exactly the per-run `runner.ps1`, `scenario.json`, `expected-runner.sha256`, and `expected-artifacts.json` contract files. The watcher never writes to this volume, passes the runner only `-EvidenceRoot` and `-ScenarioPath`, and verifies a complete input-tree digest before and after execution. T4 should attach this VHDX read-only where Hyper-V permits it.
- `S11BEVIDENCE`: fresh writable evidence volume. The runner writes artifacts below this root; the watcher writes bounded `bootstrap.log`, explicit `done.json`, `exit.json`, and runner stdout/stderr evidence. Before runner execution, it hashes its own `$PSCommandPath` on the guest OS disk and records `bootstrap watcher sha256=<digest>` in `bootstrap.log`; successful `done.json` also carries `bootstrapSha256`. Stdout and stderr are drained concurrently into capped files, and the runner is killed after the bounded guest timeout (reported as exit code `124`).

`scenario.json` uses schema `gentle-ai.yasb-limitora.reusable-vm-run/v1` and contains a safe `scenario` identifier. `expected-runner.sha256` is one 64-character SHA-256 digest. `expected-artifacts.json` uses schema `gentle-ai.yasb-limitora.reusable-artifact-manifest/v1` and contains relative, unique artifact paths with expected size and SHA-256. The watcher records `runnerExitCode` in both `done.json` and `exit.json`; nested artifact records use guest Windows separators and the host verifier normalizes them before comparison. The watcher rejects missing or ambiguous labels, shared volumes, reparse points, path escapes, malformed or mismatched hashes, input mutation, artifact mismatches, and non-zero runner exits. Volume discovery normalizes PowerShell's scalar, empty, and nested-array output before applying strict ordinal label matching, so zero, one, and multiple candidates fail or resolve deterministically. The two resolved roots are checked explicitly and must be distinct. Only a fully verified controlled success writes `result: success` and requests clean guest shutdown; failures write `result: failed`/`success: false` evidence and leave the guest running.

Tree identity is rooted at the volume contents, not NTFS root metadata. Only root-level entries named `System Volume Information` or `$RECYCLE.BIN` (case-insensitive) are excluded before descent; the same names in nested directories remain authored input and are hashed/copied. Every other unreadable or unsupported entry fails closed. Optional authored input whose root name collides with either reserved name is rejected before staging. The digest canonicalization remains the sorted `relative-path|size|sha256` record stream terminated by a newline.

### Host API boundary for T4

The host owns checkpoint restore, creation/formatting, exact volume labels, fresh-disk identity, input population, explicit writable integrity-only input attachment, evidence hot-attach/hot-remove, bounded watchdog, extraction, and independent host-side hash verification. The observed Windows PowerShell 5.1 host does not provide a trustworthy guest read-only VHDX attachment contract, so execution is refused unless the operator explicitly opts into the fallback. It must attach exactly one `S11BINPUTS` and one distinct `S11BEVIDENCE` volume, never use drive letters as the guest contract, wait only for the explicit evidence records and guest-off state, and treat missing/failed/nonzero evidence as failure. The host must not run setup or uninstall on the host and must not overwrite historical proof or the original watcher. Host tree walks apply the same root-only reserved-name boundary and fail closed on every other unreadable entry; extraction does not skip nested reserved names.

## Source custody

`source-manifest.json` records the original origin, current byte size, and current SHA-256 digest for every versioned harness script. The migrated entries preserve provenance from the two explicitly authorized ignored sibling trees; T2 corrections are recorded by updating the current-byte hash, and T4 authored entries are byte-bound in this manifest:

| Versioned path | Source role | Origin |
| --- | --- | --- |
| `guest/watch-scenarios.ps1` | resident guest scenario watcher | `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/guest/watch-scenarios.ps1` |
| `guest/capture-state.ps1` | guest state and tree capture | `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/guest/capture-state.ps1` |
| `guest/hold-locked-file.ps1` | explicit guest file-lock fixture | `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/guest/hold-locked-file.ps1` |
| `guest/run-setup-uninstall.ps1` | bounded setup/uninstaller runner | `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/guest/run-setup-uninstall.ps1` |
| `guest/bootstrap-watch.ps1` | security-critical generic reusable bootstrap watcher | authored in `proof-harness/guest/` |
| `host/orchestrate-lifecycle.ps1` | host checkpoint, attach, wait, extraction loop | `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/orchestrate-lifecycle.ps1` |
| `host/verify-evidence.py` | fail-closed offline evidence and identity gate | `yasb-limitora-s11a-setup-assist/build/s11a-lifecycle/verify-evidence.py` |
| `host/roundtrip-verify.ps1` | read-only ISO member and dismount verifier | `yasb-limitora-s11a-setup-assist/build/s11a-lifecycle/roundtrip-verify.ps1` |
| `host/run-reusable-vm.ps1` | T4 reusable checkpoint/run orchestrator | authored in `proof-harness/host/` |
| `host/new-run-volumes.ps1` | T4 input/evidence VHDX staging helper | authored in `proof-harness/host/` |
| `host/verify-reusable-evidence.py` | T4 offline reusable evidence verifier | authored in `proof-harness/host/` |

The manifest keeps the ignored origin for migrated custody while the versioned file hash records current bytes. T3's `bootstrap-watch.ps1` is explicitly byte-bound as `kind: authored` and `securityCritical: true`; T4's three host files are also explicitly authored. Original T1 migrated entries retain their sibling/build provenance semantics. Any later edit to a manifest-listed file must update its byte size and hash deliberately.

## Explicit migration boundary

The migration intentionally excludes the ISO builder, scenario corpus, installer and uninstaller binaries, ISO staging trees, XML answer media, custody records for old runs, extracted evidence, VHDX files, and logs. Those are generated or historical inputs, not reusable authored source. The versioned roundtrip verifier is a minimal source-only check and does not include any ISO or staging payload. Future T3-T4 work must build on this versioned baseline; no runtime path may read a sibling worktree. The v3 bootstrap watcher remains byte-frozen; host provenance supplements guest attestation and does not alter the guest script or retroactively repair prior run archives.

The three files under `fixtures/` are deterministic authored test inputs. `scenario.json` binds the declared volume labels, runner bytes, and expected artifact bytes. `runner.ps1` is a no-product fixture that writes the fixed artifact only; it is not executed by T1.

## T4 reusable host API

`host/new-run-volumes.ps1` is the staging helper. It validates a run contract, creates two fresh NTFS VHDX files, labels them exactly `S11BINPUTS` and `S11BEVIDENCE`, and writes `runner.ps1`, `scenario.json`, `expected-runner.sha256`, and `expected-artifacts.json` to the input volume. `-AdditionalInputPath` may name explicitly declared setup or fixture files/directories; nothing else is copied. `-DryRun` validates and emits a plan without calling Hyper-V or storage cmdlets.

`host/run-reusable-vm.ps1` is the versioned orchestrator API:

```text
- VmName, CheckpointName
- RunnerPath, ScenarioPath, ExpectedArtifactsPath
- VhdxDirectory, EvidenceDirectory
- AdditionalInputPath (optional)
- WatchdogTimeoutSeconds (bounded)
- DryRun (safe plan-only mode)
- AllowWritableInputIntegrityFallback (explicit, fail-closed fallback)
```

It restores the same named generic checkpoint, starts it if restore leaves it Off/Saved, hot-attaches one writable input disk and one evidence disk on SCSI, waits for guest completion and VM Off, detaches both disks in `finally` on success or failure, mounts both only after detach, extracts evidence into a unique archive, and invokes `host/verify-reusable-evidence.py` offline. Failed cycles retain a unique archive and host failure record; evidence extraction is attempted before final cleanup whenever the evidence disk can be detached. Cleanup failures are recorded explicitly and never reported as silent success. No DVD, ISO, cache, setup, uninstaller, PowerShell Direct, Enhanced Session, KVP, clipboard, or writable share is used.

Each non-dry run also writes `host-provenance.json` in its unique archive. This host-owned record binds the requested checkpoint's native Name, Id, VM Id, and creation time to the identities observed immediately before and after `Restore-VMCheckpoint`, records the observed restore timestamp, generic bootstrap hash, runner hash, input VHDX hash, run ID, and explicit restore/guest/extraction/verification outcomes. Any native identity drift or provenance write failure fails closed. The offline verifier checks the record when passed `--host-provenance`; it does not synthesize provenance for historical archives.

### Input immutability choice and threat model

The observed Windows PowerShell 5.1 Hyper-V host does not expose a trustworthy guest read-only VHDX attachment contract. T4 therefore makes no true read-only claim: the default refuses to run, and `-AllowWritableInputIntegrityFallback` is the only execution opt-in. That mode attaches writable input and compares complete pre/post input-tree SHA-256 values, failing closed on persistent mutation. Its transient-tamper threat is explicit: a guest can change bytes and restore the original contents before the post-hash, so this protects against accidental or cooperative mutation but not a hostile guest, compromised host/storage stack, or Hyper-V exploit. The verifier also requires `bootstrap.log` to carry the expected generic `bootstrap-watch.ps1` SHA-256 marker and independently recomputes runner, full input-tree, declared artifact, and exit-record hashes after offline extraction.

### One-time operator prerequisite for T5

The universal bootstrap source changed in this update. Any previously saved checkpoint containing the earlier watcher is stale; do not use it as live proof or freeze state from it. The parent must reinstall this source and safely recheckpoint before T5. This source-only change has not performed live VM/storage proof.

1. Prepare a dedicated generic Windows guest OS disk at the operator-selected bootstrap location. Log in once, install only the universal `guest/bootstrap-watch.ps1` watcher and its scheduled/resident startup mechanism, confirm it can resolve exact labels, then freeze the checkpoint named by `-CheckpointName` while the watcher and OS are in the intended reusable state.
2. The checkpoint must contain no runner, scenario, setup executable, fixture payload, ISO/DVD, or scenario-specific material in RAM or on the frozen OS disk. The bootstrap watcher is the only scenario-independent guest harness state; all per-run material arrives through fresh VHDX volumes.
3. The operator must provide a Hyper-V host with the VM, generic checkpoint, SCSI attachment points, enough VHDX storage, and permission to use `New-VHD`, disk initialization/formatting, checkpoint restore, hot attach/remove, and read-only post-run disk-image mounting. The bootstrap watcher must emit `bootstrap watcher sha256=<digest>` in `bootstrap.log` for the verifier's generic watcher identity gate. No login, network, integration service, or guest channel is required after freeze.
4. T5 must run the harmless fixture twice from the same checkpoint and record the checkpoint identity plus input/evidence VHDX hashes. This T4 implementation has not performed live VM, checkpoint, or disk mutation and does not constitute live proof.

## C5 silent-uninstall contract

The versioned C5 runner is `guest/run-c5-silent-uninstall.ps1`. It accepts only `-EvidenceRoot` and `-ScenarioPath`; the input root is derived from the scenario path. Stage the generic `fixtures/c5/scenario.json` as `scenario.json`, `fixtures/c5/c5-steps.json` as `c5-steps.json`, `fixtures/c5/expected-artifacts.json` as `expected-artifacts.json`, the rebuilt setup executable as `yasb-limitora-0.2.0-setup.exe`, `guest/capture-state.ps1` as `capture-state.ps1`, and `fixtures/c5/state-root/` as `state-root/`. The root scenario must retain the reusable-vm-run schema; C5-specific schema and steps live in `c5-steps.json`. The runner verifies the setup name, 11,054,574-byte size, SHA-256 `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394`, and the two 32-byte fixture files before executing the install, fixture staging, before capture, uninstall, and after capture steps. It records only `dialogAnswerAttempted`; absence of dialog answers is not a claim that no dialog was displayed. It never claims state-root deletion.

Use the following commands from the repository root. The dry run validates the reusable host plan without touching Hyper-V or storage:

```powershell
pwsh -NoProfile -Command "& 'proof-harness/host/run-reusable-vm.ps1' -VmName '<vm-name>' -CheckpointName 'clean-windows-universal-bootstrap-v3' -RunnerPath 'proof-harness/guest/run-c5-silent-uninstall.ps1' -ScenarioPath 'proof-harness/fixtures/c5/scenario.json' -ExpectedArtifactsPath 'proof-harness/fixtures/c5/expected-artifacts.json' -VhdxDirectory '<vhdx-directory>' -EvidenceDirectory '<evidence-directory>' -AdditionalInputPath @('build/c5-rebuild/yasb-limitora-0.2.0-setup.exe','proof-harness/guest/capture-state.ps1','proof-harness/fixtures/c5/c5-steps.json','proof-harness/fixtures/c5/state-root') -DryRun"
```

A real disposable-VM run uses the same command without `-DryRun` and with the explicit fallback switch because the current host cannot provide a trustworthy read-only VHDX attachment:

```powershell
pwsh -NoProfile -Command "& 'proof-harness/host/run-reusable-vm.ps1' -VmName '<vm-name>' -CheckpointName 'clean-windows-universal-bootstrap-v3' -RunnerPath 'proof-harness/guest/run-c5-silent-uninstall.ps1' -ScenarioPath 'proof-harness/fixtures/c5/scenario.json' -ExpectedArtifactsPath 'proof-harness/fixtures/c5/expected-artifacts.json' -VhdxDirectory '<vhdx-directory>' -EvidenceDirectory '<evidence-directory>' -AdditionalInputPath @('build/c5-rebuild/yasb-limitora-0.2.0-setup.exe','proof-harness/guest/capture-state.ps1','proof-harness/fixtures/c5/c5-steps.json','proof-harness/fixtures/c5/state-root') -AllowWritableInputIntegrityFallback"
```

The fallback is integrity-only: it hashes the complete input tree before and after the guest run and detects persistent mutation, but cannot detect a guest that changes bytes and restores them before the post-hash. Never run setup or the uninstaller on the host. `run-reusable-vm.ps1` continues to invoke the generic reusable-evidence verifier for the archive. After that host-level verification, run the dedicated C5 verifier against the complete archive; it loads `archive/input/scenario.json`, `archive/input/c5-steps.json`, and evidence below `archive/evidence/`:

### MAX_PATH recovery note

The current-tree attempt5 host extraction initially failed because a nested target path reached 275 characters, exceeding Windows MAX_PATH. Recovery used a read-only mount followed by a short-path copy; 14/14 evidence-file and 9/9 input byte comparisons then passed, and both offline verifiers passed. The host provenance record remains `overall=failed` for the original extraction failure; this is preserved provenance, not rewritten as a clean orchestration result. The writable-input fallback still cannot detect transient tamper restored before the post-hash. The command strings above are test-pinned and intentionally unchanged.

```powershell
python proof-harness/host/verify-c5-silent-uninstall.py `
  '<EvidenceRoot>\runs\run-<id>'
```

The C5 verifier fails closed on malformed or boolean exit codes, missing generic records, missing captures, changed fixture bytes, an application or uninstall key that remains, unexpected dialog-answer claims, or any setup identity mismatch. These commands are documentation only; this source change does not perform VM, storage, setup, or uninstaller execution.
