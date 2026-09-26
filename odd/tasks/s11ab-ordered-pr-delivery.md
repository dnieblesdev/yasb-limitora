# S11a/S11b — Ordered PR delivery

## Goal
Publish and merge the validated S11a, S11b, and G1/B1 work in dependency order, with focused PR slices and the existing commit identities preserved.

## Scope and constraints
- Keep S11b work in `feat/s11b-transaction-closeout-reconciled`; use a separate linked worktree for `feat/s11a-setup-assist` when updating PR #298. Leave the primary worktree unchanged.
- The user authorized creating the S11b issue/PR chain and merging in order, and selected preservation of existing SHAs with size exceptions for the identified atomic slices (519, 410, and 438 changed lines).
- Do not rebase or rewrite reviewed/cited commits. No PR may merge with failing required checks.
- Keep `build/` ignored; never run installers on the host. Compare the rebuilt C5 setup hash with the recorded artifact; rerun C5 only in the disposable VM if it differs.
- C5 remains **PASS with caveats**; preserve the caveats and prior v7/C7/C10 status.

## Tasks
1. [x] Verify remote PRs, branch ancestry, issue policy, and review budgets. S11a PR #298 exists but its native-proof check fails; no S11b/G1 PR or approved S11b issue exists.
2. [x] Create and read back one approved tracking issue for S11b/B1/C5. Issue #299 was created with `enhancement` and `status:approved`; the repository has no issue form, allows blank issues, and the duplicate search found no match.
3. [x] Remove the S11b-only build-driver test/helper from S11a and verify locally. Commit `72d18ca` removes 18 lines from `tests/test_inno_script.py`; focused tests passed (31) and the full suite passed (942 passed, 3 skipped). Projected PR #298 diff: 501 lines.
4. [x] Resolve native finding `R1-nonce-predictable-transport` in the S11a transport before any push. Native review marked it CRITICAL; the user authorized an Inno API-feasibility spike and disposable-VM validation. The current 194-line environment candidate removes the active elevated file exchange and passes full tests plus prior compile-only checks. Setup Assist still fails closed because of the separate Inno/Python schema mismatch (C1 follow-up). No VM proof or native approval exists; no native review calls were made per the current instruction. Keep publication blocked.
5. [x] Prepare ordered PR slices from existing commit boundaries, preserving SHAs; use the user-approved size exceptions only for the identified slices. Every PR must link an approved issue and have exactly one `type:*` label.
6. [x] Push required branches and open PRs in dependency order; verify each diff, check, review, base, and issue linkage before merging.
7. [x] Merge only after required reviews and checks pass; record PR/merge results. Keep skills tracking/copy outside scope.

## Verified delivery facts
- S11a: PR #298, `feat/s11a-setup-assist` → `main`, remote head `bd31f71`; local isolated worktree has unpushed fix commit `72d18ca`. It is not combined with S11b.
- S11b: `feat/s11b-transaction-closeout-reconciled` at `84ddcb3`; no PR exists. Its ordered commits include S11b code (`69c7ff5`), lifecycle evidence/closure (`04dd16a`, `7368a4f`), and C5 evidence/metadata (`7ff9d1a`, `660d6a6`, `84ddcb3`).
- G1/B1: `fix/g1-rollback-consent-gate` at `49d43a0`, based on `04dd16a`, with implementation `355838f`; no PR exists.
- The approved issue #297 covers S11a only. The S11b/B1/C5 duplicate search returned no match.
- The S11b PR must build on the corrected S11a head so C1–C3 changes are not duplicated. PR #298 failed because its S11a tests referenced S11b-only `scripts/build_setup.py`; local commit `72d18ca` removes that dependency, but it is not pushed because the native security finding still blocks publication.
- The repository has no PR template; follow the required issue-linked PR body and exact type-label policy from the loaded skills.

