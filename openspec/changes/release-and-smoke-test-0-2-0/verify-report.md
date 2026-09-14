# Verification report — S04a only

**Verdict: PASS — S04a only.**

> **Historical scope:** This report records the S04a verification state as of 2026-09-06. Its G2a/S04c and remaining-slice blockers are superseded by the later G2a pass and S04c/S05-S08 records in `apply-progress.md`; the historical commands and counts below are intentionally unchanged.

This re-verification is limited to S04a (`src/yasb_limitora/discovery.py`,
`scripts/spacepath_spike.ps1`, `tests/test_yasb_discovery.py`, and
`tests/test_yasb_running_probe.py`). No G2a/G2b execution, harness invocation,
YASB/PATH/YAML/CSS mutation, commit, or publication was performed.

The prior S04a FAIL is superseded: its two causes are resolved. `tasks.md` now
checks S04a, and `apply-progress.md` now contains truthful S04a strict-TDD
replay evidence. This verdict does **not** promote G2a, G2b, S04c, or release
readiness.

## Requirements and task coverage

| S04a obligation | Result | Evidence |
| --- | --- | --- |
| Safe `YASB_CONFIG_HOME` precedence and no fallback from present unsafe/empty values | PASS | Retained focused suite covers safe, empty, relative, UNC, device, root, traversal, POSIX, unreadable, and file-component cases. |
| Read-only `detected` / `absent` / `inconclusive` discovery and `.env` metadata boundary | PASS | Focused assertions cover registry/directory/process evidence, absent-creatable `.env` without creation, unsafe `.env`, probe failure, and deadline-exhausted refusal. |
| Fresh exact-name, manual-only process probe | PASS | Focused assertions cover exact `yasb.exe` / `yasb-limitora.exe`, fresh snapshots, failures, and absence of process-control APIs. |
| M1–M8 harness and design §6.2 capture shape | PASS (static only) | Retained PowerShell parser/static check found all eight methods, exactly one `use_shell = $true` (M7), required capture fields, PATH read-only handling, and no forbidden lifecycle/PATH/adoption tokens. |
| Protected examples unchanged | PASS | Re-verification `git diff --exit-code c0204c6be401895ea8c6151503109d209e433a39 -- examples/customwidget tests/test_customwidget_examples.py` exited 0. |
| Strict-TDD evidence | PASS | `openspec/config.yaml` enables strict TDD; S04a is checked in `tasks.md`; `apply-progress.md` truthfully records the four phase outcomes below. |
| G2a / G2b external execution and mechanism selection | UNRUN (external) | Outside S04a. No selection/adoption/acceptance claim exists. |

## Strict-TDD compliance and assertion quality

No project-local strict-TDD override exists at
`.pi/gentle-ai/support/strict-tdd-verify.md`; configured strict-TDD checks were
applied. `apply-progress.md` retains TDD Cycle Evidence tables and its S04a
entry now explicitly records:

| Phase | Truthful evidence |
| --- | --- |
| RED | Post-timeout reconstruction replay against reset `c6225c7d`: **1 failed, 19 passed**; the failed node was `test_existing_unsafe_components_are_rejected`. This is explicitly not presented as the timed-out worker's original evidence. |
| GREEN | Current candidate: **20 passed**. |
| TRIANGULATE | Substring-process mutant: **1 failed, 19 passed**; the failed node was `test_exact_names_only[entries0-running-pids0]`. |
| REFACTOR | Config, metadata, evidence, exact-process, no-control, and harness cases were consolidated without weakening assertions. |

The reported tests exist at the task-declared paths and substantively assert
outcome/reason values, no-fallback and non-creation behavior, exact process-name
matching, snapshot freshness, and prohibited control operations. No tautology,
ghost loop, type-only-only assertion, smoke-only test, or implementation-detail
CSS assertion was found. Static source/harness assertions are supplementary
boundary guards; they do not substitute for the real-YASB G2a gate.

## Validation evidence

The following independent retained evidence applies because the S02 frozen
candidate is unchanged; this re-verification recomputed its SHA-256 as
`93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0`, matching
the retained evidence. The test and PowerShell commands were not rerun solely to
replay an evidence-artifact correction.

| Command | Result |
| --- | --- |
| `python -m pytest -q --strict-markers tests/test_yasb_discovery.py tests/test_yasb_running_probe.py` | Retained independent PASS: **20 passed**. |
| `python -m ruff check src/yasb_limitora/discovery.py tests/test_yasb_discovery.py tests/test_yasb_running_probe.py` | Retained independent PASS: **All checks passed**. |
| `python -m pytest -q --strict-markers` | Retained independent PASS: **705 passed, 3 skipped**. |
| `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` | Retained independent PASS: **11 passed**. |
| `powershell.exe -NoProfile -Command <read-only Parser::ParseFile/static M1–M8 and §6.2 field-contract check>` | Retained independent PASS: 0 parser errors; M1–M8 and required fields present; one shell diagnostic only; forbidden-token set empty. |
| `powershell.exe -NoProfile -EncodedCommand <read-only process query>` | Retained independent PASS: **0 attributable processes**. |
| `sha256sum build/frozen/dist/yasb-limitora/yasb-limitora.exe` | Re-verification PASS: digest above. |
| `git diff --exit-code c0204c6be401895ea8c6151503109d209e433a39 -- examples/customwidget tests/test_customwidget_examples.py` | Re-verification PASS: exit 0. |

## Review workload and boundary

The S04a checkbox is checked. Its declared four-file boundary is intact; no
protected example or pinned example test changed, and no `size:exception` is
recorded.

Keep these accounting views distinct:

- Final pre-S04a baseline `c0204c6...`: **396/400**.
- Remediation baseline `c6225c7...`: **+178/-284 = 462/650**.

The remediation accounting is not substituted for the original S04a review
budget. The completed S04a slice remains within its 400-line boundary; no scope
creep was found in this re-verification.

## Remaining blockers and scope limits

1. **External release blocker:** G2a remains **unrun (external)**. It must select
   exactly one real-target M3/M6/M8 mechanism before S04c can start. It blocks
   S04c and publication.
2. **Later release blockers:** G2b and the remaining unchecked slices remain
   unresolved. The overall change is not release-ready (only S04a is passed here).
3. **Non-blocking observation:** `discover()` checks an exhausted deadline before
   probes, but retained focused evidence does not demonstrate deadline
   re-check/propagation during an in-progress registry/filesystem scan. This is a
   design-depth warning, not an S04a test failure.
