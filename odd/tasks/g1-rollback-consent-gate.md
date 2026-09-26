# G1 rollback consent gate — make the unattended rollback non-interactive

## Goal

Remove the two non-suppressible prompts that can hang an unattended failed upgrade in the G1
rollback, without weakening the interactive consent semantics. Finding B1 from the S11b lifecycle
proof: the rollback Execs the new uninstaller with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, but
`InitializeUninstall` reaches two plain `MsgBox` calls that `/SUPPRESSMSGBOXES` cannot suppress.

## Scope

- `packaging/inno/yasb-limitora.iss`:
  - `ConfirmStateCleanup`: plain `MsgBox` -> `SuppressibleMsgBox` with suppressed default `IDNO`,
    so a silent uninstall preserves the state root instead of waiting forever.
  - `PromptManualClose`: plain `MsgBox` -> `SuppressibleMsgBox` with suppressed default `IDCANCEL`,
    so a silent uninstall with YASB running aborts the uninstaller (fail closed) instead of waiting.
- `tests/test_inno_script.py`: new static contract tests for both prompts and their fail-safe
  suppressed defaults.

## Non-goals

- No change to the interactive behaviour: a user who runs the uninstaller normally still sees both
  prompts and still decides.
- No change to the runtime consent gate: `setup_assist.py` still refuses `state-cleanup` unless the
  request carries the literal `"YES"`, so the installer script is not the only guard.
- No change to the rollback's payload/registry ordering, the bounded wait, or the quarantine rules.
- No rebuild of the frozen payload or the lifecycle input set, and no VM re-run. Proving the fix
  end to end needs its own build/custody cycle, which stays pending.

## Constraints

- Strict TDD: the contract tests are written and observed failing before the installer script changes.
- Preserve every invariant the existing tests assert: `MB_YESNO or MB_DEFBUTTON2`, `= IDYES`,
  `MB_RETRYCANCEL`, `= IDRETRY`, `= IDCANCEL`, the gate order
  (`ManualCloseGate` before `CleanupConsent := ConfirmStateCleanup`), `YASB is currently running`,
  and the absence of any process-control call.
- Authored source+test footprint stays small and bounded; the project budget is 400 lines.
- Technical artifacts in English. No commit without explicit user authorization.

## Tasks

1. **RED.** Add contract tests asserting that the `[Code]` section uses `SuppressibleMsgBox` for both
   prompts, that the cleanup consent's suppressed default is `IDNO`, that the manual-close prompt's
   suppressed default is `IDCANCEL`, and that no plain `MsgBox(` call remains in `[Code]`. Observe
   them fail against the current script.
2. **GREEN.** Change the two calls in `packaging/inno/yasb-limitora.iss`. Re-run the new tests and the
   pre-existing installer-contract tests.
3. **Checks.** Run the focused test module, the full suite, Ruff, and `py_compile`.
4. **Native compile.** Compile the installer script through the bounded build driver so the Pascal
   change is proven to compile, not just to match a regex.
5. **Close.** Commit on the isolated branch and run native review.

## Evidence to record

- The RED observation (exact failing assertions) and the GREEN result.
- Focused and full test counts, Ruff and `py_compile` results.
- The native compile result and the produced setup identity.

## Evidence recorded

- **RED.** New test `test_uninstall_prompts_are_suppressible_with_fail_safe_defaults` failed against the
  unmodified script on `assert code.count("SuppressibleMsgBox(") == 2` -> `assert 0 == 2`; the module
  reported `1 failed, 46 passed`.
- **GREEN.** New test passes and the module reports `47 passed`, so every pre-existing installer
  contract still holds (`MB_YESNO or MB_DEFBUTTON2`, `= IDYES`, `MB_RETRYCANCEL`, `= IDRETRY`,
  `= IDCANCEL`, gate order, no process control).
- **Full suite.** `961 passed, 3 skipped`. The three skips are
  `tests/test_cli_platform_boundary.py:68` ("non-Windows boundary subprocess proof runs on
  non-Windows"), platform-bound and unrelated to this change.
- **Ruff.** `ruff check tests/test_inno_script.py` -> `All checks passed!`. `ruff check .` reports 151
  pre-existing findings in unrelated modules; the repository has no `[tool.ruff]` config and no Ruff
  step in CI, so the scoped check is the meaningful one.
- **py_compile.** `tests/test_inno_script.py` -> OK.
- **Native compile.** `scripts/build_setup.py` with `--app-version 0.2.0` against the unchanged frozen
  bundle printed `build-setup: ok` and produced exactly one setup:
  `yasb-limitora-0.2.0-setup.exe`, 11,052,514 bytes, sha256
  `7ff33e5dc847e05b02f1d3789200c5c0c435af37b729247c0b9380a42eea8f35`. The pre-fix production setup was
  11,052,467 bytes (`ba1aea2c...`), so the change is present in the compiled artifact and the Pascal
  compiles. The temporary output was deleted without executing the setup.
- **Footprint.** 36 insertions / 4 deletions: `packaging/inno/yasb-limitora.iss` (+14/-4) and
  `tests/test_inno_script.py` (+26).
- **Not proven here.** The end-to-end absence of the hang inside a VM. That needs a new frozen build,
  new setups, a new input-set custody identity, and a lifecycle re-run (at least scenario 5), which
  remains pending for a separate decision.

## Risks

- A suppressed `IDNO` changes nothing for interactive users but means an automated uninstall never
  cleans the state root without an explicit request; that is the intended fail-safe, and it matches
  the runtime gate that already requires a literal `"YES"`.
- A suppressed `IDCANCEL` makes the manual-close gate fail closed under silence, so the uninstaller
  aborts and the rollback continues down the existing filesystem-restore path. The existing rollback
  code already handles a non-zero uninstaller result, and a test asserts it does not ignore it.

## Native review

- Lineage `review-cb2dbb877619cd93`, target
  `sha256:bd91306e3bda7b7b2a59c0630d0c24ec85db746ad9c3fffdce8d8ff33407d5c6`, tier **high**, 133 changed
  lines, correction budget 67, four lenses in order: `review-risk`, `review-resilience`,
  `review-readability`, `review-reliability`.
- Verdict **approved** on the last admitted event with all four reviewers prepared and submitted.
  Authority is burned (`gentle-ai.review-acknowledged/v1`), so delivery follows ordinary repository
  policy and the review grants no delivery authority by itself.
- Advisory finding `R2-001` (lens readability, `odd/tasks/g1-rollback-consent-gate.md:80-81`,
  severity SUGGESTION, disposition informational) targets the footprint statement. It is
  non-blocking: it opened no correction, and the closure states it is never a reason to re-run the
  review on this candidate. Left unaddressed by decision and recorded here as later work.
- Reviewed commit identity:
  `355838f fix(installer): make uninstall prompts suppressible`, containing exactly the reviewed
  bytes of these three paths.
- Blockers hit while obtaining the review, and how each was cleared: the lens models resolve through
  the interactive session's model list, which did not contain
  `qwen-token-plan-individual/deepseek-v4.1-flash`, so every submission failed with
  `reviewer-model-not-found`; adding that model to `~/.pi/agent/models.json` by the pi documentation's
  built-in-provider merge semantics, plus a Pi reload to rebuild the session's list, restored
  resolution; the concurrent four-lens group then hit one provider `429` and succeeded after the rate
  window passed. The three failed submissions ran no reviewer and mutated nothing
  (`mutation_performed: none`), and the lineage survived them unchanged.