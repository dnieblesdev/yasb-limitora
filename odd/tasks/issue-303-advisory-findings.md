# Issue #303 — Advisory findings closeout

## Goal

Close issue **#303** by reading every recorded advisory anchor against current `main` (`abe5e7d`) and
either improving it or dismissing it with a stated reason, keeping the full suite green, and letting
the change be reviewed natively on its own (the only faithful way to recover the claim text the first
two review facades never exposed).

## Scope and constraints

- Only the anchors recorded in #303: the S11a set, the S11b set, and the B1 delivery set.
- No burned review is reopened; every recorded advisory is non-blocking by definition.
- Production finding `R3-001` (unbounded `capture_output` buffering) stays **dismissed** in this
  change by explicit user decision: ISCC output is small and the run is capped by a finite timeout, so
  a streaming bounded reader is disproportionate to a review-chore. The dismissal is recorded here; it
  can become its own approved tooling issue if it is ever scheduled.
- `R2-4` was already closed by the current-tree C5 rewrite delivered in PR #320; nothing to do.
- No VM work: nothing in this change alters installer runtime behavior.
- Branch `chore/issue-303-advisories` from `main` `abe5e7d`. The PR links #303 and carries exactly one
  `type:*` label.

## Dispositions

Each row is one recorded finding. Verdicts follow the issue's acceptance rule: read the anchor and
either improve it or dismiss it with a stated reason.

| # | Finding | Anchor on `main` | Verdict | Reason / change |
| --- | --- | --- | --- | --- |
| 1 | S11a R2-001 readability | `tests/test_setup_assist_protocol.py:594` | IMPROVE | Name says "env not set" while the test *sets* the reason env and asserts it is ignored: rename to `test_reason_not_written_when_reason_env_is_set_but_ignored`. |
| 2 | S11a R2-002 readability | `tests/test_inno_script.py:734` | DISMISS | The env assertions duplicate `:496-498` intentionally: `:734` is the request-env regression anchor. Removing them lowers coverage if the request-env test is refactored. |
| 3 | S11a R2-003 readability | `tests/test_inno_script.py:750` | DISMISS | The scenario-shape test is harness-coupled by design; its docstring states the coupling and the harness validates the same manifests. Removing it drops the only repository-side shape check. |
| 4 | S11a R2-001/R4-001 skip guard | `tests/test_inno_script.py:758-760` | DISMISS | Skip-when-absent is the correct behavior for a git-ignored disposable-VM harness, proven on a clean clone in `5cc45b2`; the "no CI gate" residue belongs to #304 (closed), not to a guessy edit here. |
| 5 | S11b R2-1 | `tests/test_inno_script.py:790-800` | IMPROVE | The DOTALL regex was satisfied by `_regular_file`'s `is_file()` far above the executable literal, so the guard was never exercised. Pin `executable = source_dir / "yasb-limitora.exe"` and `if not _regular_file(executable):` instead. |
| 6 | S11b R3-002 (Exec half) | `tests/test_inno_script.py:361-367` | IMPROVE | The Exec half rests on `rfind` ordering only. Assert the Exec sits inside the ownership-guarded `begin`/`end` block, and pin the predicate body (empty `Candidate` Exit, `SameText`-containment, `Result := FileExists(Candidate)`). |
| 7 | S11b R3-001 | `scripts/build_setup.py:162-168` | DISMISS | User decision: ISCC output is small and timeout-capped; a streaming bounded reader is disproportionate here. Recorded as a known, accepted bound; may get its own issue if ever scheduled. |
| 8 | S11b R4-002 | `scripts/build_setup.py:162-168` | IMPROVE | `text=True` without `encoding`/`errors` can raise an uncaught `UnicodeDecodeError` and break the exit-code contract. Pass `encoding="utf-8", errors="replace"`; regression asserts the kwargs through the existing spy-runner route. |
| 9 | S11b R2-2 | `packaging/inno/SetupAssistant.isi:285-291` | DISMISS | The explicit two-branch form is clearer than string concatenation on a security-sensitive uninstaller; both branches are test-pinned (`:557-563`); `CleanupConsent` accurately names the consent gate it reads. |
| 10 | S11b R2-3 | `packaging/inno/yasb-limitora.iss:117` | DISMISS | The step-1 comment (`:207-208`) already states ownership is path-bound and *not* textual inequality with the prior string, matching the code. The residual "New" naming imprecision is not a correctness claim. |
| 11 | S11b R2-4 | C5 evidence table | DISMISS | Already closed by PR #320: the document now separates a "Historical old-branch run identity" section and the reconciliation note explicitly covers watcher stamp and harness hash. |
| 12 | S11b R2-5 | `odd/tasks/s11a-setup-assist-security.md:34-64` | IMPROVE | Renumber the misordered 15-17 group to physical order, repoint the internal "item 15" reference to its new number (item 16), mark the first `32.` as superseded, and give the second `32.` its own number (item 33, bumping the tail). |
| 13 | B1 R2-DOC-EVIDENCE | `odd/tasks/g1-rollback-consent-gate.md:61-63` | IMPROVE (with 15) | The recorded RED quote uses `== 2` while the landed guard was relaxed to `>= 2`. Tightening the guard back to `== 2` (finding 15) makes the historical quote exactly the landed assertion; no rewrite of the record's chronology is needed. |
| 14 | B1 R2-DOC-FOOTPRINT | `odd/tasks/g1-rollback-consent-gate.md:80-81` | IMPROVE | `(+14/-4)` misread git's changed-line count (`14`) as additions. Verified against git: `355838f` is `yasb-limitora.iss` `+10/-4` and `tests/test_inno_script.py` `+26` (so the 36/4 total is right), and the merged PR #310 totals `+166/-4` across three files (`+48/-4` for the two code files). State the exact numbers. |
| 15 | B1 R2-TEST-COUNT | `tests/test_inno_script.py:122` | IMPROVE | Tighten `>= 2` to `== 2` with a comment: the current tree has exactly two `SuppressibleMsgBox(` sites (458, 489) and both are pinned per function below, so an unreviewed third prompt now fails the guard. |
| 16 | B1 R2-TEST-COUNT (paired) | same as 15 | — | The finding had two lenses (readability/resilience) at one anchor; both close with the finding-15 change. |

