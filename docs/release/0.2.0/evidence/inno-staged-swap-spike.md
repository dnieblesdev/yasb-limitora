# G1 — Inno staged-swap/bookkeeping feasibility spike (design.md §3.3, §10.2)

**Final G1 verdict: `pass` for the selected pre-install evacuation fallback.** The historical post-install rename attempt remains a rejected `fail`; the separate fallback run below proves native canonical bookkeeping, success-uninstall cleanup, induced post-bookkeeping failure cleanup, prior registry restoration, prior-uninstall cleanup, non-elevation, and exact disposable cleanup.

**Historical post-install rename verdict: `fail`.** The exact new `UninstallString` exited `0` but left the canonical disposable program root behind. This disproves the post-install rename-swap mechanism for the tested Inno bookkeeping path. That attempt stopped before its failure phase and does not claim a Phase B result.

This is the corrected evidence handoff for run `1e19e1aabfbfdfca28f8e2c82db1f98c`. No installer was rerun for this correction.

## 1. Scope and run binding

The authorized spike was intended to prove, under `PrivilegesRequired=lowest`, both:

1. a successful staged `.new` → canonical install followed by a working exact new uninstaller; and
2. an induced step-6 failure with `.failed` quarantine, reverse swap, verbatim HKCU restoration, and a working prior uninstaller.

