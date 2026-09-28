# Issue #304 — fail-closed and reusable VM proof harness

## Objective and authorization

User authorized both the existing #304 fail-closed verification defects and a reusable, scenario-independent logged-in guest checkpoint with hot-attached input/evidence VHDX. Work exclusively in `yasb-limitora-304`; preserve #299 and historical ignored evidence. Baseline `d5a0506`.

## Problem and scope

Current lifecycle proof lives in ignored `build/` and couples checkpoint RAM to variable ISO media. Three gates can misleadingly pass: ISO dismount, ordered-dictionary step exit, and narrow host evidence verification. Version a minimal, reviewable harness source subtree rather than silently force-adding historical generated inputs/artifacts. No product installer change; no setup/uninstaller execution on host.

## Constraints

One-time login to freeze a universal bootstrap watcher on the guest OS disk; thereafter restore the same checkpoint and hot-attach distinct input and evidence VHDX volumes. Discover by exact volume labels, not letters. Input contains `runner.ps1`, `scenario.json`, setup/fixtures, expected runner and artifact hashes. Verify in guest before execution and on host after extraction. Evidence carries explicit exit state and log; guest clean shutdown only on successful controlled completion. Input read-only in guest if practical, otherwise fail-closed pre/post integrity checks and explicitly document threat model. No network, PowerShell Direct, Enhanced Session, KVP, clipboard, or writable shares. Bounded host waits/watchdog and failed-cycle disk removal. Never overwrite historical proof.

## Tasks (stable IDs)

- [x] T1. Established separately versioned minimal source and deterministic test fixtures without generated evidence. Delegated writer; source migration did not offer meaningful RED. Custody tests 4 passed, six PS AST parses passed.
- [x] T2. Corrected ISO dismount, ordered-dictionary step failure, and host evidence gate. Delegated writer; observed RED (5 failures) then GREEN (13 focused tests), PS AST parse; mocked disk query errors/missing results/attached state fail closed. Live ISO/VM not yet exercised.
- [x] T3. Implemented universal guest bootstrap with runner/input hash, labels, path guards, bounded output/timeout, explicit exit/evidence and clean-shutdown-on-success contract. Delegated writer; source-absent RED, 13 scoped tests GREEN including concurrent-output and timeout child; AST parse passed. No live VM proof.
- [x] T4. Implemented host input/evidence VHDX staging, checkpoint restore/hot-attach, bounded watchdog/extraction/cross-check and cleanup. Independent offline verification: 35 harness tests passed, all nine PS AST parses passed, safe dry-run planned two labels without VHDX, guest-produced nested-artifact evidence passed verifier; no live VM execution. Writable input is explicit opt-in integrity-only fallback; not guest read-only.
- [x] T5. Ran two harmless runners with distinct hashes from the same generic Standard checkpoint v3 (ID `3842be2c-a8a3-4cdb-98e2-0905179b999a`) without another login. Bound host provenance in each archive records identical before/after checkpoint identity; independent verifier PASS twice, guest clean shutdown, VM Off and only OS disk retained. Writable input fallback remains integrity-only, not guest read-only.
- [ ] T6. Complete focused/full checks and documentation, update #304 scope when remote mutation separately authorized, then prepare reviewable delivery units. Route: parent coordination plus delegated verification.

## Acceptance

A changed runner/artifact executes via freshly attached input after repeated restore of one generic checkpoint; mismatched hashes and nonzero undeclared exits fail closed; input cannot be silently changed by guest; evidence is independently cross-checked; historical #299 and old proofs remain untouched. No new manual login after initial checkpoint freeze. Report any unavailable VM proof honestly.

## Forecast and strategy

Likely >400 authored changed lines across several work units. Delivery strategy `ask-on-risk`; user selected `stacked-to-main` PR slices before next commit. No PR has been created. No commits/push/PR without ordinary authorization. Native candidate assessment at work-unit boundaries if applicable.

## Progress and verification

