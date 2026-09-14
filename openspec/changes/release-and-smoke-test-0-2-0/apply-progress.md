# Apply progress: release-and-smoke-test-0-2-0

## S01 — Release identity and user migration material: COMPLETE

Date: 2026-02-06 (local). Worker: delegated apply executor. Delivery: single S01 slice only; auto-chain explicitly NOT started (user prohibition respected). No commit, tag, build, installer, release, or PR action was taken.

### Completed tasks

- [x] S01: single version source, dynamic pyproject attr, focused identity tests, release notes + migration material, minimal README/roadmap pointers, stale build-lib placeholder removed, and all required verification green after the separately authorized Python 3.10 provenance-guard fix.
- [ ] S02, G1, and all later slices/gates: NOT STARTED (out of this work unit).

### Files changed (S01 authored diff: 283 lines, budget ≤300)

| File | Change | Lines |
| --- | --- | --- |
| `src/yasb_limitora/__init__.py` | `__version__ = "0.2.0"` (single source of truth) | +1/−1 |
| `pyproject.toml` | `dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr = "yasb_limitora.__version__"}`; `[project.scripts]` unchanged | +4/−1 |
| `tests/test_version_identity.py` | New focused identity/argv/docs-guard test module (17 tests) | +155 |
| `docs/release/0.2.0/RELEASE_NOTES.md` | New: first-public 0.2.0, sole artifact, #137 break, fixed unsigned/SmartScreen disclosure (design §7.3 wording), boundaries, non-publication status | +59 |
| `docs/release/0.2.0/MIGRATION.md` | New: checkout→setup.exe migration, #137 consumer guidance, optional PATH, G2-validated no-PATH mechanism wording, manual YASB lifecycle boundary, state retention, unsigned artifact | +50 |
| `README.md` | Installation section points to setup.exe/MIGRATION, editable checkout labeled development-only; documentation-map entry for `docs/release/0.2.0/` | +7/−1 |
| `docs/roadmap.md` | Current-gate paragraph: release-material pointer; explicit no-tag/no-artifact/no-publication wording retained | +3/−1 |
| `build/lib/yasb_limitora/__init__.py` | Deleted (stale git-ignored setuptools output reporting placeholder `0.1.0`; never edited as source; not in authored diff) | — |
| `openspec/changes/release-and-smoke-test-0-2-0/tasks.md` | S01 checkbox only | +1/−1 |

### TDD Cycle Evidence

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED | Wrote `tests/test_version_identity.py` before any production/doc change | `python -m pytest -q --strict-markers tests/test_version_identity.py` | 8 failed, 9 passed — failures exactly on missing 0.2.0 source, dynamic pyproject, placeholder sweep, stale build-lib copy, missing release docs, missing README/roadmap pointers |
| GREEN | `__version__ = "0.2.0"`; pyproject dynamic attr; created RELEASE_NOTES.md + MIGRATION.md; deleted `build/lib/yasb_limitora/__init__.py`; README/roadmap pointers | `python -m pytest -q --strict-markers tests/test_version_identity.py tests/test_windows_only_documentation_contract.py` | 23 passed (17 identity + 6 doc-contract guards unweakened) |
| TRIANGULATE | Independent failure case: injected public `-rc` identity (`__version__ = "0.2.0-rc1"`) into the single source | `python -m pytest -q --strict-markers tests/test_version_identity.py` | 3 failed (`single_source_of_truth`, `dynamic_attr`, `rc_identity`), 14 passed — mutation caught; source restored to `"0.2.0"` immediately after |
| REFACTOR | Fixed one test defect during GREEN (static-version regex `^version = ` also matched the dynamic `version = {attr = ...}` line; narrowed to `^version = ["']`); added lowercase "unsigned artifact" sentence to notes without altering fixed disclosure wording; focused rerun | `python -m pytest -q --strict-markers tests/test_version_identity.py tests/test_windows_only_documentation_contract.py tests/test_cli_output_version.py tests/test_pr3b_package_provenance.py` | 104 passed, 1 failed (pre-existing, see deviations) |

### Verification evidence

- Focused: `python -m pytest -q --strict-markers tests/test_version_identity.py` → 17 passed.
- Guards: `tests/test_windows_only_documentation_contract.py` → 6 passed (not weakened; release material lives in new `docs/release/0.2.0/` files; guarded regions still forbid product versions; roadmap still forbids `Limitora 0.2.0`).
- Closed argv/version-selection contract: `--version`, `--version 0.2.0`, `--version=0.2.0`, `-V`, `version`, `--output-version 2`, `--output-version=1` all exit `2` with `invocation_invalid` and no version bytes on stdout (locked in `test_version_identity.py`, consistent with `test_cli_output_version.py`).
- Provenance regression: `python -m pytest -q --strict-markers tests/test_pr3b_package_provenance.py` → **29 passed** in 0.46s.
- Full suite after the separately authorized guard fix: `python -m pytest -q --strict-markers` → **608 passed, 3 skipped** in 35.67s.
- Native Windows proof: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** in 7.23s (runnable and run on this Windows host; not `unrun (external)`).