| Item | Value |
| --- | --- |
| Run ID | `1e19e1aabfbfdfca28f8e2c82db1f98c` |
| Disposable AppId | `{DDD7E71F-7825-41CF-B49A-29DB3F084286}` |
| Canonical root | `%LOCALAPPDATA%\Programs\yasb-limitora-g1-spike-<run-id>` |
| HKCU key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{DDD7E71F-7825-41CF-B49A-29DB3F084286}_is1` |
| Candidate | S02 frozen onedir candidate, version `0.2.0` |
| Launch shell | git-bash, non-elevated launch context recorded in the run materials |

The disposable setup sources use the exact run ID and AppId. Both `[Setup]` sections specify `PrivilegesRequired=lowest` and no privilege override. The run-specific setup and candidate hashes are retained under `build/g1/<run-id>/evidence/`.

## 2. Historical supported evidence

The following evidence is present and supports the failure conclusion without relying on Inno `/LOG` captures:

- `logs/spike-new-1e19e1aabfbfdfca28f8e2c82db1f98c.selflog.txt` — flushed ordered self-log for capture, native stage, verification, rename-swap, registry path rewrite, and commit.
- `evidence/a2-exit.txt` — new staged installer exit `0`.
- `evidence/a3-new-uninstall.txt` — exact captured new `UninstallString`, exit `0`, canonical root still present, siblings absent, and uninstall key absent.
- `evidence/final-guarded-residuals.txt` — final guarded canonical/sibling/key state before remediation.
- `evidence/key-a1-baseline.txt`, `evidence/key-a2-new.txt`, `evidence/a1-prior-uninstall-string.txt`, and `evidence/a2-new-uninstall-string.txt` — exact baseline/new key values and uninstaller strings.
- `evidence/preflight-and-binding.txt` — run binding, candidate preflight state, and recorded `token-is-admin=False` observation.
- `evidence/current-sha256.txt`, `evidence/setup-hashes.txt`, `evidence/script-hashes.txt`, and `evidence/candidate-build-info.json` — candidate, setup, script, and build identity/hash records.

The self-log shows the tested path reached commit and rewrote the new key's path-bearing values to the canonical path. The exact new uninstaller then returned `0`, removed the uninstall key, but did not remove the renamed canonical program directory. That is the evidence-backed mechanism failure.

## 3. Historical unavailable or non-claimable captures

- The A1/A2/A3 Inno `/LOG` captures are not treated as available or authoritative captures for this handoff. No conclusion above is attributed to them. The three corresponding paths may remain in the preserved raw run directory, but their contents are not used as support here.
- No before/after PATH capture was part of this G1 run. PATH behavior is unavailable and is not a passed result.
- `evidence/state-root-before.txt` is only a pre-attempt snapshot. No after snapshot was produced, so state-root preservation is not claimed as passed.
- Phase B was **not run**. There is no Phase B installer, self-log, key restoration, prior-uninstaller, or after-state result. The forced-failure requirement remains unproven.
- The recorded non-elevation observations are partial run evidence only; this handoff does not claim an independent non-elevation gate pass.

## 4. Historical Phase A evidence summary

### A1 — baseline prior install

The baseline key snapshot and prior `UninstallString` capture establish the disposable prior installation and its exact identity. The candidate/build and setup hash records bind the run inputs. No A1 `/LOG` claim is made.

### A2 — staged new upgrade

The authoritative self-log records, in order: prior-key capture, native copy to `.new`, candidate verification, canonical → `.old`, `.new` → canonical, canonical registry path rewrites, and commit. `evidence/a2-exit.txt` records exit `0`. `evidence/key-a2-new.txt` and `evidence/a2-new-uninstall-string.txt` show the new version's key and exact canonical `UninstallString`.

### A3 — exact new uninstaller health check

The exact captured string was:

```text
"C:\Users\dnieb\AppData\Local\Programs\yasb-limitora-g1-spike-1e19e1aabfbfdfca28f8e2c82db1f98c\unins000.exe"
```

It exited `0`. The guarded result recorded in `evidence/a3-new-uninstall.txt` and `evidence/final-guarded-residuals.txt` was:

| Guard | Result |
| --- | --- |
| canonical disposable root | **present residual** (`yasb-limitora.exe`, `_internal`) |
| `.new`, `.old`, `.failed` | absent |
| exact unique uninstall key | absent |

The uninstaller bookkeeping did not follow the renamed canonical payload. Therefore post-install rename is rejected/disproven for this mechanism.

## 5. Historical Phase B stop

The historical Phase B was intentionally stopped after A3 failed. Its forced-failure variant was not executed and the G1 task was left open at that time. The selected fallback is independently tested below; no historical result is retroactively inferred.

## 6. Follow-on design handoff

The separate fallback proof below closes the G1 feasibility gate for the selected mechanism. S10/S11 may implement the same pre-install evacuation lifecycle; this evidence does not authorize product-source changes.

Contract-level follow-up (fix `R3-incomplete-registry-rollback`; no new native run is claimed): the S10 static script now snapshots the complete prior HKCU uninstall registration with original value types via a bounded, exit-checked `reg.exe export` before evacuation, and re-advertises it verbatim via `reg.exe import` only after the prior payload restoration succeeds; snapshot or import failure is fail-closed and retains the recovery bytes.

## 7. Raw-artifact index (files actually present)

The preserved run directory contains the following indexed raw artifacts; no absent Phase B files are listed:

```text
evidence/a1-prior-uninstall-string.txt
evidence/a2-exit.txt
evidence/a2-new-uninstall-string.txt
evidence/a3-new-uninstall.txt
evidence/candidate-build-info.json
evidence/current-sha256.txt
evidence/final-guarded-residuals.txt
evidence/key-a1-baseline.txt
evidence/key-a2-new.txt
evidence/preflight-and-binding.txt
evidence/script-hashes.txt
evidence/setup-hashes.txt
evidence/state-root-before.txt
logs/phase-a1-baseline-install.log
logs/phase-a2-new-install.log
logs/phase-a3-new-uninstall.log
logs/spike-new-1e19e1aabfbfdfca28f8e2c82db1f98c.selflog.txt
setup/g1-spike-baseline-1e19e1aabfbfdfca28f8e2c82db1f98c.exe
setup/g1-spike-new-1e19e1aabfbfdfca28f8e2c82db1f98c.exe
setup/g1-spike-newfail-1e19e1aabfbfdfca28f8e2c82db1f98c.exe
spike-baseline.iss
spike-new.iss
```

Raw historical artifacts are preserved under `build/g1/1e19e1aabfbfdfca28f8e2c82db1f98c/`. The exact historical disposable residual was cleaned separately; raw evidence is not deleted.

## 8. Selected fallback proof — native run

### 8.1 Binding and scope

| Item | Value |
| --- | --- |
| Run ID | `181cab27ecf2fb30dc7b16bbef42801d` |
| Disposable AppId | `{55D372A6-1DA5-41BE-B7AB-65CAB362E620}` |
| Canonical root | `%LOCALAPPDATA%\Programs\yasb-limitora-g1-fallback-<run-id>` |
| HKCU key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppId}_is1` |
| Candidate | actual S02 onedir, `0.2.0`, PyInstaller `6.22.2`, Python `3.13.5` |
| Installer | Inno Setup `6.7.3`, `PrivilegesRequired=lowest` |
| Token | `token_is_admin=false`; Inno logs also record `IsAdminLoggedOn=False` and `IsAdminInstallMode=False` |