## Tasks

1. [x] Triage every anchor read-only against `main` (`abe5e7d`); record the per-anchor verdicts above.
2. [x] Apply the accepted improvements: test surface (1, 5, 6, 15), production (8), records (12, 13, 14). Focused 121 passed / 1 skipped.
3. [x] Run focused tests, the full suite (**1040 passed, 21 skipped**), `git diff --check` (clean), and the scoped Ruff check (`All checks passed!`).
4. [x] Independently verify the diff (read-only `gentle-ai-verify`): **verified-with-caveats**; one LOW finding corrected and re-verified **RESOLVED**.
5. [x] Create work-unit commits (test surface, production fix, records) with the full suite green: `6552c64` (WU1 tree verified at 1039 passed / 21 skipped), `da57b37`, and this records commit.
6. [in progress] Run native review on the committed range and acknowledge the approved result.
7. [ ] Open the PR linked to #303 with exactly one `type:chore` label and confirm `native-proof`.

## Acceptance criteria

- Every recorded location is read and either improved or dismissed with a stated reason (the table above).
- Full suite stays green and the PR's `native-proof` check passes.
- The follow-up change is reviewed on its own, and that review states its findings in full.

## Execution route and validation

- Runner: `python -m pytest` (Python 3.10.5) in the primary worktree `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora`.
- Strict TDD applies to the production change (finding 8): the spy-runner regression asserting the
  `encoding`/`errors` kwargs must fail RED before the one-line fix and pass GREEN after it.
- Findings 1, 5, 6, 15 are assertion tightenings/renames of existing tests (no behavior change).
- Findings 12-14 are record corrections; the exact numbers are the git-verified ones stated above.
- Independent read-only verification runs after the edits and before any commit.

## Verification evidence

- Writer TDD (finding 8): RED `KeyError: 'encoding'` (`1 failed in 0.34s`); GREEN focused
  `121 passed, 1 skipped`; scoped `ruff check` → `All checks passed!`; `git diff --check` clean.
- Parent: full suite **1040 passed, 21 skipped** (71.09s); independent RED reproduction — with only
  `scripts/build_setup.py` reverted to `HEAD`, the new regression failed, and passed again with the fix.
- Independent verification (`gentle-ai-verify`, read-only over the unstaged diff): scope discipline,
  claim-to-change mapping, ledger renumbering (monotonic 1..38, no dangling references) and the
  git-derived footprint numbers all PASS; one LOW finding — the empty-candidate `Exit;` was not bound
  to its branch — corrected with a positional assertion and re-verified **RESOLVED**, no new findings.
- Scope: exactly five modified paths plus this record; every dismissed anchor untouched.
