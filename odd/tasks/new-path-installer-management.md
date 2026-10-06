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

## C4 sanitized reapplication note

The clean-delivery C4 unit adds two boundaries to the historical C3 behavior above. Install PATH correction now requires both the unchecked `addtopath` choice and a separate unchecked `correctownedpath` choice. The effective `correctionConsent` is a strict boolean, defaults to false when omitted, and remains false for silent installs. PATH correction still requires exact recorded/live PATH and registry-type agreement with the recorded route last; missing or mismatched proof fails closed.

State cleanup now requires the exact recorded full PATH value and registry type to remain live, along with the unchanged ownership record, immediately before deletion. An already-absent recorded route remains a successful no-op for the independent PATH-removal operation, but it no longer authorizes state deletion. The original-candidate acceptance text above is retained as historical context; this stricter cleanup contract is the C4 correction, not a claim that the earlier decision always had that meaning.

The C4 delivery-unit label does not mean native C4 acceptance: the original native C4 attempt remains failed/consumed and did not reach cleanup. On the clean candidate, the selected baseline run produced 8 expected feature-absence failures, 2 passes, and 159 deselections before source reapplication. After reapplication, those same 10 selected cases passed. A bounded fake/static regression selection passed 62 cases with 1 skip and 106 deselections. These are current-candidate hermetic/static results only; they do not establish native installer, VM, HKCU, or UI acceptance. Original-candidate results elsewhere in this record are not verification of the clean candidate.

## C5 sanitized reapplication note

The C5 route-disclosure follow-up preserves the C4 correction-consent boundary and adds an Inno-side preview before interactive consent. The installer reads only the recorded route and PATH string for display; it presents the prior route and current destination in a default-No prompt only when the record is parseable, the snapshot matches, the recorded route is final, and the destination is not already present. This preview is disclosure, not ownership proof: the helper remains responsible for full record, PATH-value, and registry-type validation immediately before mutation. Missing or stale preview data fails closed. No provider/configuration data is read or displayed. Silent setup does not grant correction.

C5 static tests on the clean delivery candidate first produced four expected structural baseline failures before source changes: consent assignment, suppressible-prompt count, silent/default-negative consent, and route-disclosure presence. After the source delta, those four leaves and three bounded static controls passed (7 passed); Ruff passed for the test module. These are current-candidate static results only. No compile, installer execution, VM, HKCU, or lifecycle acceptance is claimed here. Historical source-candidate build details and machine-specific evidence are intentionally not reproduced.

## C6 sanitized reapplication note

C6 preserves C5's default-No correction preview and adds read-only live User PATH registry-type verification before disclosure. The preview requires the recorded type to be `REG_SZ` or `REG_EXPAND_SZ`, matching the live value type queried around the raw PATH read; query/close failures or mismatches suppress it. Raw recorded and destination routes containing Unicode bidi controls are refused without sanitization or rewriting. For a valid owned old route with a missing destination, a `path-add` request without specific correction consent now refuses with `path-correction-consent-required` and preserves both PATH and ownership record, rather than appending the new route. This covers interactive decline and silent `addtopath`.

The unchanged S5-product baseline was independently recorded as three passes and two expected structural failures: the registry API declaration assertion and missing bidi-helper extraction. The two fake-registry protocol cases passed and are not RED evidence for the installer change. On the Phase B candidate, the five bounded explicit static/fake cases passed (5 passed); Ruff and whitespace checks passed. These checks are hermetic/static only. No Pascal compile, Inno execution, VM, HKCU interaction, or native lifecycle acceptance is claimed. Existing historical C4 native failure/cleanup gap, unknown I1 state, and unproved temporary-parent race remain unresolved.

## Current delivery status

This file is sanitized historical context accompanying the C3 uninstall-consent, C4 exact-ownership, C5 route-disclosure, and C6 type-matched/bidi-safe preview and no-fallback refusal deltas. It is not a completion checklist or acceptance authority. Verification, review, and delivery decisions belong to the current candidate and its parent-owned task record. Static installer-source assertions do not prove Pascal compilation, Windows installer behavior, user consent rendering, or native lifecycle acceptance.