All four exact disposable roots/key were preflight-absent. The run generated fresh lowercase-hex identity, compiled three fresh installers, used only `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=...`, and never elevated.

### 8.2 Native lifecycle result

| Checkpoint | Result |
| --- | --- |
| Baseline A1 | Native S02 payload installed at canonical; prior DisplayVersion, UninstallString, InstallLocation and registry types captured. |
| Success A2 | Prior canonical evacuated to `.old` before native copy/registration; canonical payload and build-info `0.2.0` verified; native DisplayVersion `0.2.0`; `.old` removed only after success. |
| Success A3 | Exact new `UninstallString` ran silently and returned `0`; canonical, siblings, and exact HKCU key became absent after bounded second-phase wait. |
| Failure B2 | Baseline recreated byte-for-byte at the registry-value/type level; prior values captured again; canonical evacuated before native new copy/registration. A deterministic post-bookkeeping `cmd /c exit 121` was logged. |
| Native rollback correction | Inno 6.7.3 logs show `Installation process succeeded` before `ssPostInstall`, so Pascal cannot roll back from that late event. The smallest disposable harness correction invoked the exact newly registered native `UninstallString`; it removed the new canonical/key while retaining `.old`. No custom new-tree deletion was used. |
| Restore B3/B4 | Captured prior HKCU values and original types restored; `.old` renamed to canonical; exact restored prior `UninstallString` ran silently and returned `0`; canonical, `.new`, `.old`, `.failed`, and key absent. |
| Unrelated boundary | Before/after observable state-root child count, HKCU User PATH type/length/hash, and `YASB_CONFIG_HOME` presence/hash were equal. |

The native-uninstaller action is explicitly retained as a harness correction, not conflated with the rejected post-install rename or presented as Inno transaction rollback. The durable narrative is: Inno completed bookkeeping; the induced `[Run] cmd /c exit 121` was observed; then the harness deliberately ran the exact new native uninstaller as the late-failure rollback correction before restoring `.old` plus the captured HKCU values and types. The raw `failure-self.log` and `b2-failure.log` retain their original wording and were not edited. Raw sanitized evidence is under `build/g1-fallback/181cab27ecf2fb30dc7b16bbef42801d/**`, including setup/script hashes, process exit records, native `/LOG` files, self-logs, registry snapshots with type IDs, checkpoint directories, boundary equality, and final `VERDICT.txt`.

### 8.3 Evidence-integrity remediation

This correction changed evidence records only; no installer or compiler was rerun and no raw `.log` or EXE was mutated.

- `evidence/script-hashes.txt` now labels the hashes of the actual root compile inputs (`build/g1-fallback/baseline.iss` and `fallback.iss`) separately from the newline-normalized retained copies under `build/g1-fallback/<run-id>/scripts/`.
- `evidence/integrity.json` is the bounded derived integrity record. Its 26 entries cover both compile-input identities, both retained copies, all three setup EXEs, and every retained compiler/native/self/process log. Its post-run SHA-256 self-verification is `pass`; the record excludes itself to avoid a circular digest.
- `evidence/execution-binding.json` is explicitly `post-run-derived`, not contemporaneous telemetry. It binds the ordered three compile actions and seven setup/uninstaller actions to redacted logical argv, retained native and process logs, exit codes, exact captured `UninstallString` references, and recomputed log hashes. Its compiler entries truthfully mark a separate process log as not retained; the three empty harness process logs are hashed and included for the lifecycle entries.
- The read-only post-run confirmation found the exact run root and `.new`/`.old`/`.failed` siblings absent, the exact HKCU uninstall key absent, and zero attributable processes. G1 remains checked only because both derived records self-verify.

**Fallback G1 verdict: `pass`.** This is the single final verdict for G1; the historical post-install experiment remains `fail` and rejected.