- 2026-09-22: User clarified both scopes belong to #304. Independent issue read: issue open, only `bug` label, existing body covers three gates and asks whether to version harness. Fresh worktree `feat/issue-304-reusable-vm-harness` at `d5a0506`; #299 worktree not touched.
- Read-only mapping located ignored source in `yasb-limitora-s11b-reconciled/build/s11b-lifecycle/` and legacy verifier in `yasb-limitora-s11a-setup-assist/build/s11a-lifecycle/`.
- T1: migrated six authored scripts byte-identically into `proof-harness/` with custody manifest, README and deterministic smoke fixtures; structural pytest 4 passed, six PowerShell AST parses passed. No VM writes. Source-manifest hashes must be updated alongside future source edits.
- T2: repaired guest dictionary lookup and host evidence verifier, added versioned roundtrip dismount verifier and negative tests; initial 5 failed before fixes, then 13 scoped tests passed after query-error followup. PowerShell AST passed; no live ISO/VM test.
- T3: universal OS-disk bootstrap added. Runner receives evidence root and scenario path from labeled volumes; validates runner/artifact hashes and complete input digest; simultaneous bounded output capture and 2-second timeout regression against a harmless child passed (13 scoped tests). Accidental empty `nul` created during delegated validation was removed after confirming zero bytes; #299 tree status unchanged.
- T4: host implementation initially partial: off-surface whitespace drift of `verify-evidence.py` restored byte-identically to T2 custody hash; independent audit exposed double staging, unsupported Hyper-V `-ReadOnly`, misleading tests, missing bootstrap identity, producer/consumer mismatch and path normalization, now corrected. Final independent offline verification 35 tests passed, nine AST parses, valid dry-run, guest-shaped nested artifact verifier PASS, tree unchanged. A verifier-created zero-byte file named `'` was removed after `stat`.
- Work-unit commits: `65f854a8c718771b25f4533648db653047e67f99` (`fix(proof): version fail-closed legacy VM gates`, 2810 authored lines; native review `review-fe7b4f85ebc69d25` approved and acknowledged, advisory warnings only); `b48cdde9b02c46b624c5cc9138693e84ff909eb5` (`feat(proof): add reusable guest bootstrap contract`, 868 lines; scoped tests 12 passed; native review of this *individual* commit was not available because inspect offered accumulated branchpoint and START with previous commit base returned `native-start-retained-selection-candidate-mismatch`, no lineage created). Third host/proof commit pending. Each coherent unit exceeds ~400 changed lines; stacked-to-main selected but no PR/size exception authorized.
- T5: One login, generic v3 checkpoint `3842be2c-a8a3-4cdb-98e2-0905179b999a` (Standard, VM `703b3c71-87b0-4acf-9d7c-a57aa4b516ea`) frozen with only OS disk and two empty DVD drives. Three earlier checkpoints/attempts and failing disks preserved: initial NTFS metadata digest ACL, label-discovery array nesting, fixture `ScenarioPath` mismatch; corrected by test-first fixes before bound proof. User explicitly accepted writable input integrity-only risk. Final bound runs `20260928T011253Z-c7bf1b92ab0f44c292dd4befa6a300ba` and `20260928T011539Z-9a4c35291b034d098744a03998d19aa2`: both host and independent offline verifier PASS; runner SHA-256 `1eb8c3075150dc78e7f5d6ec8342563aa66e38d1150d151adf107ff677161a2b` vs `6b2f6af046946d6df4da7a04d013016934b3c6053309dd005da8e23ebe710ac7`; same bootstrap hash `35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7`; VM Off, only OS disk. Host provenance binds same before/after checkpoint name/ID/VMID/creation to both archives. `inputVhdxSha256` is a pre-run container fingerprint and differs from post-run writable NTFS container hash; payload tree digests pass. No ISO/media attached; two empty DVD devices remain.

## Next step

T6: produce reviewable live evidence record, run applicable full/focused checks and prepare stacked-to-main work-unit slices without push/PR. Keep historical failed run disks and prior checkpoints as diagnostic evidence. Report pre-run VHDX container hash as pre-run only: writable NTFS changes container bytes while payload tree hashes stayed identical. CodeGraph cannot target sibling worktree; use explicit paths.
