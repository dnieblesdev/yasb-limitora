# Agent Guide

## Authority and scope

- Maintainer instructions and approved project decisions define product scope,
  priorities, architecture, and repository policy.
- Skills provide execution guidance. They do not create or override product
  decisions or project policies.
- Do not import requirements from skills without explicit maintainer agreement.
- If documentation, instructions, or tooling conflict, explain the conflict.
  Do not silently change project decisions or bypass actual security or CI gates.
- Use current approved specifications as references. Historical plans and
  archived evidence are not authorization for new work.

## Product boundaries

- Product runtime is Windows-only. Linux, macOS, and WSL are not supported
  runtimes; hermetic tests do not establish native Windows support.
- Preserve the ownership boundary:
  `YASB CustomWidget -> yasb-limitora CLI / current JSON -> Limitora public API`.
- YASB owns presentation. This repository owns configuration, bounded execution,
  sanitized projection, and the CLI/process boundary.
- Limitora owns provider detection, authentication, transport, and interpretation.
  Do not duplicate provider logic or depend on private Limitora APIs.
- Preserve the sole current JSON contract, stream behavior, and exit semantics.
  Never add debug or progress text to machine-readable stdout.
- Keep secrets, workspace identifiers, raw provider payloads, and unsanitized
  exceptions out of public output and published evidence.
- Preserve shared deadlines, process containment, resource ownership, bounded
  cleanup, and fail-closed behavior.
- Do not weaken ownership checks to make cleanup or recovery succeed.
- Do not automatically edit user YASB YAML, CSS, or credentials.
- Native CLI proof is not automated YASB rendering or end-to-end UI proof.

## Working approach

- Inspect the branch, worktree, and existing changes before editing.
- Implement only the authorized scope. Small, clear changes can proceed directly.
- For non-trivial changes, present scope, affected areas, verification, and risks;
  obtain plan approval before editing.
- When pre-existing changes or concurrent sessions are present, propose an
  isolated worktree and obtain approval before proceeding.
- Preserve other work, including tracked, untracked, and ignored files.
  Do not reset, clean, discard, or remove worktrees without explicit authorization.
- Avoid unrelated refactors, bulk formatting, dependency upgrades, and changes
  to the operator's environment.
- Keep affected tests and documentation with the work unit they support.
- Evaluate review suggestions against actual evidence. Separate optional work
  outside the scope; explain dismissals rather than starting endless fix cycles.
- Write repository content, code comments, commits, and PRs in English.
  Communicate with the maintainer in Spanish.

## Setup and verification

Use the authorized checkout/worktree root and its intended Python environment.
Confirm that imports resolve to that worktree, not another editable checkout.
Use dependency and tool versions declared in `pyproject.toml`.

Development setup:

```powershell
python -m pip install -e ".[test,lint]"
```

Standard checks:

```powershell
python -m pytest -q --strict-markers <test-path-or-node>
python -m pytest -q --strict-markers
python -m ruff check .
```

- For testable behavior changes, demonstrate meaningful RED, implement the
  smallest GREEN change, and refactor with checks remaining green.
- For documentation or purely mechanical changes without a meaningful RED,
  explain why TDD does not apply and perform proportionate verification.
- Run focused tests before the full suite for code changes, then Ruff.
- Check documentation links against tracked content, not just local files.
- Native proof follows `.github/workflows/windows-proof.yml` and its helpers.
  Skipped tests, mocks, and hermetic success do not replace native evidence.
- If indispensable Windows or VM verification is unavailable, agree on the
  verification plan before implementing.
- Execute installer lifecycle scenarios only in an authorized disposable VM,
  never on the operator's host.
- Report checks that failed or were not run. Never invent results or promote
  evidence from another tree as proof of the current candidate.

## Git, issues, and pull requests

- Implementation authorization does not authorize delivery operations.
- Obtain explicit authorization for these blocks:
  1. Commit.
  2. Push and PR creation.
  3. Merge.
  An explicit request may authorize multiple blocks together.
- Before remote reads or writes, establish the destination, permitted operations,
  and authorized credential/session. Local preparation is not remote permission.
- Every PR links an issue. The issue does not require a particular label or
  approval separate from authorization of the implementation task.
- Every PR has exactly one applicable `type:*` label.
- Agree whether an issue reference is closing (`Closes`) or nonclosing (`Refs`).
  Do not assume permission to close issues.
- Aim for focused PRs of about 400 changed lines, counting additions plus
  deletions. This is a review target, not a hard repository limit.
- Discuss larger changes and possible cohesive splits before expanding them.
  Never compress code or omit tests or documentation to fit a line budget.
- Skills recommending stricter labels or budgets do not change these policies.
  If an actual delivery gate prevents execution, report it and seek resolution.
- Verify applicable checks and required reviews before merge.
  Review approval applies only to the candidate actually reviewed.

## Repository map and completion report

| Location | Purpose |
|----------|---------|
| `src/yasb_limitora/` | CLI, configuration, execution, and safe projection |
| `tests/` | Hermetic tests and explicitly identified native proof |
| `scripts/` | Build and verification tooling |
| `packaging/` | Frozen bundle and installer definitions |
| `examples/customwidget/` | YASB integration examples |
| `docs/` | Architecture, contracts, operational and release guidance |
| `openspec/` | Change specifications and planning records |
| `odd/tasks/` | Work tracking and evidence records |

Read the relevant sources rather than copying temporary milestone status here:
- `docs/architecture/README.md`
- `docs/specifications/json-output.md`
- `docs/windows-json.md`
- `pyproject.toml`
- `.github/workflows/lint.yml`
- `.github/workflows/windows-proof.yml`

At handoff, report what changed, actual checks and outcomes, unrun verification,
remaining risks, and the next required decision. Preserve historical provenance;
do not rewrite past evidence to imply that a different candidate was verified.
