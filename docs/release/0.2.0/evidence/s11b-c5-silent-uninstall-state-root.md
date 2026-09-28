# C5 — Silent uninstall with a state-root fixture

| Field | Value |
| --- | --- |
| Change | `release-and-smoke-test-0-2-0` |
| Result | **PASS with caveats on the current tree**; attempt5 evidence recovered and independently verified |
| Date | 2026-09-28 (current-tree attempt5); historical old-branch record preserved below |
| TDD | Strict TDD enabled for the harness correction; documentation-only reporting has no code-test runner. |

> **Branch reconciliation note.** The earlier v7 record below was written against the old branch
> (`feat/s11b-transaction-closeout-reconciled`, head `84ddcb3`); its setup hash, checkpoint identity,
> watcher stamp, and harness hash remain historical and do not describe the current tree. Current-tree
> attempt5 evidence was recovered and verified from the disposable run archive. The host provenance
> record retains `overall=failed` because the first extraction path reached 275 characters and hit
> MAX_PATH; a read-only mount and short-path copy recovered the evidence for the independent checks.
> Historical identities, chronology, and caveats remain preserved below.

> This is the detailed, repository-local record of the C5 follow-up. It supplements—but does not replace or alter—the original v7 `PASS_WITH_FINDINGS` verdict. C7 is unchanged; C10 remains mitigated only for forward-looking runs, not resolved.

## 1. What was exercised

The isolated scenario used the B1-fixed production setup, then created two declared files at the state root:

- `config.json` — `{"fixture":"s11b-state-root/v1"}`
- `quota-v2-cache.json` — `{"fixture":"s11b-state-root/v1"}`

It captured the state before uninstall, invoked the installed uninstaller with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, and captured the state afterward. The scenario declared no dialog answers and requested VM shutdown on completion. The fixture content matched the declared fixture used by the existing uninstall-preservation scenario.

## 2. Harness correction and regression

A one-manifest run exposed PowerShell 5.1 pipeline unrolling: `Load-Scenarios` returned a scalar `OrderedDictionary` for one scenario, so indexing the expected array failed before the VM cycle began. Eight manifests retained an array.

The harness-only fix was to return the collection with unary-comma array preservation: `return ,$scenarios`. The actual helper passed direct RED/GREEN regression checks under Windows PowerShell 5.1.26100.9444: one manifest returned an `Object[]` of count 1; eight returned an `Object[]` of count 8. The actual scenario validator and structural assertions also passed. No product source was changed.

## 3. Current-tree attempt5 result

Attempt5 exercised the rebuilt current-tree setup in the disposable VM. The generic verifier printed
`VERDICT: PASS`, and the dedicated verifier printed
`C5 VERDICT: PASS scenario=silent-uninstall-with-state-root`. This is a current-tree C5 result only;
it is not a rerun of the full S11a/S11b lifecycle matrix.

| Current identity or result | Recorded value |
| --- | --- |
| Setup | `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394` (11,054,574 B) |
| Uninstaller | `02431245dfe2a60b55d16f6606929474ef5b8c432339afe73e9070862a390a8c` |
| Fixture files | both 32-byte files: `e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795` |
| Bootstrap | `35c216859790fb91ae310d39545e7499ceb8361f5624e5c72529fb400d8a80d7` |
| Checkpoint v3 | `3842be2c-a8a3-4cdb-98e2-0905179b999a` |
| VM | `s11b-69c7ff5-20260922-050224-606df2ed` |
| Runner | `386fd6c3cc859f54c02c6c7db67c27153dba2f91e71ae0416dff805c13d04bc2` |
| Input tree | `3b614966581e3d6f8f182ed122c58687dd69f00938a9cf98c8558b184475380b` |
| Evidence VHDX | `8cf289225044fd389ce61c8616557f01d67f107ca75ad0244273c09f06545207` before/after read-only mount |

Observed behavior was exact: install exit `0`; uninstall exit `0`; the application and uninstall key
were present before and absent after; both fixture files survived byte-identically; and
`dialogAnswerAttempted=false` was recorded. No `dialogObserved` claim is made. `done.json` reported
success, runner exit `0`, `inputUnchanged=true`, and `shutdownRequested=true`; the VM ended Off and
both run disks were detached.

Host recovery verified 14/14 evidence-file byte comparisons and 9/9 input byte comparisons after the
read-only mount and short-path copy. The host provenance's `overall=failed` is retained as provenance,
not rewritten: it records the MAX_PATH extraction failure (nested target length 275). The current PASS
comes from the recovered evidence and the generic and dedicated offline verifiers.