## Execution and validation
- The S11a PR's `native-proof` failure was `test_s11_build_driver_validates_frozen_input_and_passes_explicit_iscc_defines`, which requires the S11b-only `scripts/build_setup.py`. Commit `72d18ca` removes the build-driver constant/helper/test from S11a; S11b commit `69c7ff5` adds the driver and its tests. Focused tests passed (31) and the full suite passed (942 passed, 3 skipped).
- Native review lineage `review-b5775d638257b9fc` found candidate-caused CRITICAL finding `R1-nonce-predictable-transport` in `packaging/inno/SetupAssistant.isi:214-224`; last recorded state was `correction_required`, with a 200-line correction budget. Current uncommitted candidate is 194 diff lines (123 additions + 71 deletions) across seven files. CLI dispatch is request-only and Inno checks `SetEnvironmentVariableW` before `Exec`; the active elevated path does not use request/result files. The OpenSpec transport section now marks legacy file flows inactive and records the remaining schema mismatch. Focused tests passed (84); final full suite passed (947 passed, 3 skipped). ISCC 6.7.3 compile-only validation passed before the final test/doc-only cleanup; `SetupAssistant.isi` did not change afterward. The stale frozen-entry test now requires `_REQUEST_ENV`, and `test_setup_assist_protocol.py` verifies nonce-only does not dispatch; parent authorized this test adjustment after the full suite exposed the old expectation. A separate schema mismatch (`choices` plus string operations vs typed Python request) still makes Setup Assist fail closed and remains a C1 follow-up. No installer execution, VM proof, native review/status call, commit, push, or PR update occurred. Detailed tracking is `odd/tasks/s11a-setup-assist-security.md` in this S11b worktree.
- Proposed commit slices and recorded sizes: S11a `bd31f71` (519); C1 `6b87885` (387); C2 `0646725` (180); C3 `a50335c` (60); S11b code `69c7ff5` (410); execution evidence `04dd16a` (16); closure `7368a4f` (438); G1/B1 `355838f`+`49d43a0` (158); C5 plus metadata through `84ddcb3` (134).
- Run the relevant installer contract/setup-assist tests and Inno compilation after the S11a/S11b/G1 slices are integrated. Reproduce the C5 setup artifact and compare its hash before deciding whether the disposable-VM proof must be rerun.
- Issue #299 was created once after exact title/body/labels review and target-host readback. Review exact body/labels before each PR creation and read back every created PR from the verified repository.

## Delivery progress (2026-09-25)

- Task 4 closed: the S11a transport finding is resolved, reviewed and VM-proven. The reviewed S11a head is `8681dd2`, plus `5cc45b2` for the CI test guard, reviewed separately by lineage `review-079881b1ce5b5384`.
- Task 5 closed as three stacked slices, with every SHA preserved and no rebase: **PR #300** `feat/s11a-transport-typed-request` → `main` (707 lines, `type:feature`), **PR #301** `feat/s11a-provider-selection` → PR #300's branch (370 lines, `type:feature`), **PR #302** `feat/s11a-installer-hardening` → PR #301's branch (141 lines, `type:bug`). All three link the approved issue #297 and carry exactly one `type:*` label.
- PR #298 was **closed as superseded**, not merged: its head `bd31f71` carried the pre-correction transport. Its branch stays on the remote for history but must not be reused for new pushes.
- Task 6 in progress: branches pushed and PRs read back; the required `native-proof` check passes on all three. The first CI run of PR #302 exposed a real defect (a test asserting a file inside git-ignored `build/`), fixed in `5cc45b2` and re-verified green. No merge, release or push to `main` was performed.
- Merge order matters and is user-owned: #300 → #301 → #302, bottom-up. After that the S11b PR must build on the S11a head so C1–C3 are not duplicated, then G1/B1, then C5.
- Open and not yet actionable: the three advisory `SUGGESTION`s from the approved review of the net candidate. The facade never exposed their claim text and that lineage's authority is burned, so the follow-up change must be driven by its own review findings rather than by guessing at the originals. One CI-side observation: the file `build/s11a-lifecycle/` never ships, so harness and VM-evidence debts belong in issues, not in these PRs.

### Parked as issues (user decision, 2026-09-25)

