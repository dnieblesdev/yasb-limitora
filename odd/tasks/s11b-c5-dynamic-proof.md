# S11b C5 — Dynamic B1 proof

## Goal and rationale
Close the C5 evidence gap by verifying the B1-fixed installed uninstaller with a state-root fixture and recording the result in a reviewable, repository-local evidence report.

## Branch reconciliation note

> **This file was carried from the old branch (`feat/s11b-transaction-closeout-reconciled`, head
> `84ddcb3`). The commit identities, review lineage, and run evidence recorded below were produced on
> that branch and do not apply to `feat/s11b-transaction-closeout-v2` (head `e0c2794`). The historical
> record is preserved for continuity; a fresh disposable-VM cycle on an artifact rebuilt from this
> branch is pending.**

## Scope and constraints
- Keep this record high-level; the linked evidence report is the canonical source for technical run details.
- Do not reference raw evidence outside the repository or include external filesystem paths in C5 documentation.
- Keep lifecycle harness inputs and outputs under ignored `build/`; do not add or force-add them to Git.
- Use only the disposable VM for installer/uninstaller execution; preserve the original v7 verdict and unrelated findings.
- No commit, push, or PR without explicit user authorization.

## Tasks
1. [x] Add and validate an isolated silent-uninstall scenario with a state-root fixture. The actual watcher validator and structural checks passed under Windows PowerShell 5.1.
2. [x] Fix the one-scenario loader array-collapse defect. RED/GREEN regression checks passed for one and eight manifests.
3. [x] Run C5 once on the v7 checkpoint. Result: 1/1 successful; VM Off and evidence disk detached after postflight.
4. [x] Record the initial closure as **PASS with caveats**, preserving the original v7, C7, and C10 statuses.
5. [x] Create the self-contained detailed report under `docs/release/0.2.0/evidence/`; keep this ODD record brief and update the C5 closure summaries to link directly to it. The report records the corrected unary-comma loader fix, run identities, verification, and caveats without external paths or raw-evidence links.
6. [x] Independently verify the report, ODD/review constraints, C5 cross-references, and absence of external paths in C5-specific documentation; confirm no `build/` artifacts were added. Native ASSESS was unassessable while the new documents were untracked; the separate `gentle-ai-verify` check passed.
7. [x] Review the exact six-document commit candidate. The pre-commit verifier passed with no corrections; only the six intended documentation paths are changed.
8. [x] Create the authorized docs-only work-unit commit from those six paths; exclude ignored `build/` and unrelated worktrees. Primary commit on old branch: `7ff9d1acc031a8e4f1ed350dcb403c452e961b30` (not on this branch; the equivalent commit on this branch is pending).
9. [x] Record the primary work-unit commit SHA in this feature record and its Engram mirror; commit the brief metadata update separately because a commit cannot contain its own SHA.
10. [x] Run native review on the committed documentation slice and acknowledge its approved result. The exact six-document range was approved on the old branch; native review on this branch is pending. Finding `R3-1` at `odd/tasks/s11-inno-program-transaction.md:189` (old branch line reference) was informational/non-blocking.

## Acceptance criteria
- The report contains the low-level scenario, harness-fix, run, verification, and caveat record without pointing outside the repository.
- This file remains a short progress/route record and links to the detailed report.
- C5 closure summaries say **PASS with caveats** and link to that report; v7 `PASS_WITH_FINDINGS`, C7, and C10 statuses remain unchanged.
- `build/` remains ignored and absent from the documentation commit scope.

## Execution route and validation
- Harness TDD: enabled (`strict_tdd: true` from active Gentle AI configuration). Test-first runner: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command -` under Windows PowerShell 5.1.26100.9444. Lifecycle runner: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File build/s11b-lifecycle/orchestrate-lifecycle.ps1` (under ignored `build/`). Documentation-only TDD: N/A — no executable behavior changed.
- Task 1: delegated bounded scenario authoring; independent verifier ran the actual validator and structural assertions.
- Task 2: delegated exploration diagnosed the incident; one bounded worker made the fix; independent verifier observed RED and GREEN.
- Task 3: parent performed the user-authorized VM run to retain direct Hyper-V control; separate read-only evidence verification followed.
- Task 4: delegated writer updated closure records; independent document/evidence verification followed.
- Task 5: user-authorized scope; delegated documentation writer because the report, this task record, and four closure summaries form a multi-file work unit. Parent corrected the writer's inaccurate loader-fix description during readback. Exact edit surfaces are limited to those six repository documents. Documentation-only work has no code-test runner; check formatting/links and run independent read-only verification.
- Task 6: `gentle-ai-verify` independently passed the documentation and scope checks; native ASSESS was unassessable due to intentional untracked documents, so the returned high-risk plan required this separate verifier.
- Task 7: parent reviewed the six-path diff; independent `gentle-ai-verify` confirmed no corrections before commit.
- Task 8: parent created one Conventional Commit for the six documentation files under the user's explicit authorization on the old branch; no ignored `build/` files, push, or PR. Primary SHA on old branch: `7ff9d1acc031a8e4f1ed350dcb403c452e961b30` (not on this branch; the equivalent commit on this branch is pending).
- Task 9: parent recorded the primary commit SHA in this file and Engram; a short follow-up metadata commit avoids a self-referential SHA.
- Task 10: native review lineage `review-78b9dde4de7b9b0f` approved the exact six-document committed range on the old branch (`baseRef` `7368a4ff0c8749d68cb85a259b0ffb07810bdebe`, committed-only; that commit is not on this branch) and the exact acknowledgement burned authority. Native review on this branch is pending.
- ASSESS remained unassessable (`schema-incompatible`, no sanitized diagnostic). Independent staged verification passed, and native review closed approved on the old branch; no extra verifier was required by the post-closure assessment plan.
- Primary commit identity on old branch: `7ff9d1acc031a8e4f1ed350dcb403c452e961b30`. Push and PR are not authorized.

## Current outcome and next step
C5 is **PASS with caveats** on the old branch. See [the detailed C5 evidence report](../../docs/release/0.2.0/evidence/s11b-c5-silent-uninstall-state-root.md) for the technical record. On this branch (`feat/s11b-transaction-closeout-v2`), the C5 dynamic proof is pending a fresh rebuild and disposable-VM cycle. The old-branch docs commit `7ff9d1acc031a8e4f1ed350dcb403c452e961b30` passed independent pre-commit verification and native review; the equivalent on this branch is pending. ASSESS remained unassessable, but the staged verifier and closed native review passed on the old branch. No push or publication is authorized.