## 4. Historical old-branch run identity and result

| Identity or result | Recorded value |
| --- | --- |
| Scenario | `silent-uninstall-with-state-root` |
| VM checkpoint | `clean-windows-running-watcher-v7-69c7ff5` (old branch; not valid on this branch) |
| Scenario manifest SHA-256 | `8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93` |
| Watcher build/stamp SHA-256 | `57d7ce68ece311e8c58b1c1d29c8899535182cb628c5e98b9737961ae018a95c` |
| Production setup SHA-256 | `7ff33e5dc847e05b02f1d3789200c5c0c435af37b729247c0b9380a42eea8f35` (historical old-branch identity; current-tree setup is recorded above as `1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394`) |
| Harness SHA-256 | `6dd4e0788bec5b04b36da4af5d12e0d12e3460f6162efa21a4e085d52219ed64` |
| Scenarios | 1 declared; 1 successful |
| Total run duration | 208.1 seconds |
| Uninstall step duration | 7.419 seconds |
| Scenario steps | All five returned exit code 0 |
| Guest shutdown | Completed after 109 seconds |

Before/after comparison showed both declared state files remained byte-identical: 32 bytes each, SHA-256 `e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795`. The application root and uninstall registration were removed. The watcher identity matched the required build stamp.

> **Correction for this branch.** On `feat/s11b-transaction-closeout-v2`, the `state-cleanup` assist
> requires the registry ownership proof. When the install never recorded ownership, cleanup refuses
> with `state-record-missing`, the installer logs `assistant reported non-zero exit (code 1)`, and the
> fixture state remains. That refusal is the correct outcome — the ownership gate working as designed —
> and replaces the old "state root deleted" wording that was true on the old branch but is no longer
> true here.

## 5. Independent verification

The current-tree independent evidence checks recomputed 14/14 evidence-file bytes and 9/9 input bytes
from the recovered read-only-mounted, short-path copy. The generic verifier printed `VERDICT: PASS`
and the dedicated verifier printed `C5 VERDICT: PASS scenario=silent-uninstall-with-state-root`.
The VM was Off after the run and both run disks were detached. The host provenance failure remains
reported separately because its original extraction path exceeded MAX_PATH.

The earlier old-branch verifier result was also **C5 PASS with caveats**; its runtime and documentation
checks remain historical and distinct from the current-tree attempt5 result.

## 6. Caveats and limits

### Current-tree attempt5 caveats

1. The writable-input fallback hashes the complete input tree before and after execution, but cannot
   detect transient tamper that is restored before the post-hash.
2. `dialogAnswerAttempted=false` is recorded; this report makes no zero-dialog claim and records no
   `dialogObserved` claim.
3. The uninstaller hash was observed but not pre-pinned to an expected artifact hash.
4. MAX_PATH extraction failed and required read-only mounting plus a short-path copy for recovery.
5. The full S11a/S11b lifecycle scenarios were not rerun on this tree, so their OpenSpec completion
   boxes remain unchecked.

### Historical old-branch caveats


1. **Suppressed confirmation:** the cleanup confirmation resolved to the safe default `No` while message boxes were suppressed. The fixture survived and the run did not block. This demonstrates the suppressed safe default—not zero prompts.
2. **Uninstaller identity:** the installed `unins000.exe` SHA-256 was recorded as `02431245dfe2a60b55d16f6606929474ef5b8c432339afe73e9070862a390a8c`, but was not independently pinned to an expected artifact hash.
3. **Integrity-count discrepancy:** the orchestrator reported an 8-file cross-check although 14 files had been copied. The independent verifier recalculated all 14 and matched them; the discrepancy in the orchestrator's reported count remains noted.
4. **Scope:** this was one isolated dynamic follow-up, not a rerun of the full eight-scenario v7 matrix. The state-root files were declared disposable fixtures, not representative user configuration.

## 7. Preserved history

- Original v7 verdict: `PASS_WITH_FINDINGS` (unchanged).
- C5: the historical follow-up supplied the missing dynamic attribution and was **PASS with caveats** on the old branch. Current-tree attempt5 now independently supplies **PASS with caveats** for this tree; it does not rewrite the historical result.
- C7: unchanged.
- C10: mitigated for forward-looking runs only; the historical v7 identity limitation remains, so C10 is not resolved.

The high-level task and route record is [`odd/tasks/s11b-c5-dynamic-proof.md`](../../../../odd/tasks/s11b-c5-dynamic-proof.md). The C5 closure summaries link to this report. No lifecycle harness artifacts are included in this document commit.