### Deviations / notes

- A pre-existing supported-Python blocker was found during S01 verification: Python 3.10.5 has no `sys.flags.safe_path`, so `scripts/verify_limitora_package.py` rejected `-I` even though isolated safe-path semantics were active. The user separately authorized a version-aware guard fix that still requires `sys.flags.isolated`; direct probes confirmed `-I` passes and non-isolated invocations fail closed. This correction is not counted in S01's 283-line budget.
- Placeholder sweep result: after S01, no active surface (`pyproject.toml`, package init, README, roadmap, release material) reports `0.1.0`, and the stale `build/lib` copy is deleted, so a repository sweep for the placeholder returns no live hit.
- No design deviations in S01: dynamic-attr mechanism, fixed unsigned/SmartScreen wording, and doc-placement strategy follow design §2.2, §7.3, §9.1 exactly.

### Remaining work (not this work unit)

- S02 → G1 → S10 chain, S03, S04a → G2a → S04c, S05–S09, S11–S16, G2b per `tasks.md`. Auto-chain start is prohibited by the user until explicitly approved.

### Workload / PR boundary

- S01 is one review unit: 283 authored lines (≤300 slice budget). Source, tests, and docs kept together. Rollback boundary: revert only the version/release-material files listed above; no tag, release, or artifact exists.
- The Python 3.10 provenance-guard correction is a separately authorized focused work unit in `scripts/verify_limitora_package.py` (26 additions / 18 deletions, including behavior-preserving type narrowing and structural cleanup required by diagnostics). RED was the reproducible Python 3.10 isolated-mode failure; GREEN made the guard version-aware while retaining mandatory `sys.flags.isolated`; TRIANGULATE proved plain and `-E -s` invocations still fail closed; REFACTOR left primary/auxiliary diagnostics clean. Verification: 29 provenance tests passed, full suite 608 passed / 3 skipped, and native proof 11 passed.

## S02a — PyInstaller onedir specification and build driver: COMPLETE

