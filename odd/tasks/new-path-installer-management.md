# PATH setup and uninstall consent — historical source record

## Historical context and scope

This record describes the original feature candidate at the source-branch endpoint used for the S3/C3 delta. It is historical evidence only: its test, review, build, installer, and native results do not apply to the sanitized delivery candidate, and its approvals do not transfer. No publication, installer execution, VM use, or host-state mutation is authorized by this record.

The original feature addressed user PATH setup and removal while retaining the then-existing state-cleanup ownership boundary. Its intended scope was HKCU user PATH only; it did not authorize System PATH changes. PATH ownership required exact recorded/live value and type agreement, and a recorded route had to be the final element. Existing current-install paths were successful no-ops without ownership adoption. PATH correction required explicit opt-in. Uninstall PATH removal was separately selectable and limited to a still-owned route; absent or unowned routes were no-ops. State cleanup remained separately consented and revalidated PATH state before clearing bookkeeping.

## Original candidate acceptance and evidence (not current-candidate verification)

The original candidate recorded these acceptance points:

1. An exact current install-directory PATH element succeeds without duplication or ownership adoption.
2. Optional `addtopath` is unchecked by default and discloses correction; correction requires matching ownership evidence and a final recorded element.
3. Uninstall offers `removePATH`, checked by default; silent uninstall retains that default. Unchecked preserves PATH; checked removal of absent or unowned entries is a no-op.
4. Separately accepted state cleanup revalidates the record and PATH. It may proceed when the recorded route is already absent, but refuses changed PATH that still contains the route. Bookkeeping clears only after successful deletion.
5. Applicable review findings are dispositioned before local delivery.

The historical source record reports initial PATH tests failing for an already-present route and an unowned removal, then passing after the original implementation. It also reports a state-cleanup drift test and an already-absent-route test failing before their original fix, then passing afterward. These are source-candidate-only reports, not RED/GREEN evidence for this sanitized reapplication.

The source record reports 163 focused tests passed and 1 skipped; 1,073 full-suite tests passed and 21 skipped; Ruff, whitespace checks, and an import-provenance check passed. It reports an inconclusive language-server pass with auxiliary Protocol-stub warnings. It explicitly leaves native installer compile/lifecycle verification to maintainers and claims no native execution. None of those results verifies this delivery candidate.

## Historical decisions and limitations

The original implementation treated a correct destination already present as a strict no-op even when an older valid route record existed; this was recorded as conservative behavior pending confirmation. The original delivery was split into a PATH/ownership helper unit and an Inno/UI integration unit. The reported source diff exceeded 400 changed lines; that historical size is not a reason to omit code, tests, or documentation here.

The source record also described several source-worktree artifacts and machine-specific locations. Those identifiers are intentionally omitted from this public-safe record. No conclusion about their current custody or state is made here. Original ancestry remains private and is not imported into the sanitized delivery lineage.

## Current delivery status

This file is sanitized historical context accompanying the C3 uninstall-consent delta. It is not a completion checklist or acceptance authority. Verification, review, and delivery decisions belong to the current candidate and its parent-owned task record. Static installer-source assertions do not prove Pascal compilation, Windows installer behavior, user consent rendering, or native lifecycle acceptance.
