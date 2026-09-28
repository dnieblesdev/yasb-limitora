# Issue #304 — reusable checkpoint smoke proof

**Result: PASS for the reusable bootstrap transport, not for installer behavior.** Two harmless runners with different source hashes executed after separate restores of one logged-in Standard checkpoint. Both emitted verified evidence and shut the guest down without another login. The input VHDX was writable under an explicitly accepted integrity-only fallback; this is not a hostile-guest isolation proof.

## Reproduce the evidence check

The versioned source is in `proof-harness/`. The run archives and the four **FINAL bound-pair VHDXs**—one input and one evidence VHDX for each final run—are local, git-ignored artifacts under `build/issue-304-evidence/runs/` and `build/issue-304-runs/`; they are **not** in this repository. Sixteen historical/diagnostic VHDX files from earlier attempts are also retained locally, but are not part of the final bound pair and are not counted as archive-bound evidence. From the #304 worktree, for each archive below:

```text
python proof-harness/host/verify-reusable-evidence.py <archive>/evidence \
  --input-root <archive>/input \
  --expected-bootstrap-sha256 35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7 \
  --host-provenance <archive>/host-provenance.json
```

Both independent invocations exited `0` with `VERDICT: PASS`. The guest `done.json` and `exit.json` each report runner exit `0`, success, and shutdown requested; the final VM state was `Off` with only its OS hard disk attached.

## Identity and observed sequence

| Item | Identity / result |
| --- | --- |
| VM | `s11b-69c7ff5-20260922-050224-606df2ed`; ID `703b3c71-87b0-4acf-9d7c-a57aa4b516ea` |
| Generic checkpoint | `clean-windows-universal-bootstrap-v3`; Standard; ID `3842be2c-a8a3-4cdb-98e2-0905179b999a`; created 2026-09-28 00:30:07 UTC |
| Checkpoint RAM / media | Logged-in session and running universal watcher; one OS hard disk, no variable input/evidence disk; two DVD devices with **empty media paths** |
| Watcher | `proof-harness/guest/bootstrap-watch.ps1`, SHA-256 `35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7` in host source, guest `bootstrap.log`, `done.json`, and both host checks |
| First bound run | `20260928T011253Z-c7bf1b92ab0f44c292dd4befa6a300ba`; archive `build/issue-304-evidence/runs/run-20260928T011253Z-c7bf1b92ab0f44c292dd4befa6a300ba-16473951a1c444acb8df0e1a93e9b436/` |
| Second bound run | `20260928T011539Z-9a4c35291b034d098744a03998d19aa2`; archive `build/issue-304-evidence/runs/run-20260928T011539Z-9a4c35291b034d098744a03998d19aa2-351cd67cae944ace90c3586ac0329960/` |

| Check | First run | Second run |
| --- | --- | --- |
| Runner SHA-256 | `1eb8c3075150dc78e7f5d6ec8342563aa66e38d1150d151adf107ff677161a2b` | `6b2f6af046946d6df4da7a04d013016934b3c6053309dd005da8e23ebe710ac7` |
| Input payload-tree SHA-256 | `86e24390fa54005ca1de24ddaf46b7e1199fa5584e8dcaa39b02446648bd4e44` | `788192b7f5d9c3379cf03c9ead410aef8f702a0630c6da06694db6758a8ff297` |
| Artifact | `artifact.txt`, 23 bytes, SHA-256 `a65c40af2ddb17e3e5c65e30eb5abe70e0a70e34c02d244cf3c1af3e0ccc9db8` | Same independently checked bytes |
| Guest exit / shutdown | `0` / requested; VM observed `Off` | `0` / requested; VM observed `Off` |
| Host provenance | Before/after checkpoint Name, ID, VM ID, creation time identical; restore observed 01:14:23 UTC | Same checkpoint identity; restore observed 01:17:06 UTC |
| Independent offline verdict | PASS, exit `0` | PASS, exit `0` |

The second runner differs only by a harmless trailing comment; the output fixture remains byte-identical. The host staged a fresh `S11BINPUTS` and `S11BEVIDENCE` pair after each restore and removed both before inspection. No DVD ISO, network, PowerShell Direct, Enhanced Session, KVP, clipboard, or writable share was used as an input/evidence transport. No setup or uninstaller ran on the host or in these smoke cycles.

## Evidence boundaries and failed attempts

The archive-bound evidence consists of each run's extracted guest records, staged input/evidence trees, and the verifier cross-checks. Host/VM observations—such as Hyper-V checkpoint identity, disk attachment, restore timing, and the final `Off` state—are distinct corroborating observations, not guest-produced evidence or cryptographic attestation.

- On this Hyper-V/Windows PowerShell 5.1 host, `Add-VMHardDiskDrive` exposes no trustworthy guest read-only option. The user explicitly accepted `-AllowWritableInputIntegrityFallback`. Pre/post **payload-tree** digests detect persistent input mutation, not a transient guest change that is reverted before hashing. `host-provenance.json.inputVhdxSha256` is a **pre-run container fingerprint**, not the post-run VHDX hash: NTFS writes can change the writable container while payload bytes remain identical.
- `host-provenance.json` records host-observed before/after checkpoint identity and restore time. It is not a cryptographic attestation by Hyper-V. The verifier binds it to each archived input/evidence tree, and a separate read-only Hyper-V inspection confirmed the same live checkpoint ID/VM ID. Previous smoke archives lacking this record are **not** counted as the final bound pair.
- Earlier failed attempts and disks were retained, not overwritten: initial `System Volume Information` access during host digest before VM restore; a PowerShell nested-array bug that hid present labels; and a fixture runner missing `-ScenarioPath`, whose guest `done.json` truthfully reported failure. Corrections were tested before the final pair. Old v1/v2 checkpoints remain as historical diagnostic states and must not be used for a new run.
- This proves the transport/bootstrap path and repeated restore only. Installer scenarios, failure-injection semantics, true guest read-only input, and a malicious-guest threat model remain outside this smoke proof. #299 stays paused in its separate worktree pending its own C5 execution and evidence.

## Review path

1. Start with `proof-harness/README.md` and `proof-harness/guest/bootstrap-watch.ps1` for the trust and execution boundary.
2. Read `proof-harness/host/new-run-volumes.ps1`, `run-reusable-vm.ps1`, and `verify-reusable-evidence.py` for distinct volumes, bounded cleanup, identity, and host cross-check.
3. Run `python -m pytest -q tests/test_proof_harness_*.py`; review the negative tests before accepting PASS claims. Check `proof-harness/source-manifest.json` for current byte custody.