- **#303** `test(s11a): address the advisory review findings on the delivered test surface` (`enhancement`) — the three `SUGGESTION`s plus the two WARNINGs from the CI-guard review, with the explicit note that their claim text was never exposed.
- **#304** `fix(proof): make the disposable-VM verification gates fail closed` (`bug`) — `roundtrip-verify.ps1` check (d) cannot fail, the guest watcher cannot see step exit codes, and `verify-evidence.py` covers less than its PASS suggests. Needs a decision first: version a minimal harness subtree, or keep it disposable and advisory.
- **#305** `docs(s11a): record the r3 VM proof identities and what it does not prove` (`documentation`) — the r3 identities plus the five limits (silent-run `config-apply`, `assist-request` payload, refusal cause no longer recorded, `owned-cleanup` attribution inference, ISO attached by design).
- None of the three carries `status:approved` yet; that label is the user's gate to start, and any PR linking them needs it.

### S11b PR opened (2026-09-25)

**#306** `feat/s11b-transaction-closeout-v2` → `feat/s11a-installer-hardening`, `type:bug`, +1255/−18 across 12 files, linking #299 as the umbrella with an explicit note that it does not close it (B1/G1 and the C5 re-proof remain). Commits: `d4b4013` (C1 `path-remove` fragment), `355df8a` (G1 closeout + build driver), `e0c2794` (S11a delivery record and this plan), `de76b29` (the S11b records re-authored for this base). Documentation dominates the diff, so the PR exceeds the 400-line review budget: the chained-PR rule permits docs to travel with the unit they describe, but a `size:exception` acceptance is the maintainer's.

### Merged (2026-09-25)

All four PRs merged in order with the `size:exception` accepted on #306: #300 → `8c4072e3`, #301 → `d9688073`, #302 → `94db00a9`, #306 → `73181486`. Each child was retargeted to `main` after its parent merged (the parent branches are kept on purpose, and GitHub only auto-retargets on deletion). Every commit SHA is preserved and verified as an ancestor of `origin/main`: `bd31f71`, `1f37fa6`, `93aa649`, `b363abe`, `8681dd2`, `5cc45b2`, `d4b4013`, `355df8a`, `de76b29`. Every merge happened on a `MERGEABLE`/`CLEAN` PR with `native-proof` green; `main` carries no branch protection.

### S11b review closed (2026-09-26)

The unrun review recorded above did run, on the same commits, and closed honestly.

- Lineage `review-b7e714040d2e7c77` (candidate `5cc45b2..de76b29`, tier high, 1273 changed lines, correction budget 200): four lenses admitted, and `review-resilience` raised one candidate-caused CRITICAL - `R4-001` at `packaging/inno/yasb-limitora.iss:254-260`, where the candidate's cleanup ordering let an owned `.failed` quarantine present at the rollback step make `RenameFile(AppDir, FailedDir)` fail, so the rollback exited before restoring the prior payload and before re-advertising its registry state.
- Correction applied with test-first evidence (two tests that fail on the parent `de76b29` and pass on the fix) as `93a802e` (`fix(installer): clear the owned failed quarantine before re-quarantining`), touching only `packaging/inno/yasb-limitora.iss` and `tests/test_inno_script.py`. Contract of the fix: the owned quarantine is cleared before the rename, its `DelTree` result is checked fail-closed with a logged `Exit`, and the post-restore cleanup of the step-2 quarantine is preserved and stays ownership-guarded.
- Delivered as **PR #307** (`fix/s11b-owned-failed-quarantine` -> `main`, `type:bug`, `Refs #299` non-closing) with the required `native-proof` check passing in 1m32s, merged as **`c3b8a03d268188467abe0d14c21ca414df7c787a`**; `main` no longer carries the un-corrected rollback.
- The targeted validator materialized, validated the correction, and the lineage closed `approved` (store revision `sha256:62162782b748465be7e59d1294c67413d68d50f562e4f6f1c1df415ab0b22948`) with its acknowledgement burned (`gentle-ai.review-acknowledged/v1`).
- Getting there cost one detour worth recording rather than hiding: every validator attempt was refused with `repository_context_unavailable ... invalid rctx2 repository context` while STATUS kept reissuing the identical slot, because the capture path derives the correction from the **live worktree** while STATUS derives it from the frozen snapshot. The two uncommitted records of this change (these two `odd/tasks` files, both inside the frozen reviewed scope) were enough to make the provider-issued context unresolvable. Normalizing the worktree made the byte-identical binding work on the first attempt, and the two files were then restored unchanged. Reported upstream as **Gentleman-Programming/gentle-ai#4997**, with a diagnosis comment on #4664.
- The eight remaining validator findings are informational and non-blocking; they are recorded verbatim in **#303**.

