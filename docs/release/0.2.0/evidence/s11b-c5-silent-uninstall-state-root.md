# C5 — Silent uninstall with a state-root fixture

| Field | Value |
| --- | --- |
| Change | `release-and-smoke-test-0-2-0` |
| Result | **Not yet verified on this branch** (historical record from old branch preserved below) |
| Date | 2026-09-24 (old branch); pending rebuild on `feat/s11b-transaction-closeout-v2` |
| TDD | Strict TDD enabled for the harness correction; documentation-only reporting has no code-test runner. |

> **Branch reconciliation note.** This report was written against payloads built from the old branch
> (`feat/s11b-transaction-closeout-reconciled`, head `84ddcb3`). The recorded setup hash, checkpoint
> identity, watcher stamp, and harness hash were all derived from that tree and do not describe the
> current branch (`feat/s11b-transaction-closeout-v2`, head `e0c2794`). A fresh disposable-VM cycle on
> an artifact rebuilt from this branch is pending; no proof is claimed for this tree until that rebuild
> and cycle complete. The historical record is preserved below for continuity.

> This is the detailed, repository-local record of the C5 follow-up. It supplements—but does not replace or alter—the original v7 `PASS_WITH_FINDINGS` verdict. C7 is unchanged; C10 remains mitigated only for forward-looking runs, not resolved.

## 1. What was exercised

The isolated scenario used the B1-fixed production setup, then created two declared files at the state root:

- `config.json` — `{"fixture":"s11b-state-root/v1"}`
- `quota-v2-cache.json` — `{"fixture":"s11b-state-root/v1"}`

It captured the state before uninstall, invoked the installed uninstaller with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, and captured the state afterward. The scenario declared no dialog answers and requested VM shutdown on completion. The fixture content matched the declared fixture used by the existing uninstall-preservation scenario.

## 2. Harness correction and regression

A one-manifest run exposed PowerShell 5.1 pipeline unrolling: `Load-Scenarios` returned a scalar `OrderedDictionary` for one scenario, so indexing the expected array failed before the VM cycle began. Eight manifests retained an array.

The harness-only fix was to return the collection with unary-comma array preservation: `return ,$scenarios`. The actual helper passed direct RED/GREEN regression checks under Windows PowerShell 5.1.26100.9444: one manifest returned an `Object[]` of count 1; eight returned an `Object[]` of count 8. The actual scenario validator and structural assertions also passed. No product source was changed.

## 3. Run identity and result

| Identity or result | Recorded value |
| --- | --- |
| Scenario | `silent-uninstall-with-state-root` |
| VM checkpoint | `clean-windows-running-watcher-v7-69c7ff5` (old branch; not valid on this branch) |
| Scenario manifest SHA-256 | `8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93` |
| Watcher build/stamp SHA-256 | `57d7ce68ece311e8c58b1c1d29c8899535182cb628c5e98b9737961ae018a95c` |
| Production setup SHA-256 | `7ff33e5dc847e05b02f1d3789200c5c0c435af37b729247c0b9380a42eea8f35` (old branch; must be produced by a rebuild on this branch and is not yet recorded) |
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

## 4. Independent verification

The independent evidence verifier returned **C5 PASS with caveats**. It recomputed all 14 copied-file hashes and matched them to their copy-time records. The VM was Off after the run, the checkpoint remained intact, and no evidence disk remained attached.

The final documentation-only verification checked the report and closure wording; it did not rerun the VM or recompute runtime hashes. The runtime verification and documentation verification are distinct checks.

> **Status on this branch.** The recorded S11b lifecycle proof and the C5 dynamic proof were run on
> payloads built from the old branch, so they establish nothing for this tree. A fresh disposable-VM
> cycle on an artifact rebuilt from `feat/s11b-transaction-closeout-v2` is pending.

## 5. Caveats and limits

1. **Suppressed confirmation:** the cleanup confirmation resolved to the safe default `No` while message boxes were suppressed. The fixture survived and the run did not block. This demonstrates the suppressed safe default—not zero prompts.
2. **Uninstaller identity:** the installed `unins000.exe` SHA-256 was recorded as `02431245dfe2a60b55d16f6606929474ef5b8c432339afe73e9070862a390a8c`, but was not independently pinned to an expected artifact hash.
3. **Integrity-count discrepancy:** the orchestrator reported an 8-file cross-check although 14 files had been copied. The independent verifier recalculated all 14 and matched them; the discrepancy in the orchestrator's reported count remains noted.
4. **Scope:** this was one isolated dynamic follow-up, not a rerun of the full eight-scenario v7 matrix. The state-root files were declared disposable fixtures, not representative user configuration.

## 6. Preserved history

- Original v7 verdict: `PASS_WITH_FINDINGS` (unchanged).
- C5: this follow-up supplies the missing dynamic attribution and is **PASS with caveats** on the old branch. On this branch, the C5 dynamic proof is pending a fresh rebuild and disposable-VM cycle.
- C7: unchanged.
- C10: mitigated for forward-looking runs only; the historical v7 identity limitation remains, so C10 is not resolved.

The high-level task and route record is [`odd/tasks/s11b-c5-dynamic-proof.md`](../../../../odd/tasks/s11b-c5-dynamic-proof.md). The C5 closure summaries link to this report. No lifecycle harness artifacts are included in this document commit.