Date: 2026-02-07 (local). Worker: delegated apply executor (recovery of a timed-out writer's partial S02 work, split per tasks.md into S02a + S02b only). No commit, tag, installer, release workflow, ZIP/setup artifact, or PR action. G1/S03/S04a/auto-chain NOT started.

### Recovery note

The prior writer's files existed on disk and were verified by reading actual contents (not its preview) and by running them: baseline focused run of the recovered `tests/test_packaging_spec.py` + recovered smoke tests was 18 passed before this session's audit fixes. Two required corrections were then applied strict-TDD (RED first):

1. `SOURCE_DATE_EPOCH` was captured in `capture_source_identity` but never propagated into the PyInstaller subprocess environment when resolved from git; `run_build` now takes `source_date_epoch` and sets it in the child env, and `main()` passes the resolved value.
2. Spec-construction tests matched raw spec text (docstring/comments could satisfy them); they now strip the module docstring and `#` comment lines via `_code_only` and assert real construction (`EXE(...exclude_binaries=True`, `console=True`, `COLLECT(`, the major-version `!= 6` enforcement expression, `upx=False` ×2, `collect_submodules("limitora")`, `datas=[]`, entry source `yasb_limitora.cli import main` / `sys.exit(main())`), with a docstring-mutant test proving comment/doc-only matches are rejected.

Preserved from recovered content and re-verified: PyInstaller `>=6,<7` enforcement (spec raises `SystemExit`; driver `check_pyinstaller_version`), UPX off, Limitora submodule collection, empty `datas`, single-`__version__`-source version rendering via `@@VERSION@@`/`@@VERSION_TUPLE@@` placeholders, `_internal/build-info.json` record (version, source_commit, python, pyinstaller, limitora, source_date_epoch; no path/secret bytes), failed-output cleanup (`shutil.rmtree` of failed dist), bounded hidden-import diagnostics (`diagnose_failure`: 1200-char tail + `ModuleNotFoundError` hint). Public argv/entry ordering unchanged; entry mirrors the console-script target with no wrapper reordering.

### Files changed (S02a authored: 377 lines, budget ≤400)

| File | Change | Lines |
| --- | --- | --- |
| `packaging/pyinstaller/yasb-limitora.spec` | New (recovered, verified): onedir/console/entry contract, PyInstaller 6 enforcement, UPX off, limitora collection, empty datas, version-resource via `YASB_LIMITORA_VERSION_INFO` | 44 |
| `packaging/pyinstaller/version_info.txt.in` | New (recovered, verified): placeholder-driven VSVersionInfo; no hard-coded product version | 20 |
| `scripts/build_frozen_bundle.py` | New (recovered) + this session's `source_date_epoch` propagation fix in `run_build`/`main` | 177 |
| `tests/test_packaging_spec.py` | New (recovered) + this session's `_code_only` hardening, mutant test, propagation test | 136 |

### TDD Cycle Evidence (S02a)

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED | Added `test_source_date_epoch_propagated_to_subprocess` (asserts child env carries the resolved epoch) and docstring-mutant/code-only spec assertions before touching the driver | `python -m pytest -q --strict-markers tests/test_packaging_spec.py tests/test_frozen_smoke.py` | 1 failed (`TypeError: run_build() got an unexpected keyword argument 'source_date_epoch'`), 20 passed — failure exactly on the missing propagation |
| GREEN | `run_build(..., source_date_epoch=None)` sets `base["SOURCE_DATE_EPOCH"]`; `main()` passes `identity["source_date_epoch"]` | same focused command | 21 passed |
| TRIANGULATE | Independent mutation: replaced the propagation assignment with `pass` in a scratch copy | focused single test, then restore | mutant FAILED the propagation test; file restored; 21 passed again. Docstring-mutant test independently proves construction assertions cannot be satisfied by comments/docstrings |
| REFACTOR | No structural refactor needed; `ruff check` clean on all S02a files; focused rerun | `python -m ruff check ...` / focused pytest | All checks passed; 21 passed |

### Verification evidence (S02a)

- Focused: `python -m pytest -q --strict-markers tests/test_packaging_spec.py` → 16 passed (within the 21 combined above).
- Syntax: `python -m py_compile` on spec, driver, template-consuming files → compile-ok.
- Fail-closed tooling precondition: `python scripts/build_frozen_bundle.py` on this host → `pyinstaller_missing: PyInstaller >=6,<7 not installed`, exit 2 (correct precondition refusal, no output written).
- Full suite after the S02b contract audit: `python -m pytest -q --strict-markers` → **630 passed, 3 skipped** in 36.85s (independent verification).
- Native Windows proof: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** in 7.25s.
- **Native frozen build proof: `unrun (tooling)`** — PyInstaller 6.x is not installed in the local Python 3.10.5 environment (`importlib.metadata` raises `PackageNotFoundError`), and this work unit is not permitted to install tools. No clean frozen build was executed; no native frozen-build proof is claimed. The driver's behavior against a stubbed runner (success, failure cleanup, diagnostics) is covered by tests.

## S02b — Frozen smoke driver: COMPLETE

Same session/worker and recovery note as S02a. A later narrow audit correction (2026-02-07, strict-TDD) hardened the JSON payload contract: the validator previously accepted any JSON object (including `{}`) as a valid normal payload and could accept `{}` for invalid/helper paths when exit/stderr happened to match. `_json_defect` now requires a recognized root `execution_state` (`complete`/`partial`/`not_run`/`execution_error`) for normal output and `execution_state == "execution_error"` with `execution_error.code == "invocation_invalid"` for invalid/helper checks, retaining the removed root `version` rejection; failure reasons now surface the JSON defect instead of only exit/stderr detail.

### Files changed (S02b authored: 250 lines, budget ≤250)

| File | Change | Lines |
| --- | --- | --- |
| `scripts/smoke_frozen.py` | New (recovered, verified) + audit correction: contract-aware `_json_defect(expect_error=...)`, `_STATES`, defect surfaced in `_validate` reasons; docstring compressed | 136 |
| `tests/test_frozen_smoke.py` | New (recovered) + `test_cli_failures_are_fail_closed` triangulation + audit RED test `test_bare_object_rejected_for_missing_error_contract`; fixture normal payload aligned to recognized state `complete` | 114 |

Coverage: bundle structure/version (missing exe, missing/invalid build-info, version mismatch fails and stops before any subprocess), normal frozen CLI (JSON object with recognized root `execution_state`, no removed root `version` field, bounded exit 0/1), invalid-argv and helper/bootstrap sentinel without helper env (exit 2 + `invocation_invalid` + stdout carrying the `execution_error`/`invocation_invalid` contract; helper path additionally rejects traceback/bootloader output), timeout (bounded, sanitized), secret/path sanitization (`token=hunter2` redacted, bundle path replaced, excerpt ≤240 chars), fail-closed paths (wrong exit code, bare `{}` payload, traceback in helper path, root `version` regression each fail their check). Diagnostics remain bounded and non-secret; helper env keys are stripped from child env; no network/provider calls; single disposable temp config removed on exit.

### TDD Cycle Evidence (S02b)

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED/baseline | Recovered smoke driver + 4 recovered tests verified against actual file contents before any change | `python -m pytest -q --strict-markers tests/test_frozen_smoke.py` (combined run) | 4 recovered smoke tests passed; no implementation defect found in the driver itself |
| GREEN | No driver change required; driver already satisfied the recovered contract | — | — |
| TRIANGULATE | Added `test_cli_failures_are_fail_closed`: independent failure case where all three CLI checks misbehave (exit 0 on `--bogus`, traceback/bootloader on helper sentinel, root `version` field on normal CLI) | `python -m pytest -q --strict-markers tests/test_frozen_smoke.py` | 5 passed — each misbehavior fails closed with the expected reason; structure still passes |
| REFACTOR | `ruff check` clean; focused rerun | focused pytest | 5 passed |

### TDD Cycle Evidence (S02b audit correction)

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED | Added `test_bare_object_rejected_for_missing_error_contract` before any driver change: runner returns exit 2 + stderr `invocation_invalid` + stdout `{}` for every CLI invocation; test demands invalid-argv and helper-sentinel fail with an "error contract" reason and normal-cli fail on missing recognized `execution_state`. Fixture normal payload changed `"ok"`→`"complete"` (behavior-neutral pre-change) | `python -m pytest -q --strict-markers tests/test_frozen_smoke.py` | 1 failed, 5 passed — failure exactly at invalid-argv status `'pass' != 'fail'`, proving `{}` was accepted when exit/stderr matched |
| GREEN | `_json_defect(bundle_root, stdout, expect_error)`: expect_error requires `execution_state == "execution_error"` and dict `execution_error.code == "invocation_invalid"`; normal path requires `state in _STATES = {complete, partial, not_run, execution_error}`; removed root `version` rejection retained; `_validate` passes `expect_error=not normal` and reports the JSON defect as the failure detail | same focused command | 6 passed |
| TRIANGULATE | Two independent mutations of the restored driver, each run against the new test: (1) expect_error branch forced to `return ""`; (2) recognized-state check forced to `return ""` | focused single test per mutant, then byte-identical restore (`cmp`) | both mutants FAILED the test; restore verified identical; 6 passed again |
| REFACTOR | Compressed module docstring, `check_structure` mismatch return, `_validate` normal branch, and two test expressions to hold budget; no check weakened | `python -m ruff check ...` / focused pytest / `wc -l` | ruff clean; 6 passed; 136 + 114 = 250 ≤ 250 |

### Verification evidence (S02b)

- Focused: `python -m pytest -q --strict-markers tests/test_frozen_smoke.py` → 6 passed (5 recovery-session + 1 audit-correction test).
- Usage fail-closed re-verified after the audit correction: `python scripts/smoke_frozen.py` (no args) → usage message, exit 2.
- Full suite and native proof: same independently verified runs as S02a → 630 passed, 3 skipped; native proof 11 passed.
- **Native frozen smoke proof: `unrun (tooling)`** — requires an actual S02a frozen candidate, which requires PyInstaller 6.x; not installed locally and installation not permitted. No native frozen-smoke proof is claimed.

### Deviations / notes

- `ruff format --check` would reformat these files, but the repository baseline does not enforce `ruff format` (48 pre-existing files would be reformatted; no ruff config in `pyproject.toml`); `ruff check` is clean and was used as the diagnostics gate.
- Public argv/entry ordering untouched; no ZIP/setup/public artifact produced; output roots remain internal/disposable (`build/frozen/`).
- The timed-out writer's preview was not trusted; every file was read and executed to verify actual state before corrections.

### Remaining work (not this work unit)

- G1 (Inno staged-swap spike), S03, S04a -> G2a -> S04c, S05-S16, G2b per tasks.md. Auto-chain and G1 remain explicitly unauthorized; a delivery decision is needed before any further unit.

### Workload / PR boundary

- S02a: 377 authored lines (<=400). S02b: 250 authored lines (<=250, at budget after the audit correction). Tests kept split per unit; not recombined. Rollback: delete `packaging/pyinstaller/`, `scripts/build_frozen_bundle.py`, `scripts/smoke_frozen.py`, `tests/test_packaging_spec.py`, `tests/test_frozen_smoke.py`, and any disposable `build/frozen/` output; no published artifact exists.

## G1 — pre-install evacuation fallback: PASS

Date: 2026-09-05 (local). Worker: delegated apply executor. Work unit: `G1-preinstall-evacuation`. No S10, RDD, commit, tag, PR, release, elevation, or product-source change was made.

### Completed task

- [x] G1: the selected pre-install evacuation fallback was built, executed, natively verified, cleaned, and recorded. Historical post-install rename evidence remains a separate rejected `fail`.

### Native evidence

- Fresh run: `181cab27ecf2fb30dc7b16bbef42801d`; AppId `{55D372A6-1DA5-41BE-B7AB-65CAB362E620}`; exact canonical root and HKCU key were unique and preflight-absent, with `.new`, `.old`, and `.failed` siblings also absent.
- Input binding: actual `build/frozen/dist/yasb-limitora` S02 onedir; build-info version `0.2.0`, PyInstaller `6.22.2`, Python `3.13.5`; candidate executable SHA-256 is recorded in `binding.json`.
- Three fresh setup binaries were compiled with Inno Setup `6.7.3`: baseline, success, and induced-failure variants. Setup and ISS hashes are retained. All lifecycle setup/uninstaller invocations used `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=...`.
- Non-elevation: `token_is_admin=false`, Inno `IsAdminLoggedOn=False`, `IsAdminInstallMode=False`, `User privileges: None`, HKCU install root; no override/elevation switch was used.
- Success: baseline installed natively; new installer captured DisplayVersion/UninstallString/InstallLocation before moving canonical to `.old`; Inno copied/registered at canonical; build-info and native `DisplayVersion=0.2.0` passed; `.old` was deleted only after success. The exact new `UninstallString` returned `0` and, after bounded second-phase wait, removed canonical, siblings, and key.
- Failure: baseline was recreated with equal registry values/types. A post-bookkeeping `cmd /c exit 121` was deterministically logged. Inno 6.7.3 logs show installation completion precedes `ssPostInstall`; therefore the smallest disposable harness correction invoked the exact newly registered native uninstaller, which removed the new canonical/key while retaining `.old`. Captured prior HKCU values and types were restored, `.old` was renamed to canonical, and the exact restored prior uninstaller returned `0`.
- Boundary: before/after observable state-root child count, HKCU User PATH type/length/hash, and `YASB_CONFIG_HOME` presence/hash were equal. Final exact canonical, `.new`, `.old`, `.failed`, and HKCU key state was absent. Retained sanitized raw evidence: `build/g1-fallback/181cab27ecf2fb30dc7b16bbef42801d/**`.

### Verification commands

| Command | Result |
| --- | --- |
| `python build/g1-fallback/run_g1_fallback.py` | **PASS**; native build/execute/verify/cleanup; final verdict recorded in run evidence |
| `python scripts/smoke_frozen.py build/frozen/dist/yasb-limitora --expect-version 0.2.0` | PASS; structure, invalid argv, helper sentinel, normal CLI |
| `python -m pytest -q --strict-markers tests/test_packaging_spec.py tests/test_frozen_smoke.py` | 22 passed |
| `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` | 11 passed |
| `python -m pytest -q --strict-markers` | 629 passed, 3 skipped, 1 unrelated pre-existing failure: `tests/test_version_identity.py::test_stale_build_lib_placeholder_copy_is_removed` because disallowed `build/lib/yasb_limitora/__init__.py` is present |

### Deviations and remaining work

- The historical post-install rename attempt remains unchanged and is preserved as `fail`. Inno's late `ssPostInstall` hook cannot roll back a transaction it has already logged as complete; this was diagnosed in native logs and the disposable exact-new-uninstaller correction is explicitly documented, not presented as an Inno transaction rollback.
- Remaining work is S03, S04a/G2a/S04c, S05–S16, and G2b per `tasks.md`. G1 does not authorize S10 or any chained slice.

### Workload / PR boundary

- One external gate work unit only. Durable authored changes are limited to the evidence report, design D7/§3.3 wording, task checkbox, and this cumulative progress entry; the durable documentation addition remains below the 400-line limit. Disposable harness/setup/raw evidence is confined to `build/g1-fallback/` and no publication artifact was created.

## Historical G1 — evidence-record remediation: FAILED HANDOFF

Date: 2026-02-08 (local). Worker: delegated apply executor. This was an evidence correction only; no installer, compiler, frozen runtime, S10, or RDD action was run.

### Candidate and run binding

- Run: `1e19e1aabfbfdfca28f8e2c82db1f98c`; disposable AppId `{DDD7E71F-7825-41CF-B49A-29DB3F084286}`.
- Candidate: retained S02 frozen onedir candidate, version `0.2.0`, source commit `528313c972e14ef72f784ada0284ac7fdf5a5d82`, PyInstaller `6.22.2`, Python `3.13.5`; candidate/setup/script hashes remain in `build/g1/<run>/evidence/`.

### Completed corrections and exact evidence

- Corrected the historical evidence handoff to a single historical `fail` verdict, removed PENDING/in-progress wording, removed reliance on Inno `/LOG` claims, indexed only present raw files, and separated supported self-log/exit/guard/key/hash evidence from unavailable A1/A2/A3 log captures, PATH captures, and Phase B.
- Recorded in `design.md` §3.3 that post-install rename is rejected/disproven because the exact new `UninstallString` exited `0` while leaving the canonical renamed payload; selected the design-named pre-install evacuation fallback for later S10/S11 design implementation.
- G1 was kept unchecked in `tasks.md` at that historical handoff and pointed at the selected fallback.
- Supported exact evidence: `logs/spike-new-<run>.selflog.txt`; `evidence/a2-exit.txt` (`0`); `evidence/a3-new-uninstall.txt` (exact new uninstaller exit `0`, canonical present, siblings/key absent); `evidence/final-guarded-residuals.txt`; key/uninstaller captures; candidate/setup/script hashes and build-info.
- Guarded cleanup deleted only the exact literal residual directory after directory, exact-basename, and no-reparse checks. Post-cleanup verification: canonical, `.new`, `.old`, `.failed`, and the exact unique uninstall key are absent; raw `build/g1/<run>` evidence remains.

### Stop reason and truthful blockers

- The historical Phase B was stopped because A3 failed the required exact-new-uninstaller health check. The forced step-6 failure, reverse-swap, registry restoration, prior-uninstaller check, and after-state comparison were not run in that attempt and are not claimed as historical evidence.
- No before/after PATH evidence existed in that historical attempt. Its recorded non-elevation observations were not promoted to an independent passed gate. That historical attempt remained failed; the selected fallback was subsequently implemented in the disposable harness and separately evidenced above.

### Verification and workload / PR boundary

- No tests were required or run for this external-gate evidence correction. Verified markdown/content by inspecting the corrected sections and exact raw-artifact index; verified cleanup with the guarded PowerShell literal-path command above.
- Authored documentation changes remain under the requested 400-line limit. This is a single G1-fail handoff boundary; no other slice evidence was altered, and no commit was created.

## G1 — pre-install evacuation evidence-integrity remediation: COMPLETE

Date: 2026-09-05 (local). Worker: delegated apply executor. Delivery: `auto-chain`, feature-branch-chain; bounded unit `G1-preinstall-evacuation` evidence remediation only. Native mechanism was independently verified PASS. No installer/compiler rerun, commit, tag, PR, S10, RDD operation, or product-source/test change was made.

### Completed corrections

- [x] Replaced the ambiguous `script-hashes.txt` handoff with explicit actual-root compile-input hashes and separate retained-copy hashes.
- [x] Added `evidence/integrity.json`, a bounded derived SHA-256 record covering 26 entries: compile inputs, retained copies, all three setup EXEs, and every retained compiler/native/self/process log. Its self-verification is `pass`.
- [x] Added `evidence/execution-binding.json`, explicitly labeled post-run-derived rather than contemporaneous telemetry. It binds the ordered three compile actions and seven setup/uninstaller actions to redacted logical argv, native/process logs, exit codes, exact captured `UninstallString` references, and recomputed log hashes.
- [x] Corrected the durable narrative without touching raw `failure-self.log` or `b2-failure.log`: Inno completed bookkeeping, `[Run] cmd /c exit 121` was observed, and the harness deliberately ran the exact new native uninstaller as the late-failure rollback correction before restoring `.old` and captured HKCU values/types.
- [x] Updated the evidence report, design §3.3, and G1 task guard to reference the integrity conditions. G1 remains checked only because both derived records self-verify.

### Files changed

- `build/g1-fallback/181cab27ecf2fb30dc7b16bbef42801d/evidence/script-hashes.txt`
- `build/g1-fallback/181cab27ecf2fb30dc7b16bbef42801d/evidence/integrity.json`
- `build/g1-fallback/181cab27ecf2fb30dc7b16bbef42801d/evidence/execution-binding.json`
- `docs/release/0.2.0/evidence/inno-staged-swap-spike.md`
- `openspec/changes/release-and-smoke-test-0-2-0/design.md`
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md`
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`

### Verification evidence

- Evidence JSON syntax passed with `python -m json.tool`.
- Recomputed all 26 integrity entries from current bytes; every digest matched. Existing setup EXE hashes were recomputed and retained.
- Read-only PowerShell check: exact canonical run root plus `.new`, `.old`, `.failed` siblings were absent; exact HKCU uninstall key was absent; attributable process count was `0`.
- Raw log hashes remained unchanged during remediation; no `.log` or EXE mutation occurred.
- TDD: N/A — external evidence-only remediation; native mechanism was already independently verified PASS and lifecycle execution was prohibited.

### Remaining tasks

- G1 remediation is complete. S03, S04a/G2a/S04c, S05–S16, and G2b remain as listed in `tasks.md`; this unit does not start another slice.

### Workload / PR boundary

- Feature-branch-chain boundary: one bounded G1 evidence-remediation unit only. Durable authored changes remain below 400 lines; no PR or commit was started.

## S10 — Inno base installer identity, consent UI, and task contract: COMPLETE

Date: 2026-09-06 (local). Delivery: `auto-chain`, `feature-branch-chain`; S10 is its own review unit. No commit, tag, PR, installer execution, assistance invocation, or native review was performed.

### Completed tasks

- [x] Added the fail-closed Inno static contract: per-user x64 identity, fixed AppId, version/output defines, canonical install path, `NoRepair=1`, and unchecked optional User PATH task.
- [x] Recorded the G1-selected pre-install evacuation mechanism without adding the rejected post-install rename; captured consent booleans, default-negative cleanup confirmation, and manual-close Retry/Cancel UI wiring.
- [x] Added static guards for forbidden transport/target-path/secret arguments and YAML/CSS or portable-artifact references.

### Files changed

- `packaging/inno/yasb-limitora.iss` (+119 lines)
- `tests/test_inno_script.py` (+116 lines)
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md` (S10 checkbox)
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md` (this evidence)

### TDD Cycle Evidence

| Phase | Command / action | Result |
| --- | --- | --- |
| RED | `python -m pytest -q --strict-markers tests/test_inno_script.py` before the script existed | 9 failed: required installer file was missing |
| GREEN | Same focused command after implementation | 9 passed |
| TRIANGULATE | `python -c "from pathlib import Path; p=Path('packaging/inno/yasb-limitora.iss'); t=p.read_text(encoding='utf-8'); m=t.replace('Flags: unchecked','Flags: checked',1); assert 'Name: \\\"addtopath\\\"; Description:' in m; line=next(x for x in m.splitlines() if 'Name: \\\"addtopath\\\"' in x); assert 'Flags: unchecked' not in line; print('TRIANGULATE mutant: addtopath checked mutation detected')"` | `TRIANGULATE mutant: addtopath checked mutation detected` |
| REFACTOR | `python -m ruff check tests/test_inno_script.py`; focused pytest rerun | ruff clean; 9 passed |

### Verification evidence and deviations

- `python -m pytest -q --strict-markers` → 638 passed, 3 skipped, 1 unrelated pre-existing failure: stale `build/lib/yasb_limitora/__init__.py` remains present; this allowed surface was not edited.
- `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → 11 passed.
- Inno Setup compilation was not run: native review and machine installation are outside S10 and prohibited by the delegation.
- No external/native installer evidence is claimed. S11 remains responsible for executable lifecycle and assistance behavior.

### Remaining tasks

- S03, S04a/G2a/S04c, S05–S09, S11–S16, and G2b remain as listed in `tasks.md`; no later slice was started.

### Workload / PR boundary

- S10 authored changed lines: **278** (119 installer + 116 tests + 2 task-checkbox diff + 41 progress lines), within the ≤350 budget. This is a standalone feature-branch-chain review unit; stop here before S03 or any later slice.

### Corrective rerun (automatic-gatekeeper allowance)

- Focused: `python -m pytest -q --strict-markers tests/test_inno_script.py` → **9 passed** (0.04s).
- Full: `python -m pytest -q --strict-markers` → **638 passed, 3 skipped, 1 failed** (37.77s). Exact node: `tests/test_version_identity.py::test_stale_build_lib_placeholder_copy_is_removed`. Traceback: `tests/test_version_identity.py:59`, assertion `not (ROOT / "build/lib/yasb_limitora/__init__.py").exists()`, with `exists()` true.
- Causality: **outside S10**. The failing assertion targets ignored `build/` state; the S10 files do not create or modify it. Read-only proof found source and ignored copy byte-identical (975 bytes; SHA-256 `ca6775189a06d5c9b9667f52320538a4bb781c08de29648c0bfd3fa7312977e4`); no ignored file was edited or deleted.
- Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** (7.63s). Ruff: `python -m ruff check tests/test_inno_script.py` → **All checks passed**.
- Cleanup: post-run attributable-process check returned no matches after the test runner exited.
- No S10 implementation correction was authorized or applicable. S10 remains **in progress** and its checkbox is retained unchecked pending the ignored stale-copy blocker. Corrective rerun authored delta: **13 changed lines**; cumulative S10 authored scope: **291 lines**, within the ≤350 budget. Delivery boundary remains `auto-chain`, `feature-branch-chain`; no later slice started.

## S10 — final remediation and verification: COMPLETE

Date: 2026-09-06 (local). Delivery: `auto-chain`, `feature-branch-chain`.

### Final remediation

- Deleted only the authorized ignored artifact `build/lib/yasb_limitora/__init__.py` (975 bytes); its parent directory was retained.
- No tracked source, other build evidence, installer execution, commit, tag, push, PR, or native review was performed.

### Exact verification evidence

- `python -m pytest -q --strict-markers tests/test_version_identity.py::test_stale_build_lib_placeholder_copy_is_removed` → **1 passed**.
- `python -m pytest -q --strict-markers tests/test_inno_script.py` → **9 passed**.
- `python -m pytest -q --strict-markers` → **639 passed, 3 skipped** in 36.61s.
- `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** in 7.38s.
- `python -m ruff check tests/test_inno_script.py` → **All checks passed!**

### Static contract, cleanup, and workload

- S10 static contract recheck is green: all 9 `tests/test_inno_script.py` tests passed.
- Exact ignored path is absent; `build/lib/yasb_limitora` remains, with no other build artifact deleted.
- No attributable `pytest`, Python, Inno, setup, or YASB processes remain after verification.
- `tasks.md` S10 is checked complete; remaining S03, S04a/G2a/S04c, S05–S09, S11–S16, and G2b are unchanged.
- Independent candidate-view recount: **312/350 authored changed lines** (119 installer + 116 tests + 2 task-checkbox diff + 75 current S10 progress lines). The earlier **323/350** figure cumulatively counted replaced progress-record lines and is not the authoritative net review diff.
- Workload boundary remains one S10 feature-branch-chain slice; no later slice started. Strict-TDD closeout is N/A for this authorized evidence remediation.

## S03 — Immutable candidate manifest, hashes, and build provenance records: COMPLETE (final-net remediated)

Date: 2026-09-06 (local); same-day REFACTOR-only final-net remediation. Worker: delegated apply executor. Standalone S03 slice only; no commit/tag/push/PR/promotion/publication; no later slice started.

- Delivered: `scripts/make_release_manifest.py` — release-manifest/v1 `rc-manifest.json` generator/validator + read-only `--verify` + bounded CLI (exit 0/1/2): deterministic sorted keys, exact SHA-256/size per artifact, final `0.2.0` identity, source_commit/source_date_epoch, python/pyinstaller/limitora tool identity, bound `sbom.cdx.json` and `_internal/build-info.json` digests, coreutils `SHA256SUMS.txt`; fail-closed on gate/approval/evidence/custody/acceptance/run-id/status/publication fields, secret-bearing keys, absolute/UNC/POSIX-root/`..` names, unknown/missing root keys, non-final `-rc` versions, duplicate artifacts, overwriting existing records, tampered bytes, and malformed manifests — plus focused contract suite `tests/test_release_manifest.py` (35 tests).
- TDD evidence retained from the original cycle: RED (suite authored before implementation; all errored on the missing module) → GREEN (focused suite passing; one GREEN fix added `publication` to forbidden-key parts) → TRIANGULATE (three mutants killed: constant digest, overwrite-allowed, `_FORBIDDEN_KEY_PARTS=()`; byte-identical restore) → REFACTOR. This remediation is REFACTOR-only: duplicated test setup consolidated into shared fixtures and data-driven parametrization (forbidden/secret-field, absolute/UNC/`..`-name, and root-key validation cases folded into one parametrized table; tamper cases packed); every behavioral case preserved — 35 tests before and after — with no production validation weakened and no code golf.
- Final-net accounting vs pre-S03 tree `6b77a29c`: **334 changed lines** (script 175 + tests 146 + tasks.md checkbox diff 2 + this section incl. separator 11), within the ≤350 final-net cap. Supersedes the stale "440 authored lines" claim and the 403-line interim final-net (prior corrective reduction took 440 → 403; this remediation takes 403 → 334).
- Corrective-attempt delta vs begin tree `3d26ae80`: **165 changed lines** (tests 79 + script 33 + this section replacement 53), within the ≤200 native corrective cap.
- Remediation verification: focused `python -m pytest -q --strict-markers tests/test_release_manifest.py` → **35 passed**; `python -m ruff check scripts/make_release_manifest.py tests/test_release_manifest.py` → clean. Independent full-suite and native verification are delegated separately by the parent.
- Rollback boundary: delete the two S03 files and revert this section; all generated records live only in disposable tmp dirs. Remaining work per `tasks.md`: S04a → G2a → S04c, S05–S09, S11–S16, G2b; S12 consumes this generator.