Remaining in the plan: the B1/G1 slice on the merged head, then the C5 artifact rebuild and its disposable-VM re-proof, plus the parked issues #303/#304/#305 (no `status:approved` yet).

Branch `feat/s11b-transaction-closeout-v2` from `5cc45b2`, in the S11b worktree, uncommitted and independently verified: net delta four files (391 insertions / 9 deletions) plus two untracked ODD records. Carried the C1 uninstall `path-remove` fragment (adapted to the S11a environment transport) and `69c7ff5` by cherry-pick; dropped C2 and C3 by user decision. Full suite 982 passed / 4 skipped with the correct runner (`PYTHONPATH=<worktree>/src` against the S11a venv); ISCC 6.7.3 compile-only exit 0. No S11a work was lost: all nine removed lines are the intended replacements.

Runner rule learned the hard way: the system python imports `yasb_limitora` from the primary worktree, the S11a venv imports it from the S11a worktree, and only `PYTHONPATH=<worktree>/src` makes it import the worktree under test. Evidence produced with the wrong runner (six phantom failures) must be discarded, not reported as pre-existing.

Still pending before the S11b PR: re-author the tree-bound documentation and evidence (SHAs, the `7ff33e5d…` setup hash, checkpoint names, line references, the false "C1–C3 delivered on the S11a side" claim), make the `explicit-cleanup` evidence record the ownership-gate refusal as correct, then verification, native review and the PR on top of `feat/s11a-installer-hardening`.

Committed on `feat/s11b-transaction-closeout-v2` (user-authorized, ODD records included): `d4b4013` C1 `path-remove` fragment + renamed test; `355df8a` G1 transaction closeout + `scripts/build_setup.py`; `e0c2794` the S11a delivery record and this plan. Delta against `5cc45b2`: six files, 567 insertions / 9 deletions. Post-commit verification: final tree 982 passed / 4 skipped, intermediate `d4b4013` 971 passed / 4 skipped in a clean clone, so the branch is bisectable.

Consequence for the S11b evidence that must not be glossed over: the recorded S11b lifecycle proof and the C5 dynamic proof were run on payloads built from the old branch, so on this base they establish **nothing**. Either a fresh disposable-VM cycle is run on an artifact rebuilt from this branch, or the PR ships with those proofs explicitly marked as pending. That is a user decision, and the documentation phase records whichever answer it gets.

The plan's assumption that the S11b branch merely duplicates C1–C3 was wrong. Merge base `bd31f71`; S11b-only commits: `6b87885` C1 (3 files, +303/−84), `0646725` C2 (5 files, +76/−104), `a50335c` C3 (4 files, +43/−17), `69c7ff5` (4 files, +402/−8), plus docs/evidence. Content facts: the S11a head emits **no** `path-remove` from `packaging/inno/` (C1's uninstall fragment is missing); `cleanup_literal_state` is `(registry, state_dir)` on S11a versus `(state_dir)` on S11b, so C2 is missing **and** removes the registry ownership proof S11a deliberately kept; C3 deletes `configassist`, which Slice 2 deliberately added — do not carry it. The S11b evidence for `explicit-cleanup` only holds under C2, so a product decision is required before any reconciliation: keep S11a's ownership gate (and rewrite that evidence) or adopt C2 (and revert the S11a decision).