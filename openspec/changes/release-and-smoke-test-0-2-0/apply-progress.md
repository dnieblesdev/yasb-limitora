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

## S04a — Read-only YASB discovery and spike harness: COMPLETE
> Redaction: `<user-home>` replaces the observed Windows profile root; evidence semantics are unchanged.

- Strict TDD: post-timeout RED replay against reset `c6225c7d` produced **1 failed, 19 passed** (`test_existing_unsafe_components_are_rejected`); GREEN current candidate produced **20 passed**; TRIANGULATE substring-process mutant produced **1 failed, 19 passed** (`test_exact_names_only[entries0-running-pids0]`); REFACTOR consolidated the same config, metadata, evidence, exact-process, no-control, and harness cases without weakening their assertions. The replay is explicitly reconstruction evidence, not a claim that the timed-out worker returned its original RED result.
- Verification: focused **20 passed**; Ruff clean; full suite **705 passed, 3 skipped**; native Windows proof **11 passed**; PowerShell parser and static M1–M8/§6.2 contract passed; protected examples unchanged; no attributable process remained.
- Accounting: final pre-S04a baseline `c0204c6b` = **396/400** lines (182 discovery + 113 harness + 71 discovery tests + 30 process tests); remediation baseline `c6225c7d` = **462/650** diff lines. G2a remains truthfully `unrun (external)`; no invocation mechanism was selected/adopted and S04c was not started.

## G2a — real release-target YASB feasibility/selection checkpoint: `unrun (external)` — INTERACTION REQUIRED

Date: 2026-09-06 (local). Worker: delegated apply executor. Work unit: G2a external checkpoint only, explicitly authorized by the user to run now. Strict TDD: **N/A** — external verification gate. No production code, test, harness, shipped example, YASB YAML/CSS, PATH, or persisted environment variable was created, modified, or deleted. No process was installed, launched, terminated, suspended, restarted, or otherwise controlled. No commit, tag, build, installer, or PR action. **S04c and all later slices were NOT started.**

### Verdict

G2a = **`unrun (external)`**, truthfully. The design §6.2 mechanism executions (M1–M8) against the real release-target YASB did **not** occur, because they require a manual native YASB widget run and UI observation (exact test-YAML `run_cmd`/`use_shell` quote, cropped/redacted widget screenshot, real spawned-child `argv`/process ancestry, stdout/exit from a real YASB spawn). This delegated executor is prohibited from launching/controlling YASB, from editing its config to load a test widget, and from manual UI observation — the exact stop condition. No mechanism is selected. Per the fail-closed rule (design §6.3), G2a `unrun` blocks S04c and leaves publication blocked.

### Environment discovery (read-only)

- Produced with S04a `src/yasb_limitora/discovery.py` `discover(os.environ)` plus read-only registry/version/PATH inspection.
- Outcome `detected`; install evidence `registry:HKLM:YASB Reborn@`, `directory:C:\Program Files\YASB`.
- Release-target YASB version **`2.0.6`** (`yasb.exe` FileVersion `2.0.6.0`) at **`C:\Program Files\YASB`** (install path contains a space — the spaced-path machine class G2a must prove).
- Config home `resolved`/safe: `<user-home>\.config\yasb` (`YASB_CONFIG_HOME` unset); `.env` `present`; `config.yaml` present.
- YASB process status **`clear`** — no `yasb.exe`/`yasb-limitora.exe` running (a running YASB could only be observed read-only; none is running).

### Integrity baseline (read-only; `before` half of §6.2 rule 8)

- Frozen candidate (S02b target) `build/frozen/dist/yasb-limitora/yasb-limitora.exe` SHA-256 `93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0`; `_internal/build-info.json` `f783582a…` (version `0.2.0`, PyInstaller `6.22.2`, Python `3.13.5`, source_commit `528313c9…`).
- S04a harness `scripts/spacepath_spike.ps1` revision SHA-256 `3c24332abc75751ad63a38062acc666a491668df7033ec4c410d7f7a5fcef853` (unchanged).
- YASB `yasb.exe` `28b5fe3d…`; `config.yaml` `728af2dc…`; `.env` `3bdaf891…` (hashed only; contents never read — secret-bearing; both unmodified).
- Persisted PATH: Machine `REG_EXPAND_SZ` len 957, User `REG_EXPAND_SZ` len 1960, combined SHA-256 `29f76483d0601f0653cf6f06c25c68f19e25966430ab8b587a8ae0d4afca1a54`; candidate dir **not** on PATH (confirms the no-PATH requirement is real). No PATH change made.

### Harness readiness and why it was not run as a substitute

- The S04a harness is present/unmodified and is read-only/disposable by design; it records `yaml_quote`, `screenshot`, `child_cmdline`, and `process_ancestry` as `pending-manual`, so it **cannot** itself satisfy §6.2 rules 2/3/4/7. Its `Invoke-LaunchProbe` only emulates the `use_shell:false` first-token parse by directly spawning the candidate — **not** a real YASB widget spawn — and would not produce real child-argv/ancestry or widget-rendering evidence. Running it alone would not complete G2a and would risk being misread as partial completion, so it was not executed. Disposable/prototype M3/M6/M8 arrangements must be built by the external run outside the repository and YASB config; none were created here.

### M1–M8 result summary

- Every mechanism and every §6.2 field is `unrun` (no widget render, no child argv/ancestry, no stdout/exit from a real YASB run). M7 remains diagnostic-only and never selectable. Full table recorded in the evidence file.
- Selected mechanism: **none** (selection requires complete execution evidence proving feasibility with PATH unchanged and `use_shell:false`).
- Bounded machine-class behavior: **not established** (no execution). The resolved program dir may contain a space (`C:\Program Files\…`), so a space-free-only M3 result could not cover the spaced-path class.

### Cleanup / process evidence

- No disposable arrangement created (nothing to clean up); no process spawned/controlled; YASB probe after discovery `clear` (unchanged); PATH combined digest `29f76483…` unchanged; YASB `config.yaml`/`.env` bytes unmodified. Secret-scan: only path strings, versions, and SHA-256 digests are recorded; `.env` never read as text.

### Interaction required — smallest exact user action

A human operator with native GUI access must perform the external manual G2a run recorded in §10 of `docs/release/0.2.0/evidence/spacepath-spike.md`: (1) re-confirm target/version and the integrity/PATH baselines above; (2) build disposable/prototype M3/M6/M8 (and M4/M5/M7) arrangements outside the repository and YASB config, pointing at the frozen candidate; (3) load a disposable test widget (separate `YASB_CONFIG_HOME`, never the shipped config/CSS) invoking the candidate for M1–M8 with the exact §6.1 `run_cmd`/`use_shell`; (4) manually open YASB and capture every §6.2 field per mechanism (YAML quote, cropped/redacted screenshot, child argv with `argv[0]` = intended path and no extra tokens, ancestry with no `cmd`/`powershell`/`conhost` for a pass, selector-free JSON stdout with no root `version`, contract exit code, PATH unchanged before/after); (5) select exactly one feasible M3/M6/M8 only if complete evidence proves it, else record `fail`/`unrun` truthfully (M7 never selectable); (6) redact, retain, clean up all disposables, leave PATH/YASB config/shipped examples/production code/tests unmodified, and close YASB manually.

### Files changed (evidence/state only)

- `docs/release/0.2.0/evidence/spacepath-spike.md` (new G2a `unrun (external)` evidence record).
- `openspec/changes/release-and-smoke-test-0-2-0/tasks.md` (G2a status note; checkbox remains unchecked).
- `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md` (this section).

### Remaining tasks

- G2a remains `unrun (external)` pending the manual native run. S04c, S05–S16, and G2b remain blocked/not started per `tasks.md`. This unit does not start any later slice or adopt any mechanism.

### Workload / PR boundary

- One bounded external-gate evidence unit. Durable authored changes are limited to the evidence file, the tasks.md status note, and this cumulative progress entry; all remain well below the 400-line review budget. No adoption, candidate, or publication artifact was created.

### G2a prep update (2026-09-07): disposable manual-test environment prepared; config schema truthfully blocked — still `unrun (external)`

The user chose `Preparar prueba manual` and authorized preparing the disposable/prototype environment. A uniquely named root was created under `%TEMP%` only (`<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14`), outside the repository and the real YASB config home. No YASB process was launched/terminated/restarted/controlled; the real `config.yaml`, `.env`, CSS, PATH, shipped examples, production, tests, and installer were not read or modified. Only frozen-executable bytes were copied and read-only capture helpers created.

- **Arrangements (full onedir, 70 files each; exe SHA-256 `93db5fbd…` byte-identical to source):** M3 space-free `arrangements\m3-spacefree\bundle`; M4/M5/M6 spaced `arrangements\m4 m5 m6 spaced bundle\bundle`; M8 space-free launcher `arrangements\m8-launcher-spacefree\bundle`. M1/M2 need no arrangement (bare name; candidate not on PATH → M2 expected fail). M7 reuses the spaced bundle with `use_shell:true` (diagnostic).
- **M6 finding:** 8.3 short-name generation is enabled on the volume; the spaced bundle resolves to a space-free short path (`...\YASB-G~1\ARRANG~1\M4M5M6~1\bundle\YASB-L~1.EXE`, `spaced_short_has_space=false`), so M6 is prototypeable here (real-YASB spawn still must be re-observed). Recorded in `evidence\shortpath-and-path.json`.
- **Read-only helpers (validated):** `capture\capture-path.ps1` (`f73183e2…`), `capture\capture-child.ps1` (`180d63d2…`; CIM ancestry/argv, dry-run reported `NO_TARGET_RUNNING`, never controls a process), `capture\probe-shortpath-and-path.ps1` (`ef3de4a5…`).
- **PATH unchanged:** combined SHA-256 `3736ac1a…` identical `before-prep-complete` and `after-prep`; candidate not on PATH. Post-prep YASB `clear`, `yasb-limitora` process count `0`. (Canonical expanded/UTF-16 digest differs from the raw-registry UTF-8 `29f76483…` in §2; same unchanged PATH — manual run must compare like-for-like.)
- **Truthful blocker:** the disposable `config-home\` is intentionally empty. A valid YASB 2.0.6 custom-widget `config.yaml` cannot be fabricated from allowed sources (real config/shipped example/tests protected from reading; YASB ships no loose schema — compiled into `library.zip`, pydantic-validated; design grants only `run_cmd`/`use_shell`). Guessing would risk an invalid config that YASB rejects (spoiling the run) and would violate design §6.1's "re-observe, don't assume" rule. Per the stop-truthfully instruction, this element is left unprepared. Smallest unblock: read-only access to the project's own `examples/customwidget/customwidget.yaml` (+ optionally `tests/test_customwidget_examples.py`) as the authoritative schema, or the human drops a valid disposable `config.yaml` into `config-home\`.
- **Files changed (evidence/state only):** `docs/release/0.2.0/evidence/spacepath-spike.md` (§11 prep record), `tasks.md` (G2a prep note; checkbox unchecked), this section. No production/test/harness/example change; verdict stays `unrun (external)`; S04c and all later slices remain not started.
- **Cleanup boundary:** delete `%TEMP%\yasb-g2a-20260907-020324-0e776d14` and marker `%TEMP%\yasb-g2a-20260907-020324-0e776d14.path` only; nothing written under the repo, real YASB config home, PATH, or any protected surface.

### G2a evidence completion attempt (2026-09-07, second turn): manual run recorded, complementary direct runs executed — verdict `fail (selection evidence incomplete)`; checkbox remains unchecked

The user performed the manual native YASB run and supplied the widget screenshot; this executor
recorded it, ran the authorized complementary direct M3/M6/M8 executions, and assessed §6.2
completeness. No YASB process was launched/stopped/restarted/controlled (a pre-existing session-2
YASB, pid 6708, was observed read-only only). No adoption, no S04c, no tasks.md checkbox change.

- **Screenshot retained:** `docs/release/0.2.0/evidence/spacepath-spike-widget.png` (copy of
  `<user-home>\OneDrive\Documentos\ShareX\Screenshots\2026-09\explorer_nrak6Lxj9b.png`, mtime
  16:50), SHA-256 `9aeb22b54a49996819f01039efcf92ace5aa1890c5004cfc415bab0fc05a5e3a`. Exact visual
  interpretation recorded in spike §12.1: M1/M2/M3/M6/M8 `Quota not run`; M4 slot bare `Loading...`
  (no prefix); M5 `Quota 89% remaining: state=available; freshness=fresh`; M7 prefix + literal
  `{data[providers][0][compact_text]}`.
- **Session facts:** session 1 (03:00:44–03:16:40) produced the CIM/child captures
  (`capture\live-g2a-cim-poll.txt`, `capture\live-g2a-existing-helper-poll.txt`,
  `capture\post-poll-state-and-hashes.txt`); session 2 (16:49:05→) produced the screenshot with **no
  capture running** → render↔spawn simultaneity is absent (recorded caveat).
- **Session-1 spawn evidence:** direct `yasb.exe`→child, no shell between YASB and child: M3 exe
  (pids 38028/12452), M8 exe (37848/41008), quoted-spaced pair (29392/42668, **unattributable among
  M4/M5/M7**), bare name → unrelated pyenv `yasb-limitora` (M1/M2 controls; wrong binary, not the
  frozen candidate). Never observed: unquoted-spaced (M5) child, 8.3 short-path (M6) child,
  `cmd.exe`-parented child (M7). M5 rendered a quota snapshot with no captured spawn (anomaly
  recorded, unusable as rule-4 evidence).
- **Complementary direct runs (authorized, labeled non-YASB):** harness
  `capture\direct-run-m3m6m8.py` (SHA-256 `57e0324b…`), each of M3/M6/M8 `run_cmd` executed exactly
  once, `argv=[exe]`, `shell=False`, 30 s bound: all exit 0, ~0.43 s, stdout SHA-256 `0ed3a41c…`
  (2117 B), stderr empty, 0 redaction hits, JSON ok with root keys
  `execution_error, execution_state, providers`, **no root `version`**, `providers[0].outcome=
  snapshot`, `compact_text="Quota 89% remaining; state=available; freshness=fresh"`,
  `execution_state=partial`; exe SHA-256 `93db5fbd…` before each run; no process residue.
- **§6.2 completeness (spike §12.5):** M5 and M6 lack rule-4 child argv/ancestry; M4/M7 attribution
  ambiguous; M4/M7 renders absent; M3/M8 strong but cross-session-bound. Selection evidence is
  incomplete → per design §6.2/§6.3 **G2a = `fail (selection evidence incomplete)`**, not pass and
  not unrun. **Selected mechanism: none.** Machine-class note: this machine's profile path is
  space-free, so M3/M8 cover only the space-free class; the spaced class (target of
  `yasb-spaced-path`) rests on the incomplete M4/M5/M6 records; §6.3 forbids M3-only selection as
  spaced coverage, and M8 is not proven against the spaced-install class, so no preference-based
  selection was made.
- **Fail-closed consequences:** S04c never starts; no mechanism adopted; publication remains
  blocked; `tasks.md` G2a checkbox **unchanged (unchecked)**; no installer/candidate/ledger claim.
- **Single smallest manual rerun returned (spike §12.7):** one captured session — start both capture
  helpers, launch YASB with the same disposable config (`e105cd7d…`), wait ≥2 widget cycles (~5 min)
  with the bar visible, screenshot inside the capture window, exit from tray, stop captures. Yields
  distinct M5/M6 child argv/ancestry (or bound proof-of-absence), M4-vs-M7 disambiguation
  (`cmd.exe` ancestry presence/absence), and a simultaneous screenshot.
- **Integrity/cleanup:** PATH canonical digest `3736ac1a…` identical pre/post (22:01:03Z/22:01:41Z),
  `contains_yasb_limitora=False`; real `config.yaml` `728af2dc…` and `.env` `3bdaf891…` unchanged;
  disposable config `e105cd7d…`/`styles.css` `a15c8375…` unchanged; frozen candidate `93db5fbd…`
  unchanged; S04a harness `3c24332a…` unchanged; no `yasb-limitora` residue; new external files
  confined to `capture\`; secret-scan 0 hits (`.env` hashed only).
- **Files changed:** `docs/release/0.2.0/evidence/spacepath-spike-widget.png` (new binary),
  `docs/release/0.2.0/evidence/spacepath-spike.md` (§12 + header verdict update), this file.
  `tasks.md` untouched.
- **Workload / PR boundary:** evidence-only unit; authored doc lines well under the 400-line budget;
  no production/test/example/installer change; no commit made.

## G2a remediation preparation (round 3) — BLOCKED: interaction_required (2026-09-07)

- Authorized scope: prepare ONE new manual G2a session in the existing disposable root
  `<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14` to remedy parent-supplied
  evidence identity `sha256:0e4af39a…` (M1–M8 distinct prototype paths, disposable config with
  `run_once:true` where possible, capture monitor, integrity helpers, static validation only;
  no launch/stop/restart/control of YASB or any candidate).
- Read-only process gate result at 2026-09-07T22:15:46Z: **YASB session 2 from spike §12.1 is still
  running** — PID 6708, `C:\Program Files\YASB\yasb.exe`, parent 23008, started 16:49:05.
  No `yasb-limitora.exe` process found.
- Per the gate: preparation stopped before any mutation. No prototypes, onedir copies, disposable
  config/CSS, capture monitor, or integrity helpers were created or modified; disposable
  `config-home\`, `arrangements\`, `capture\` untouched. Only write under temp: read-only inspection
  script `<root>\prep-r3\proccheck.ps1` (disposable exception surface). No real config/.env/CSS/PATH
  read or mutated.
- Files changed: `docs/release/0.2.0/evidence/spacepath-spike.md` (§13 blocked-preparation record,
  +31 lines), this file. `tasks.md` untouched — G2a checkbox remains unchecked; verdict remains
  `fail (selection evidence incomplete)`; S04c and publication remain blocked. No screenshot,
  ancestry, or capture output claimed.
- Human action required: manually close YASB (PID 6708, tray → exit), verify no YASB process remains,
  then re-authorize the remediation preparation.
- Workload / PR boundary: evidence-only record (~43 authored lines total); no production/test/
  example/installer change; no commit made.

## G2a remediation preparation (round 3) — PREPARED, awaiting one manual session (2026-09-07)

- Process gate recheck: user manually closed YASB (PID 6708 gone); strict read-only CIM recheck
  returned `NO_YASB_PROCESSES` (zero `yasb.exe` / `yasb-limitora*`) before any mutation.
- Built inside the existing disposable root (round-2 evidence untouched):
  - `arrangements-r3\`: six DISTINCT full onedir copies (70 files each; every exe = frozen
    `93db5fbd…`; full-tree hash equality with source verified) — `m3-spacefree`, `m4 quoted spaced`,
    `m5 unquoted spaced`, `m6 shortpath spaced`, `m7 shell spaced`, `m8-launcher-spacefree`;
    executable basename `yasb-limitora.exe` everywhere. M4 vs M7 no longer share command/path; M5 has
    its own spaced path; M6 uses verified unique space-free 8.3 short path
    `…\YASB-G~1\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe` (6/6 short paths distinct, round-trip
    hash matches); M3/M8 separate space-free paths.
  - `config-home-r3\config.yaml` (`bc43b5a9…`, 5796 B): eight identifiable widgets, exact M1–M8
    semantics, `use_shell:false` except M7 `true`, `run_once:true` (monitor-first sees every initial
    spawn), M1/M2 identical bare control labeled `…-PYENV-NEVERSELECT` (resolves to unrelated pyenv
    shim/exe `76fb2532…`; never selectable). `styles.css` (`c829271b…`, 395 B): legible 11px labels,
    bounded min/max widths and spacing.
  - `capture\r3-monitor.ps1` (`d3c89989…`): read-only CIM `Win32_ProcessStartTrace`/`StopTrace`
    events (stop carries ExitStatus) + 300 ms WQL polling backstop; records timestamp, PID, command
    line, exe path, direct parent, ancestry snapshot, shell-intermediary flag, exit status per
    distinct command; auto-exits after 10-min bounded horizon; runs integrity before/after
    (screenshot-window binding); never signals/controls processes.
  - `capture\r3-integrity.ps1` (`2ff2721d…`): PATH canonical digest + contains-flag, real
    config/.env SHA-256 (hashes only, never read), disposable config/CSS hashes, six frozen-target
    hashes + counts + M6 short-path round-trip, bare-control resolution, screenshot hash/mtime vs
    monitor window, process residue. Dry-run verified: PATH `3736ac1a…` unchanged, real config
    `728af2dc…`, `.env` `3bdaf891…`, residue 0 (`capture\r3\integrity-before.txt`).
- Static validation without launching YASB/candidate: PowerShell `Parser::ParseFile` 0 errors on
  both scripts; `yaml.safe_load` + semantic assertions (widget set/order, use_shell map, run_once,
  label distinctness, M4≠M7, M5 unique spaced unquoted, M6 short-path uniqueness/collision checks,
  M3/M8 space-free distinct, basename checks) and CSS brace/selector/width checks → 0 fails
  (`evidence\r3-static-validation.json`).
- Exact 5-step human procedure recorded in spike §14.4 (monitor first → launch YASB with
  `YASB_CONFIG_HOME=<root>\config-home-r3` → screenshot to `capture\r3\screenshot-r3.png` when bar
  settles → manual tray exit → wait for `MONITOR_COMPLETE`); expected outputs listed in §14.4.
- Files changed: `docs/release/0.2.0/evidence/spacepath-spike.md` (§14, +96 lines), this file.
  `tasks.md` untouched — G2a checkbox UNCHECKED; verdict remains
  `fail (selection evidence incomplete)`; no screenshot/ancestry/capture claimed; S04c and
  publication remain blocked until the manual rerun is recorded.
- Workload / PR boundary: evidence-only unit (~135 authored lines this round); no production/test/
  example/installer/PATH/config change; no commit made. Cleanup boundary: delete `<root>` + marker
  `%TEMP%\yasb-g2a-20260907-020324-0e776d14.path` only.

## G2a monitor defect correction (round 3, second bounded attempt) — PREPARED, awaiting one manual session (2026-09-07)

- Scope honored: fixed ONLY the disposable capture monitor defect before any manual YASB run; no
  YASB/candidate launch, stop, or control; edits confined to `<root>\capture\r3-monitor.ps1`,
  `<root>\capture\r3\` (clearing failed partial + dry-run outputs only), `<root>\prep-r3\validate-r3b.ps1`
  (new read-only validator), spike evidence §15, and this file. `<root>` =
  `<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14`.
- Defect: previous monitor revision `d3c89989…` failed before `MONITOR_ARMED` —
  `Register-CimIndicationEvent` (Win32_ProcessStartTrace) returned WBEM_E_CALL_CANCELLED at ~22:38Z;
  only partial r3 outputs existed (integrity-before block, unclosed monitor-window).
- Correction: rewrote `r3-monitor.ps1` as pure bounded polling — SHA-256
  `b4124958b5dfb2719b454ef8aa3d4ad922f2053b469f54ab61542c59c885396e`. No Register-*Event / WMI
  indication subscription (scan: comment-only matches). Full-table `Get-CimInstance Win32_Process`
  poll at default 200 ms (`-PollMs` 100–300), horizon ≤10 min (`-HorizonMinutes` 1–10), grace
  15 s; detects YASB roots + any-depth descendants (self/own-ancestry excluded); retains first
  observation per PID (`poll_new`: ts, PID/PPID/name, commandline, exe path, direct parent,
  child→ancestor chain, shell-intermediary flag, is_yasb_root); disappearances as `poll_gone`
  with `exit_status:null` + `exit_status_unavailable_from_polling`; early stop only after YASB
  root observed then gone + grace; outer try/finally ALWAYS closes window, runs integrity-after,
  and writes summary incl. failure state; `MONITOR_ARMED` only after setup + one successful probe
  query; never signals/controls a process.
- Validation without YASB/candidate: `Parser::ParseFile` 0 errors; read-only gate
  `NO_YASB_PROCESSES`; bounded dry run `-HorizonMinutes 1` printed
  `MONITOR_ARMED horizon_minutes=1 poll_ms=200 grace_seconds=15 out_dir=<root>\capture\r3` then
  `MONITOR_COMPLETE` `status=completed` `failure=none`, closed window 22:49:44Z→22:50:44Z,
  `poll_records=0`, `yasb_root_observed=False`, `early_exit=none (full bounded horizon)`,
  `integrity_after=written`. Dry-run outputs + failed partials cleared: `capture\r3\` is EMPTY, so
  the real run gets a clean uniquely identified capture set. §14.1/§14.2 arrangements,
  `config-home-r3`, and `r3-integrity.ps1` (`2ff2721d…`) unchanged and statically valid.
- Authoritative human procedure now spike §15.4 (monitor first → YASB with
  `YASB_CONFIG_HOME=<root>\config-home-r3` → screenshot to `capture\r3\screenshot-r3.png` → manual
  tray exit → early-exit ~15 s after YASB gone or 10-min horizon). Expected outputs:
  monitor-window.txt, monitor-poll.jsonl, monitor-summary.txt, integrity-before/after.txt,
  screenshot-r3.png; NO monitor-events-*.jsonl; exit statuses NOT claimed from polling.
- Files changed: `docs/release/0.2.0/evidence/spacepath-spike.md` (§15 + superseded notes on
  §14.3/§14.4, ~75 authored lines), this file, external `<root>\capture\r3-monitor.ps1`,
  `<root>\prep-r3\validate-r3b.ps1`. `tasks.md` untouched — G2a checkbox UNCHECKED; verdict
  remains `fail (selection evidence incomplete)`; S04c and publication remain blocked until the
  manual rerun is recorded and evaluated.
- Workload / PR boundary: evidence-only unit within the remaining round-3 budget; no
  production/test/example/installer/PATH/config change; no commit made. Cleanup boundary
  unchanged: delete `<root>` + marker `%TEMP%\yasb-g2a-20260907-020324-0e776d14.path` only.

## G2a captured remediation session — verdict `pass (feasibility/selection only)`, M6 selected (2026-09-07)

- Human ran the §15.4 procedure once; executor performed read-only inspection, interpretation,
  and durable recording only. No process was run, stopped, or controlled by the executor; no
  temp/config/PATH/example/code/test/installer surface was altered.
- Capture set (evidence revision candidate `g2a-evidence-rev-r3-session-1`): monitor
  `b4124958…` summary `status=completed failure=none`, window 22:58:39.9611646Z–23:01:26.0009352Z,
  `poll_records=120` (60 poll_new/60 poll_gone), `distinct_related_pids=56`,
  `yasb_root_observed=True`, early exit after YASB gone + 15 s grace; poll log SHA-256
  `6705793c0e9c9072457122de71766e721ef61a4bad1f356e28e807f57e8be72c`; screenshot SHA-256
  `baa7e2f8a405353b052aefb1765a6efd5982cad19de8e53bbbb497b0155a2744` (96766 B, mtime
  23:00:57Z, `inside_monitor_window=True`), copied byte-identical to
  `docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png` (earlier cross-session screenshot
  untouched); integrity before/after: PATH `3736ac1a…` equal + `contains_yasb_limitora=False`,
  real config `728af2dc…`/.env `3bdaf891…` unchanged, disposable config `bc43b5a9…` exact
  binding, six frozen exes `93db5fbd…` + M6 short-path round-trip True, residue 0 after;
  S04a harness `3c24332a…` re-verified unchanged; secret scan 0 hits.
- §6.2 table (spike §16.2): M1/M2 bare controls → unrelated pyenv exe `76fb2532…`, never
  selectable (M1 snapshot render, M2 not_run); M3 spawned (21452/36592) snapshot render,
  feasible space-free class; M4 quoted spaced → NO spawn, widget `Loading…` (fail as expected);
  M5 unquoted spaced → spawned with quoted single-token argv (15056/33060), recorded, not
  selectable, contradicts naive split(" ") model; M6 short path → spawned (23596/34176) exact
  single-token argv, shell-free `yasb-limitora.exe ← yasb.exe` segment, widget rendered live
  parsed JSON (`Quota not run` = designed guard-lease `not_run` under the 16-spawn burst, not
  empty/error); M7 shell → NO spawn and `cmd.exe` count 0, raw template render, diagnostic fail;
  M8 spawned (13484/25796) feasible, not selected. All direct children of YASB PID 2480 carry
  exactly one argv token; `--multiprocessing-fork` grandchildren are internal PyInstaller
  respawns, excluded from rule 4. Every `poll_gone` has `exit_status:null` +
  `exit_status_unavailable_from_polling`; no exit code invented; rule-5/6 stdout/exit evidence
  from authorized §12 direct runs (`0ed3a41c…`, contract keys, no root version, exit 0).
- Selection: exactly one — **M6** (8.3 short-path alias, `use_shell:false`, no PATH), bounded
  machine-class: SF + SP-83 proven; SP-no83 unproven → installer §6.3(a)–(d) skip+inform and
  G2b block. M3 excluded by §6.3 spaced-coverage rule; M8 not selected (no guaranteed space-free
  writable dir, extra launcher custody).
- Verdict: G2a `pass (feasibility/selection only)`; `tasks.md` G2a checkbox CHECKED with status
  note; §12 simultaneity gap identity `sha256:0e4af39a58c510dd073b40a4a4dbf9462647633e825efc7b7bfcf7c96e3a7cc1`
  named remediated failed evidence. Non-claims preserved (no installer guaranteeability, no S04c
  adoption, no retained-candidate inclusion, no ledger acceptance, no publication pass); S04c
  stays sequenced after S10 static installer path/identity contract; overall G2 closes only via
  G2b against the exact retained candidate.
- Files changed: `docs/release/0.2.0/evidence/spacepath-spike.md` (§16 ~95 lines + header
  verdict), `docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png` (new binary copy),
  `openspec/changes/release-and-smoke-test-0-2-0/tasks.md` (G2a checkbox + status note), this
  file. External: read-only analysis helpers `prep-r3\analyze-poll.py`, `prep-r3\zoom-r3.ps1`,
  `prep-r3\zoom2-r3.ps1` + zoom crops (disposable).
- Workload / PR boundary: evidence-only unit (~140 authored doc lines); no production/test/
  example/installer/PATH/config change; no commit made. Cleanup boundary unchanged: delete
  `<root>` + marker `%TEMP%\yasb-g2a-20260907-020324-0e776d14.path` only.

## G2a bounded exact-M6 evidence remediation — direct run of the EXACT r3 command; verdict stays `pass (feasibility/selection only)`, M6 selected (2026-09-07)

- Maintainer-authorized reset; remediated failed verification
  `sha256:8ad2c24fdab0a9dc9fda638596ce556ada9c1a7b825eacdb1f7ebc261ddf796a`. Rejection cause: §16's
  M6 rule-5/6 evidence cited the §12 complementary direct runs, whose M6 command was the round-2
  short path (`…\ARRANG~1\M4M5M6~1\bundle\YASB-L~1.EXE`), not the exact r3 command the live session
  spawned (`…\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe`). Strict TDD: **N/A** — external evidence
  remediation only; no production/test/harness/example/installer/PATH/real-config change; S04c not
  started; YASB never launched/stopped/controlled (pre- and post-run CIM gates: no
  `yasb.exe`/`yasb-limitora.exe`).
- Executed the exact r3 M6 `run_cmd` quoted from `config-home-r3\config.yaml` (`bc43b5a9…`
  unchanged) **once**, directly: `subprocess.run([exe], shell=False)`, single-token argv, bounded
  30 s timeout, cwd = capture dir, environment inherited unmodified. Ancestry
  `yasb-limitora.exe ← python.exe 3.10.5 ← harness shell` — a direct harness run, **not** a YASB
  spawn; no YASB stdout interception claimed. New external files confined to
  `<root>\capture\exact-m6-r3\`: runner `run-exact-m6.py` (`ce4b5ca8…`), record `exact-m6-r3.json`
  (`e01fa6c2…`), raw/redacted stdout/stderr.
- Captured: exit code **0**; stdout 2124 B `fe609c77cc4ec86a149baa4b8583dc91a6e4b9f0852ee0df0b0b84f46bc8843c`
  (JSON ok; root keys exactly `execution_error/execution_state/providers`; no root `version`;
  0 selector placeholders; `execution_state=partial`; `providers[0]` `outcome=snapshot`,
  `compact_text="Quota 66% remaining; state=available; freshness=fresh"`); stderr empty
  `e3b0c442…`; timestamps `2026-09-07T23:27:11.694248Z`→`23:27:14.091050Z` (2.407 s, no timeout);
  path resolution `GetLongPathNameW(short)` = the exact M6 bundle long path, short path space-free;
  exe identity via short AND long path `93db5fbd…` = frozen S02b candidate (recomputed at source);
  complete onedir binding: 70 files, `_internal\build-info.json` `f783582a…`; PATH canonical digest
  `3736ac1a…` identical before/after, `contains_yasb_limitora=False`; real config `728af2dc…`/`.env`
  `3bdaf891…` hash-checked unchanged (never read); secret scan 0 hits (redaction verified no-op);
  process cleanup: 0 candidate processes before/after, no residue.
- Acceptance evidence now composes **two separate executions, explicitly distinct**: (a) retained r3
  live-window evidence (§16: real YASB spawned the exact M6 command shell-free, single-token
  argv[0], widget rendered live-parsed JSON — rules 1–4/7/8/9) and (b) this §17 exact-command direct
  run (rules 5–6 + identity/path/immutability binding). Neither half claims the other's process.
- Verdict: G2a `pass (feasibility/selection only)` meets design §6.2 for the selected mechanism;
  `tasks.md` G2a checkbox remains **checked** (status note updated). Exactly one M6 selection kept;
  SF + SP-83 proven; SP-no83 unproven (§6.3(a)–(d) skip+inform, blocks G2b for that class);
  §12 superseded for M6 only. New distinct evidence revision candidate:
  **`g2a-evidence-rev-r3-session-1-exactm6-1`** (§16 bindings + §17 record). Non-claims preserved:
  no installer guaranteeability, no S04c adoption, no retained-candidate inclusion, no ledger
  acceptance, no publication pass; overall G2 closes only via G2b.
- Aggregate manifest `g2a-aggregate-manifest.json` (`08655ec0…`) and validation receipt bind the
  exact M6 evidence, failed lineage `aeb474c0…`, and 70-file tree digest `866cde15…`.
  Contract clarification was exactly 32 diff lines: cumulative correction is **192/200**.
  No commit or S04c start; cleanup remains `<root>` plus its marker only.

## S10 native-review `review-a2c398942b30e071` — bounded correction 2/2: COMPLETE (2026-09-07)

- Findings R4-001 (manual-close gate precedes capture/evacuation) and R3 (bounded rollback cleanup wait): corrected in round 1 — RED 6 failed / 20 passed, GREEN 26 passed, five one-token mutations each killed one guard test, then byte-restored; REFACTOR: none needed after restoration. Their guards re-verified GREEN this round (`tests/test_inno_script.py` → 26 passed).
- Finding R4-002: independent verification `sha256:b5e35a1b…8c47a2` proved handler-only `Exit` in `CurStepChanged(ssPostInstall)` returns from the handler without failing setup. RED: strengthened `test_post_install_cleanup_is_checked_and_failure_preserves_recovery_state` to reject `Exit;` and require fatal `RaiseException` before any snapshot deletion/state clearing → 1 failed (exact assertion observed). GREEN: `Exit` → `RaiseException` in the cleanup-failure branch; `PriorRegistrySnapshot`/`EvacuatedOldDir` preserved for the `DeinitializeSetup` rollback → 26 passed. TRIANGULATE: one-token mutation `RaiseException(…)` → `Exit;` killed the focused test; byte-identical restore hash-verified (`5c7aa4aa…`), 26 passed again.
    - ISCC compile: `Successful compile` → disposable `build/iscc-check/out/yasb-limitora-0.2.0-setup.exe` (never executed; no publication). Accounting: correction 2 = 16 diff lines (iss 5 + tests 5 + record 6); correction 3 = 5 (1 snapshot-preservation test assertion + 4 in-place record rewrites retaining round-1 TDD facts); cumulative 159 + 16 + 5 = 180 ≤ 180. No commit, publication, YASB/process control, or unrelated edit.

## S04c — Bounded post-G2a adoption of the exact-M6 mechanism: COMPLETE (independently verified)

Date: 2026-09-08 (local). Worker: delegated apply executor; final state independently verified.
Delivery: single S04c review unit. No commit, tag, PR, installer execution, publication, or
delivery action occurred. This record does NOT advance S05/S06/S11 or G2b.

### Adoption scope (mechanism M6 only)

- Encodes exactly the G2a-selected **M6** mechanism: 8.3 short-path alias of the spaced install
  path, one literal single-token command, `use_shell:false`; no PATH mutation, no shell, no
  environment-variable/substitution, and no fallback mechanism silently substituted.
- Machine-class semantics: **SF** (space-free) and **SP-83** (spaced, 8.3 alias available)
  resolve to the exact command. **SP-no83** (spaced, no 8.3 alias) is a nonfatal no-command
  outcome: skip writing the integration command and inform the user (skip-and-inform, per G2a
  §6.3(a)–(d)); this contract is recorded for later setup-assist consumption, and that class
  remains unproven pending G2b.
- Shipped example `examples/customwidget/customwidget.yaml` and
  `tests/test_customwidget_examples.py` unchanged (protected example diff verified clean).

### Strict TDD chronology

1. Initial M6 API: RED 16 failed / 15 passed (missing API) → GREEN 31 passed.
2. Path safety: RED 3 failed / 31 deselected → GREEN 34 passed.
3. Alias leaf: RED 3 failed → GREEN focused 6 passed and discovery suite 37 passed.
4. Canonical/existing-ancestor: RED 6 failed → GREEN discovery suite 44 passed.
- TRIANGULATE: prior positive cases, security (unsafe/reparse/traversal) cases, and short-path
  mismatch cases exercised. REFACTOR: none/minimal helper reuse only; focused suites stayed green.
- Honesty note: the historical RED outputs above were retained/reported by the executing workers
  and their numerical chain is coherent; they were NOT independently reproduced here. The final
  GREEN state below WAS independently reproduced.

### Final independent verification

- Focused discovery suite: **44 passed**. Full suite `python -m pytest -q --strict-markers`:
  **741 passed, 3 skipped**. Ruff on touched targets: clean. Protected example diff: clean.
- No candidate-caused blockers found in independent verification.
- Marker technical scope before this concise evidence addition: **201/400** authored lines.
- Final evidence digest:
  `sha256:fa411e3f74de61f968b9566bc3f58e063ab5ee5772f9988689ccf3d172da350c`.

### Gate and delivery state

- Overall **G2 remains blocked**: it closes only via a later candidate-bound **G2b** run against
  the exact retained S04c-integrated setup bytes with immutable `rc-manifest.json` identity.
  No delivery, publication, acceptance ledger, or retained-candidate promotion occurred.

### Workload / PR boundary

- `tasks.md`: S04c checkbox only (+1/−1); S05/S06/S11/G2b untouched. The documentation unit
  added 54 lines and replaced 1 checkbox line (**55 changed lines**), so authoritative S04c
  accounting is **201 technical + 55 documentation = 256/400**. Rollback: revert only the M6
  integration guidance and this record; no fallback mechanism is substituted.

## S05 — Private setup-assist dispatch and nonce-derived temp transport: COMPLETE

Date: 2026-09-08 (local). Worker: delegated apply executor. Delivery: `auto-chain`, `feature-branch-chain`; single S05 review unit. No commit, tag, PR, installer build/execution, publication, install/uninstall, YASB config/PATH/process mutation, or native review; no later slice started.

### Delivered

- `src/yasb_limitora/setup_assist.py` (new; private: no public export, no `__all__`): sentinel `--__yasb-limitora-setup-assist` gated on the per-run `_YASB_SETUP_ASSIST_NONCE` env value; exact `[0-9a-f]{32}` nonce grammar validated before any filesystem access; Local AppData resolved through `SHGetKnownFolderPath`; transport independently derived as `%LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\` from fixed literal segments through a two-input derivation — no request/argv/env-supplied transport or target path is ever accepted; request read bounded to a regular non-reparse ≤64 KiB file with fd-bound fstat recheck; strict request/v1 schema (exact root keys, ≤8 unique operations, path-bearing-key rejection, unknown/duplicate/malformed/undecodable/oversize refusals); result/v1 created exclusively (`O_CREAT|O_EXCL`, ≤64 KiB) and sanitized — status `complete|partial|refused`, fixed per-operation reason codes, discovery facts limited to state strings, no paths, never on stdout; `discover`/`yasb-running` run read-only via S04a discovery; operations owned by S06–S09 refuse nonfatally as `operation-unavailable` so a program transaction can continue.
- `src/yasb_limitora/cli.py` (+4/−0): dispatch immediately after `freeze_support()` with the existing helper sentinel preserved first, before `_config_path`; without the nonce env value the sentinel is unrecognized and falls through to the normal invalid-argv exit 2 (`invocation_invalid` contract intact) touching nothing; public argv surface unchanged.
- New tests: `tests/test_setup_assist_protocol.py` (38 cases: derivation literal/independence/program+state-root separation, nonce grammar, pre-filesystem refusal, no stdout contract, no state creation, transport/request/result defects incl. reparse component, non-regular file, oversize, stale-fs-view TOCTOU race, 15 schema-violation cases with request-byte preservation, nonfatal refusal, pre-existing result never overwritten) and `tests/test_frozen_entry_order.py` (5 cases: platform gate, freeze_support precedence, helper-before-assist, dispatch before `_config_path`, no-nonce fall-through with no mutation, extra-args rejection).

### TDD Cycle Evidence

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED | Both test modules authored before any implementation | `python -m pytest -q tests/test_setup_assist_protocol.py tests/test_frozen_entry_order.py` | 2 collection errors — `No module named 'yasb_limitora.setup_assist'`; failure exactly on the missing module/dispatch |
| GREEN | `setup_assist.py` + 4-line cli dispatch | same focused command | 42 passed |
| TRIANGULATE | Mutants on final bytes: `fullmatch`→`match`; cli `args ==`→`args[:1] ==`; dropped `O_EXCL`. The `O_EXCL` mutant initially SURVIVED (kind precheck masked it), so the stale-fs-view exclusivity test was added; each mutant then killed exactly 1 test; byte-identical restore sha256-verified | focused pytest per mutant + `sha256sum -c` | 1 failed/37 passed; 1 failed/4 passed; 1 failed/37 passed; restore OK → 43 passed |
| REFACTOR | Compacted module/tests to house style; no assertion weakened | focused + full + native + ruff | 43 passed; 784 passed, 3 skipped; 11 passed; ruff clean |

### Verification, boundaries, accounting

- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_protocol.py tests/test_frozen_entry_order.py` → **43 passed**. Full: `python -m pytest -q --strict-markers` → **784 passed, 3 skipped**. Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** (runnable on this Windows host; not `unrun (external)`). `python -m ruff check` clean on all four touched files.
- Boundaries honored: assist creates nothing except `result.json` (nonce directory owned by setup.exe; state/program roots never created — tested); no YASB/PATH/registry mutation; no secret or absolute user path in results; the Inno side must independently derive the same literal in S11; `state-cleanup`/PATH/`.env`/config semantics arrive in S06–S09.
- Accounting: **369 technical** (172 module + 144 protocol tests + 49 entry-order tests + 4 cli diff) + 2 tasks.md + 26 this section = **397/400**. Rollback: delete `setup_assist.py` and both test files and revert the 4 cli lines — the existing helper sentinel order is restored and no user-data mutation surface remains.

### S05 corrective rerun — TOCTOU hardening at request/result I/O boundaries (2026-09-08, local)

**Blocker (independent verification FAILED):** `_components_safe`/`fs.kind` validated the transport path, but `_read_request` and `_write_result` then opened `request.json` / created `result.json` **by pathname**. `O_EXCL` protects only the leaf; a validated nonce directory (or parent) could be swapped to a junction/reparse point between check and I/O, redirecting the read or the exclusive create to an attacker-chosen location.

**Fix (smallest Windows-safe, operation-boundary revalidation — not a second precheck):** after each pathname-based `os.open`, the open handle's true location is resolved with `GetFinalPathNameByHandleW` (`\\?\`-prefixed, all reparse points resolved) via `msvcrt.get_osfhandle`, and compared casefolded against the expected canonical path (`_fd_reached_path`/`_expected_final`/`_handle_final_path`):

- `_read_request`: mismatch after fstat checks → `request-unsafe`; planted bytes behind a substituted parent are never consumed and never reach `_validate_request`.
- `_write_result`: `O_EXCL` create retained; mismatch on the created handle → `_close_and_remove_stray` closes and deletes only the empty remnant this call exclusively created, returns `False` — the attacker directory gains nothing. Post-open binding is race-free: once the handle is open, later parent swaps cannot move it.
- No weakening: `O_EXCL`, nonce grammar, `_canonical_dir`/`_components_safe`, schema/size/path-key checks, no-stdout contract, helper/assist dispatch order, and all 43 prior tests unchanged. Fail-closed on any `GetFinalPathNameByHandleW` failure (None → refuse).

**RED tests (real junctions on this native Windows host, deterministic, both boundaries + direct units):** `SwapFs` fires the attacker swap (`os.rename` nonce dir aside + `_winapi.CreateJunction` to attacker dir, `mklink /J` fallback) exactly at the first `kind()` probe of `request.json` (before request open) or `result.json` (after request read, before result create), with `fs.done`/armed-flag assertions proving the race actually fired:

1. `test_request_open_rejects_nonce_directory_swapped_to_junction_after_validation` — exit 1, no `result.json` through the junction or in the preserved original, attacker dir holds only its planted request (no stray artifacts).
2. `test_result_creation_rejects_nonce_directory_swapped_to_junction_after_request_read` — exit 1, attacker dir ends **empty** (no result, no exclusive-create remnant), original request bytes preserved.
3. `test_read_request_fails_closed_when_parent_is_already_a_junction` — `(None, "request-unsafe")`; planted bytes never returned.
4. `test_write_result_fails_closed_and_removes_stray_when_root_is_a_junction` — `False` and attacker dir empty.

**TDD Cycle Evidence (correction):**

| Phase | Action | Command | Result |
| --- | --- | --- | --- |
| RED | 4 junction-substitution tests authored first (2 mid-run races via `SwapFs`, 2 direct unit boundaries); no implementation change yet | `python -m pytest -q --strict-markers tests/test_setup_assist_protocol.py tests/test_frozen_entry_order.py` | **4 failed, 43 passed** — failures exactly reproduced the blocker: attacker-planted request bytes consumed (`data is None` assertion failed with the planted JSON) and `result.json`/remnant created through the junction (`True is False`, non-empty attacker dir) |
| GREEN | `_expected_final`/`_handle_final_path`/`_fd_reached_path`/`_close_and_remove_stray` added; guards inserted in `_read_request` (post-fstat) and `_write_result` (post-create, pre-`fdopen`) | same focused command | **47 passed** (one interim test-harness defect — `-orig` dir located under `tmp_path` instead of `root.parent` — fixed in the test, never in the guard) |
| TRIANGULATE | Mutants: M1 drop read-side guard → 1 failed/41; M2 drop write-side guard → 3 failed/39; M3 `_fd_reached_path`→`True` → 4 failed/38; M4 drop stray `os.remove` → 3 failed/39; byte-identical restore after each | focused pytest per mutant + `sha256sum -c` | every mutant killed only by the new race tests; restore **OK** |
| REFACTOR | `_la` unused-unpack cleanup for ruff RUF059; no assertion or guard weakened | focused + full + native + ruff | **47 passed**; full `python -m pytest -q --strict-markers` → **788 passed, 3 skipped**; native `tests/test_windows_native_proof.py` → **11 passed**; `python -m ruff check` → **All checks passed** on both touched files |

**Verification, boundaries, correction accounting:**

- Edit surfaces honored exactly: `src/yasb_limitora/setup_assist.py` (172→216 lines, +44), `tests/test_setup_assist_protocol.py` (144→241, +97), this file. Everything else read-only; no commit, review, delivery, installer, publication, real YASB/PATH/config/registry mutation, or later slice. All substitutions occurred only inside disposable pytest `tmp_path` dirs; junctions removed by pytest cleanup.
- Native-Windows proof passed where runnable (junction races executed for real on this host, not simulated/mocked FS kinds); non-nt hosts skip the 4 junction tests via `needs_nt` while the guards fail closed (`_handle_final_path` returns None off-Windows).
- Correction accounting: **141 technical** (44 module + 97 tests) + this section ≈ **176/400** — bounded and reviewable as a single corrective unit on top of the settled S05 unit (397/400), which the parent may aggregate or review separately per its settlement authority.
- S05 checkbox in `tasks.md` remains `[x]`; this rerun closes the verification blocker without re-opening slice state. Gate order untouched: G2b/S06+ remain blocked as before.
- Rollback boundary: revert the 4 new helpers + 2 guard insertions in `setup_assist.py` and delete the 4 new tests + helpers section in the protocol test file; prior S05 bytes are reconstructible from the sha256-verified pre-mutant restore point.

## S06 — Consented, byte-preserving YASB `.env` assistance: COMPLETE

Delivery: `auto-chain`, `feature-branch-chain`; standalone S06 only. No commit, installer, real YASB/PATH/config mutation, or later slice.

### Completed tasks

- [x] Explicit-consent-only `env-block-apply` choice, using S04c's M6 resolved no-PATH invocation only.
- [x] Comment-only, marker-delimited `.env` transaction with UTF-8/BOM/dominant-newline and unrelated-byte preservation, idempotence, atomic replacement/verification, state-root backup, and rollback.
- [x] Bounded nonfatal refusals cover unsafe/reparse home or target, malformed markers, undecodable bytes, credential-like rendering, create/replace/verify failure, and rollback failure. YAML/CSS are never opened or written.

### TDD Cycle Evidence

| Phase | Command / action | Result |
| --- | --- | --- |
| RED | Added `tests/test_setup_assist_env_block.py` before implementation | `python -m pytest -q --strict-markers tests/test_setup_assist_env_block.py` → collection failed: `ModuleNotFoundError: yasb_limitora._env_block` |
| GREEN | Added `_env_block` transaction | same command → **9 passed** |
| RED (protocol) | Added explicit-false consent assertion before dispatch/schema change | `python -m pytest -q --strict-markers tests/test_setup_assist_protocol.py::test_env_block_choice_requires_explicit_true_consent` → **1 failed** (`schema-violation`, not consent refusal) |
| GREEN | Narrow `consent: bool` schema for `env-block-apply`; independently derive home/state/M6 invocation | focused required command → **57 passed** |
| TRIANGULATE | Mutated rendered safe text to credential-like `token`; restored byte-for-byte | creator test → **1 failed** (no `.env` promoted); source restored |
| REFACTOR | Added create-failure refusal coverage; Ruff and focused rerun | `python -m ruff check ...`; focused required command → clean; **58 passed** |

### Verification and workload

- Full: `python -m pytest -q --strict-markers` → **799 passed, 3 skipped** (40.50s).
- Files: `src/yasb_limitora/_env_block.py`, `src/yasb_limitora/setup_assist.py`, `tests/test_setup_assist_env_block.py`, `tests/test_setup_assist_protocol.py`, `tasks.md`, and this progress record.
- S06 review boundary: **305 additions+deletions** (129 new helper + 100 new tests + 40 setup-assist + 7 protocol + 2 task + 27 progress); ≤400. Rollback: revert these S06 files; an existing `.env` restores from state-root backup, while a created target is deleted on failure.
- Remaining: S07 onward and external G2b remain untouched.

## S06 reparse/atomicity corrective remediation: COMPLETE

Delivery: parent-acquired `S06-reparse-atomicity-remediation` only. No new attempt was acquired or settled; no commit, installer, real YASB/state/PATH mutation, or later slice.

### Completed corrective work

- Direct `.env` mutation fails closed unless `consent=True` is explicitly supplied; setup-assist passes that literal only after validated request consent.
- `lstat` reparse-point validation covers existing home, `.env` leaf, state root, backup, and temporary components. Real Windows `mklink /J` proofs cover home, target, and state root.
- Reads, backup creation, and temp writes are bound to their opened Windows handles with `GetFinalPathNameByHandleW`; a post-open substitution fails closed before bytes are consumed or written. Replace/verify paths are revalidated; rollback restores through a verified target handle rather than pathname replacement.
- Backup testing enumerates actual backup files and proves retained original bytes.

### TDD Cycle Evidence (corrective)

| Phase | Action / command | Result |
| --- | --- | --- |
| RED | Added default-consent, actual-junction, and opened-handle race tests first | `python -m pytest -q --strict-markers tests/test_setup_assist_env_block.py` → **4 failed, 10 passed**: default mutated; home/state junctions accepted; backup proof did not prove bytes. |
| GREEN | Added reparse/handle guards, safe backup/restore, explicit default, and dispatch integration | same suite → **16 passed**. |
| TRIANGULATE | Injected parent-to-junction swaps immediately after `os.open` and at rollback | focused suite → attacker tmp locations received no original bytes. |
| REFACTOR | Retained byte/BOM/newline/idempotence/marker/M6/no-secret behavior and linted | **16 passed**; Ruff clean. |

### Verification and boundary

- Required focused: `python -m pytest -q --strict-markers tests/test_setup_assist_env_block.py tests/test_setup_assist_protocol.py tests/test_frozen_entry_order.py` → **64 passed**.
- Full: `python -m pytest -q --strict-markers` → **805 passed, 3 skipped**.
- Native Windows: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**; junction/race tests used only `tmp_path` and cleaned artifacts.
- Ruff: `python -m ruff check src/yasb_limitora/_env_block.py src/yasb_limitora/setup_assist.py tests/test_setup_assist_env_block.py tests/test_setup_assist_protocol.py` → **All checks passed**.
- Files changed: `src/yasb_limitora/_env_block.py`, `src/yasb_limitora/setup_assist.py`, `tests/test_setup_assist_env_block.py`, and this progress record. Bounded S06 remediation below 400 lines; S06 remains checked and no task/gate order changed.
- Remaining: S07 onward and G2b; all external/publication gates stay unchanged.

## S06 — final-check-to-replace directory-TOCTOU correction: COMPLETE

Delivery: parent-authorized exact `S06-windows-directory-guard` correction only. No new native attempt was acquired or settled; no commit, installer, delivery, real YASB/state/PATH mutation, or later slice.

### TDD Cycle Evidence

| Phase | Action / command | Result |
| --- | --- | --- |
| RED | Added the native Windows race test before guard code. Its `os.replace` boundary hook runs only after final pathname checks, attempts a real parent-directory rename, and creates a junction only if the rename succeeds. | Exact node → **1 failed**: attack fired, rename succeeded, and substitution was possible. |
| GREEN | Added a verified `CreateFileW` directory handle (`FILE_FLAG_BACKUP_SEMANTICS`, `GENERIC_READ`, shared read/write only — no `FILE_SHARE_DELETE`) held across temp creation, flush, replace, post-replace read verification, and rollback-sensitive verification. | Exact node → **1 passed**: attack fired at replacement, rename was denied, no junction was created, and `.env` updated normally. |
| TRIANGULATE | Mutated the handle share mask from read/write (`0x3`) to read/write/delete (`0x7`), then restored the exact source bytes. | Exact node → **1 failed**: rename and junction substitution succeeded; restored guard passed. |
| REFACTOR | Retained handle-bound read/temp/backup/rollback, O_EXCL, BOM/newline/idempotence/markers/M6/no-secret behavior. | Focused suite **65 passed**; Ruff and `py_compile` clean. |

### Verification and scope

- Determinism: the native junction race passed **20 consecutive** runs; all activity used pytest `tmp_path` and cleanup removed test trees/junctions.
- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_env_block.py tests/test_setup_assist_protocol.py tests/test_frozen_entry_order.py` → **65 passed**.
- Full: `python -m pytest -q --strict-markers` → **806 passed, 3 skipped** (39.60s). Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** (7.51s).
- Diagnostics: `python -m ruff check src/yasb_limitora/_env_block.py tests/test_setup_assist_env_block.py` and `python -m py_compile src/yasb_limitora/_env_block.py tests/test_setup_assist_env_block.py` → clean.
- Accounting is against immutable pre-correction tree `01513cb574a70354f15adec568d3ac401e54a53e`, not the ordinary index. Reproduce from the repository root:

  ```sh
  base=01513cb574a70354f15adec568d3ac401e54a53e; tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT; total=0
  for path in src/yasb_limitora/_env_block.py tests/test_setup_assist_env_block.py openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md; do
    baseline="$tmp/$(basename "$path")"; git show "$base:$path" > "$baseline"
    numstat=$(git diff --no-index --numstat -- "$baseline" "$path" || test $? -eq 1); set -- $numstat
    printf '%s +%s/-%s\n' "$path" "$1" "$2"; total=$((total + $1 + $2))
  done; printf 'total=%s\n' "$total"
  ```

- Result after this evidence edit: `_env_block.py` **+78/−37 = 115**, `test_setup_assist_env_block.py` **+31/−0 = 31**, and this record **+33/−0 = 33**; total **179 changed lines** (≤400). The final correction section occupies 33 physical Markdown lines; physical lines and diff lines are distinct measures.
- No design deviation: raw Windows handle acquisition/final-path failure fails closed; `CloseHandle`/fallback fd closes on all paths. S06 remains checked; S07 onward and G2b are untouched.

## S07 — Optional User PATH and explicit literal-state cleanup: COMPLETE

- Files: `setup_assist.py`, new `_path_cleanup.py`, new `test_setup_assist_path.py`, `test_setup_assist_protocol.py`, task/progress records. HKCU-only verbatim add/remove preserves `REG_SZ`/`REG_EXPAND_SZ`, `%VAR%`, and empty elements; only the recorded final exact element is removed. Cleanup accepts only `YES`, derives the literal state root, rejects file/reparse state, and leaves nonce transport for the result.
- | TDD Cycle Evidence | Result |
  | --- | --- |
  | RED | `python -m pytest -q --strict-markers tests/test_setup_assist_path.py` → collection failed: missing `_path_cleanup` module. |
  | GREEN | focused path/protocol → 50 passed, 1 skipped. |
  | TRIANGULATE | independent duplicate/missing-record, `REG_SZ`/expand, empty-element/`%VAR%`, non-YES, file/reparse, and post-delete-result cases pass. |
  | REFACTOR | ancestor reparse check added; focused rerun 50 passed, 1 skipped; Ruff clean. |
- Verification: focused 50 passed/1 skipped; full `python -m pytest -q --strict-markers` → 813 passed, 4 skipped; native `tests/test_windows_native_proof.py` → 11 passed; scoped Ruff clean. No installer/YASB/process action. An early protocol test accidentally invoked the real adapter once; exact recorded element was immediately removed through the product's precise removal path; tests now inject a fake registry.
- Workload/rollback: 399 changed lines (203 new helper + 124 new path tests + 39 setup add/delete + 19 protocol add/delete + 2 task checkbox + 12 evidence); ≤400. Roll back only the exact recorded PATH element and literal state root after YES; never delete transport. S08+ untouched.

## S07-security-remediation — PARTIAL, security blockers narrowed

Native rescope authorized by the maintainer; attempt token `sha256:793807382e60513bf02cd0b2f9f37af69f558c832e2e680cf0cc0e88e93ac1e2` was not acquired or settled here. This record does not claim settlement of `sha256:d8ea0a47a9a153d909c5c72912d9909245522b63a686d4753c53d251e299a864`.

### Completed bounded corrections

- PATH append now uses a bounded compare/retry operation, preserving an external edit observed before the retry; it preserves `REG_SZ`/`REG_EXPAND_SZ`, empty elements, and verbatim content.
- PATH bookkeeping is rollback-safe: append/record and remove/clear failures compare-restore the original PATH value/type and do not notify.
- The stored record now binds the owned final PATH string/type and element. Any concurrent PATH edit, including an externally appended identical element, refuses removal rather than guessing ownership.
- Cleanup rechecks the literal state directory identity at every destructive descent and rejects a reparse root substituted after prior validation. The deterministic temp-only swap test proves outside content remains intact.
- All operation tests use explicit fake registries. A protocol guard patches the default real adapter to raise and proves the injected fake is used instead.

### TDD Cycle Evidence

| Phase | Command / action | Result |
| --- | --- | --- |
| RED | `python -m pytest -q --strict-markers tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py` | 6 failed, 48 passed, 1 skipped: retry, bookkeeping rollback, ownership, and post-validation root-swap protections were absent. |
| GREEN | Implemented bounded CAS/retry, ownership-bound bookkeeping, rollback, and reparse identity checks | focused rerun: 55 passed, 1 skipped. |
| TRIANGULATE | Mutated the ownership comparison to permit changed PATH ownership, then ran `tests/test_setup_assist_path.py::test_removal_refuses_external_identical_element_after_owned_append`; restored exact code | 1 failed under mutant; restored focused suite passed. |
| REFACTOR | Scoped Ruff plus focused rerun | `ruff check` clean; 55 passed, 1 skipped. |

### Verification and safety evidence

- Focused S07/protocol: `python -m pytest -q --strict-markers tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py` → **55 passed, 1 skipped**.
- Full: `python -m pytest -q --strict-markers` → **818 passed, 4 skipped**.
- Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**.
- Ruff: `python -m ruff check src/yasb_limitora/_path_cleanup.py tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py` → **All checks passed**.
- Sanitized read-only HKCU snapshot before/after: `Path` remained `present`, type `2` (`REG_EXPAND_SZ`), SHA-256 `1a06e298463a47b52a3e818873769549c7758956653858e2f5e77026d32153c4`; bookkeeping remained `absent`. No registry contents were recorded. No real HKCU write, System PATH access, installer/config/YASB/release operation, or process launch was performed. Post-verification attributable process count: `0`.

### Accounting correction and residual risk

- Corrected the original S07 review accounting claim from **400** to the independently measured **399 changed lines** against the supplied attempt-begin accounting: `203 + 124 + 39 + 19 + 2 + 12 = 399`. This is a correction only; it does not authorize a new slice or broaden S07.
- **Residual blocker:** Windows Python does not expose directory file-descriptor operations (`os.supports_dir_fd` is empty). The current cleanup revalidates identity/no-reparse at each path operation and the deterministic root-swap case passes, but it is not a Windows kernel-handle-bound recursive deleter. Do not settle the supplied evidence or treat the cleanup TOCTOU blocker as fully remediated until a true handle-bound Windows deletion primitive is implemented and natively proven.
- S08 and all other slices remain untouched. No task checkbox was changed because this remediation is partial.

## S07-C2 — integration/regression closure: COMPLETE

Delivery: `auto-chain`, `feature-branch-chain`; C2 only. No commit, branch, PR, native-token acquisition/settlement, installer, or real PATH mutation.

### TDD Cycle Evidence

| Phase | Action / command | Result |
| --- | --- | --- |
| RED | Added the missing cross-operation integration guard before any production edit: injected fake registry, patched default real adapter to raise, PATH add/remove plus affirmative cleanup in one assist request. | New guard defines the previously unrepresented C1/C2 integration boundary; no production defect was exposed, so production code was intentionally unchanged. |
| GREEN | `python -m pytest -q --strict-markers tests/test_setup_assist_protocol.py::test_s07_operations_use_injected_registry_and_keep_result_after_native_cleanup` | 1 passed. |
| TRIANGULATE | The guard uses a raising `WindowsUserPathRegistry` replacement: any construction fails; it also requires deleted state, a readable `result.json` below Temp but outside the deleted state root, and empty stdout. | Passed, proving all exercised registry behavior uses the explicit fake and transport remains usable after C1 deletion. |
| REFACTOR | No production refactor: the completed C1 native cleanup integration is correct. | Scoped Ruff clean. |

### Verification, custody, and accounting

- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py tests/test_windows_native_state_cleanup.py` → **62 passed, 1 skipped**. This regresses S07-A PATH ownership/transaction and S07-B literal-YES, root, and transport behavior alongside C1's direct native proof.
- Full: `python -m pytest -q --strict-markers` → **825 passed, 4 skipped**. Native proof: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**. The supplied native token `sha256:ddb8368ad8b58433ca4265af36dfa5d3d513f335aff13a0b8c24c72717080686` was neither acquired nor settled.
- Ruff: `python -m ruff check src/yasb_limitora/setup_assist.py src/yasb_limitora/_path_cleanup.py tests/test_setup_assist_path.py tests/test_setup_assist_protocol.py tests/test_windows_native_state_cleanup.py` → **All checks passed**.
- Sanitized HKCU snapshots before/after are identical: User `Path` is present, type `2` (`REG_EXPAND_SZ`), raw-value SHA-256 `b335b90d33445151c2706289f39ef8e8c1a2659c5b36f7895ceebb57ac629ba9`; app bookkeeping is absent (no value/type/hash). No PATH contents were recorded. The test patched the real adapter to raise and supplied an explicit fake; no registry write occurred.
- Process/temp evidence: focused tests use pytest `tmp_path`; native cleanup tests use temp roots only. No real state root or transport was touched. Final attributable-process query excludes itself and reports `0` after runner completion.
- Why the original **399-line** S07 was practically oversized: one nominal line of headroom could not honestly contain a handle-bound cleanup replacement plus native proof. C1 therefore became a separate feature-chain unit: **312-line base plus a separate 17-line proof correction**. C2 is separately bounded and does not relabel or compress those changes.
- Exact C2 accounting against the C2 attempt-begin tree: `tests/test_setup_assist_protocol.py` +38/−0; `tasks.md` +4/−0; this progress record +24/−0; **66 changed lines**, within the hard ≤250 C2 budget. Aggregate S07 is now complete only because A, B, C1, and this passing C2 are explicitly checked in `tasks.md`; S08 remains unchecked.
- Rollback boundary: remove only the C2 integration guard and its C2 task/progress entries; production cleanup, PATH behavior, state, registry, and transport remain untouched.

## S08 — Config assist Gate 1: whole-document validation and reject-and-preserve: COMPLETE

Delivery: `auto-chain`, `feature-branch-chain`; S08 only. No commit, branch, PR, installer, release-state, PATH, registry, YASB, or real user config mutation. Native attempt token `sha256:7e087b59861ee1dce23a7c5b544a4e9f5e4399532145dbc7325652382261e9fc` was neither acquired nor settled.

### Completed task

- [x] Exposed `config.validate_config_document()` to parse raw UTF-8 with duplicate-key and non-finite rejection and run the existing strict `LocalConfig.from_mapping()` contract without altering runtime callers or acceptance.
- [x] `config-apply` now reads only an existing literal state config during Gate 1. Invalid bytes return one bounded `{field: "config", reason: ...}` diagnostic with no value disclosure and no backup, temp, write, normalization, reserialization, repair, merge, or deletion. Valid/absent configs stop nonfatally before S09's write path.

### TDD Cycle Evidence

| Phase | Command / action | Result |
| --- | --- | --- |
| RED | Added `tests/test_setup_assist_config.py` before production edits | `python -m pytest -q --strict-markers tests/test_setup_assist_config.py` → 8 failed, 1 passed; every invalid case reported the prior `operation-unavailable` behavior. |
| GREEN | Added the reusable raw-document validator and read-only Gate 1 result path | focused test → 9 passed. |
| TRIANGULATE | Replaced the one validator call with `pass` in a temporary source mutation, ran the focused suite, then restored the exact source hash | mutant → 7 failed, 3 passed; restored `setup_assist.py` SHA-256 `7500f89f73f5cfe58813efab907ed8e68d345d0053b01bbf21128ee2f45e1d86`; focused rerun → 10 passed. |
| REFACTOR | Added the runtime-valid no-backup/no-temp boundary case and typed narrowing only; reran focused tests and Ruff | 10 passed; Ruff clean. |

### Verification and preservation evidence

- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_config.py` → **10 passed**.
- Full: `python -m pytest -q --strict-markers` → **835 passed, 4 skipped** in 38.89s.
- Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** in 7.52s.
- Scoped Ruff: `python -m ruff check src/yasb_limitora/config.py src/yasb_limitora/setup_assist.py tests/test_setup_assist_config.py` → **All checks passed**.
- Seven invalid byte inputs (malformed JSON, duplicate key, `NaN`, unknown key, credential-like key, wrong type, and undecodable bytes) are written only below pytest `tmp_path`; each test captures a SHA-256 before read and asserts the exact original bytes plus the same digest after refusal. The credential test asserts a fixed diagnostic and never permits its secret-like value into a record.
- Directory assertions prove invalid and valid existing configs have only `config.json` after Gate 1; absent config leaves even the state root uncreated. The only assist output mutation remains S05's nonce transport result, not config state. No cleanup/process operation is invoked by S08.
- Normal runtime remains fail-closed: the S08 test calls `cli._load_explicit` on an unknown-field document and receives `ConfigError`; existing CLI projection retains `configuration_invalid`. No runtime call site changed.

### Workload / PR boundary and rollback

- Exact S08 attempt-begin accounting: `config.py` **+45/−4** (49), `setup_assist.py` **+35/−0** measured from its 239-line S08 begin snapshot, new config tests **+79/−0**, task checkbox **+1/−1** (2), and this progress record **+34/−0**: **199 changed lines**, within the ≤400 budget. Existing untracked S05/S07 files are excluded from this per-slice accounting.
- Rollback boundary: remove `validate_config_document`, the read-only `config-apply` Gate 1 branch, S08 tests, and this task/progress record. Invalid configs remain untouched; S09 merge/create/backup/write work is not present.
- Remaining work starts at S09; it is deliberately not started by this slice.

## S08 — Gate 1 remediation: COMPLETE

Delivery remains `auto-chain`, `feature-branch-chain`; S08 correction only. Native token `sha256:b58a3f8b6f41add5bbc6f0f8f9eacae5ddc4017db350006c12b9d028d01db988` was neither acquired nor settled; passing remediation target `sha256:5dc980f832a631dbb9db260a69bb895bee20c154aae19860926a63d76eb0da02` is recorded.

- [x] Gate 1 now invokes `LocalConfig.from_mapping` through `validate_config_document(..., provider_errors)` at runtime's provider-scoped whole-document boundary. Invalid root fields still refuse; invalid `codex`/`opencode_go` subdocuments match runtime acceptance and report only bounded `{provider, reason: provider-invalid}` diagnostics.
- [x] Existing config reads are handle-bound: no `exists()`/`read_bytes()`, no-follow open, regular/reparse/size checks, final-handle path binding, and fail-closed refusal when verification is unavailable. The read handle—not a later pathname—supplies validation bytes. No backup/temp/write/normalization/reserialization occurs.
- [x] RED: `python -m pytest -q --strict-markers tests/test_setup_assist_config.py` → **4 failed, 10 passed, 1 skipped** (provider parity and handle-swap cases). GREEN: same command → **14 passed, 1 skipped**. TRIANGULATE: removing the final-handle check made `test_gate_one_refuses_when_handle_verification_detects_a_config_swap` fail; source was restored byte-identically, then focused rerun → **15 passed, 1 skipped**. REFACTOR: scoped Ruff passed.
- Verification: `python -m pytest -q --strict-markers` → **840 passed, 5 skipped**; `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**; `python -m ruff check src/yasb_limitora/config.py src/yasb_limitora/setup_assist.py tests/test_setup_assist_config.py` → **All checks passed**. Temp-only deterministic root-junction coverage passed; file-symlink coverage skipped where the host denies it. External target bytes remained unchanged; no attributable Python/YASB/installer process remained.
- Accounting correction: the historical S08 entry is preserved at the immutable native-ledger value **203 additions+deletions**. This second attempt is **143 additions+deletions**, for **346/400 cumulative**; the false **146/349** claim is removed. S08 remains checked. S09 is deliberately unchecked and unstarted; this proves only the nonfatal optional-operation result contract, not S11 installer continuation.
- Rollback: revert only this Gate-1 validator/read/test correction and its evidence; invalid documents remain byte-identical and no S09 transaction exists.

## S08 — final correction: COMPLETE

Delivery remains `auto-chain`, `feature-branch-chain`; S08 final correction only. No production behavior changed, and no real config/PATH/registry/YASB/installer/release state was touched.

- [x] Added a real Windows temp-filesystem parent-replacement race proof. The reader is synchronized before pathname open, the validated parent is replaced with a junction, and substituted bytes are rejected rather than consumed.

### Strict TDD

- RED: the new behavioral test passed immediately; current production already safely rejects the real race, so this correction is evidence-only and no fabricated RED failure is claimed.
- GREEN: focused S08 config tests passed with the real filesystem race repeated three times inside the node.
- TRIANGULATE: a temporary mutation forcing final-handle verification true made the real-race test fail with `config-gate-2-unavailable`; production was restored byte-identically.
- REFACTOR: bound loop-local synchronization values as function defaults; scoped Ruff and the focused node passed.

### Verification

- Focused: `python -m pytest -q --strict-markers tests/test_setup_assist_config.py` → **16 passed, 1 skipped**.
- Repeated race node: three standalone invocations → **1 passed** each.
- Full: `python -m pytest -q --strict-markers` → **841 passed, 5 skipped**.
- Standalone native proof: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**.
- Ruff: `python -m ruff check src/yasb_limitora/setup_assist.py tests/test_setup_assist_config.py` → **All checks passed**.
- Process/cleanup: pytest temp roots only; no real-state mutation or attributable process remained.

### Accounting

- Immutable native ledger: initial S08 **203**; second attempt **143**; prior cumulative **346**. S08 remains checked and S09 remains unchecked.
- Exact normalized changed lines against this correction attempt-begin tree: **91** (`tests/test_setup_assist_config.py` +60/−0; production +0; progress record +29/−1).
- Native attempt token `sha256:5cb17b72658841134e0a226aa965309d781c9d634160d01b2a44171ec8c139cd` was not settled.
- Rollback boundary: remove only the real-race test and this final-correction record; production behavior and S09 remain unchanged.

## S08 — final cleanup gate remediation: COMPLETE

- Added explicit `finally` cleanup for every probe and replacement junction in `tests/test_setup_assist_config.py`. Cleanup uses Windows `os.rmdir` (directory-link removal; it does not follow the junction target) and asserts each recorded junction is absent. Existing attacker/original config sentinels remain asserted byte-for-byte.
- Strict TDD RED: a temporary cleanup assertion against the pre-change test failed (`1 failed`) at `assert not os.path.lexists(probe)`; baseline inspection found all six created links (three probe junctions and three replacement junctions) in the pytest temp root. GREEN: the focused node passed, and three standalone repeats passed (`1 passed` each). Post-run scans reported `reparse_count=0` for all three repeat roots and `NEW_TEST_ATTRIBUTABLE_JUNCTIONS=0` in the pytest temp root. A broader scan found only two junctions from the unrelated pre-existing root-reparse test; they are not attributable to this node.
- Verification: focused config tests **16 passed, 1 skipped**; full suite **841 passed, 5 skipped**; native proof **11 passed**; `python -m ruff check tests/test_setup_assist_config.py` **All checks passed**. No production code or S09 work changed.
- Accounting uses only the native-authoritative prior value: **93/180 lines charged** before this correction. The current correction remains unsettled; no exact current-attempt total is claimed.

## D01a3a2b — Identity re-open and disposition delete: COMPLETE

Delivery: `auto-chain`, `feature-branch-chain`; D01a3a2b only. No commit, installer, real YASB/state/PATH mutation, or later slice. Depends on delivered D01a3a2a (commit `7a2ea0e`).

### Completed task

- [x] `identity_reopen(path, *, parent, expected, api)` — OPEN_EXISTING on the fixed final marker leaf; verifies exact normalized final path, non-reparse regular-file status, and volume/file identity against the retained original; closes every probe on success and failure.
- [x] `disposition_delete(handle, *, api)` — `SetFileInformationByHandle(FileDispositionInfo)` only on the original DELETE-capable handle after identity confirmation.
- [x] `_real_api()` extended with `set_disposition` (SetFileInformationByHandle info-class 4, BOOL TRUE).
- [x] No marker IO, Guard, reclaim, or deadline policy changed.

### TDD Cycle Evidence

| Phase | Action / command | Result |
| --- | --- | --- |
| RED | Added 10 D01a3a2b tests (imports + `_IOFake.set_disposition` + test bodies) before production code | `ImportError: cannot import name 'disposition_delete'` — collection failed |
| GREEN | Added `identity_reopen`, `disposition_delete`, and `_real_api.set_disposition` | focused 10 passed; full focused 52 passed |
| TRIANGULATE | M1: identity check removed → `test_identity_reopen_rejects_identity_mismatch` FAILED; M2: OPEN_EXISTING→CREATE_NEW → `test_identity_reopen_open_existing_with_identity_check` FAILED; M3: disposition always-True → `test_disposition_delete_refuses_invalid_handle` FAILED; byte-identical restore after each | every mutant killed; restore verified |
| REFACTOR | Fixed 6 Ruff RUF059/F841 unused-variable warnings; no assertion weakened | Ruff clean; focused 52 passed |

### Verification evidence

- Focused: `python -m pytest -q --strict-markers tests/test_config_lock.py` → **52 passed**.
- Full: `python -m pytest -q --strict-markers` → **905 passed, 4 skipped** in 42.33s.
- Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed** in 7.34s.
- Ruff: `python -m ruff check src/yasb_limitora/_config_lock.py tests/test_config_lock.py` → **All checks passed**.
- Process residue: `NO_YASB_PROCESSES`.

### Files changed

| File | Change | Lines |
| --- | --- | --- |
| `src/yasb_limitora/_config_lock.py` | +`identity_reopen` (37 lines), +`disposition_delete` (6 lines), +`_real_api.set_disposition` (6 lines) | +57 |
| `tests/test_config_lock.py` | +imports (2), +`_IOFake.set_disposition` (8), +10 D01a3a2b tests (156) | +166 |
| `openspec/changes/release-and-smoke-test-0-2-0/tasks.md` | D01a3a2b checkbox | +1/−1 |

### Budget and workload

- **223/280** source+test lines (57 source + 166 tests). Within budget.
- Evidence revision: `sha256:eeddde7033be01af1f4968747281c29ad217128fc00a11c1f9a75413248390b2`.
- Attempt token: `sha256:e089f0c9341be45a4ef62dc8d9f5de71e977e9cf6c6617372f64dd143bff5a1c`, settled passed.
- Rollback boundary: revert only `identity_reopen`, `disposition_delete`, `_real_api.set_disposition`, and the D01a3a2b test section; D01a3a1/D01a3a2a remain unchanged.
- Remaining: D01a3b (depends on D01a3a2b); D01b depends on D01a3b.

## D01a3a2b — Corrective: mandatory verification inputs and 1-byte BOOLEAN ABI

Independent verification exposed two contract defects that blocked RDD/delivery despite green tests:

1. **Mandatory verification inputs:** `identity_reopen` previously accepted omitted `parent` and `expected` parameters (defaulted to `None`), allowing callers to bypass exact fixed-leaf path verification and volume/file identity checks. Both parameters are now mandatory keyword-only arguments with no defaults; omission raises `TypeError` at call time.
2. **1-byte BOOLEAN ABI:** `FILE_DISPOSITION_INFO` is a single `BOOLEAN` (1 byte per Win32 ABI), but `set_disposition` was passing a 4-byte `c_int`. Introduced `_FileDispositionInfo` ctypes Structure with a single `c_byte` field (`DeleteFile`), updated `SetFileInformationByHandle.argtypes` to use `POINTER(_FileDispositionInfo)`, and `set_disposition` now instantiates and populates the 1-byte structure. `ctypes.sizeof(_FileDispositionInfo())` asserts to 1.

### Strict TDD

- **RED:** Added `test_identity_reopen_requires_parent_and_expected` (omission of `parent` or `expected` must raise `TypeError` or `MarkerPrimitiveError`) and `test_real_api_set_disposition_uses_one_byte_boolean` (asserts `sizeof(_FileDispositionInfo()) == 1`). Both tests failed as expected: the first because the old code silently accepted `None` defaults, the second because `_FileDispositionInfo` did not exist.
- **GREEN:** Changed `identity_reopen` signature from `parent: ParentHold | None = None, expected: tuple[int, int, int] | None = None` to `parent: ParentHold, expected: tuple[int, int, int]` (mandatory keyword-only). Removed the `if parent is not None:` and `if expected is not None and` guards — both checks now execute unconditionally. Added `_FileDispositionInfo` Structure definition before `_real_api()`, updated `SetFileInformationByHandle.argtypes` to `POINTER(_FileDispositionInfo)`, and rewrote `set_disposition` to instantiate `_FileDispositionInfo()`, set `DeleteFile = 1`, and pass `ctypes.byref(delete)` with `ctypes.sizeof(delete)` (now 1 byte). Both RED tests passed.
- **TRIANGULATE:** Verified that existing tests `test_identity_reopen_rejects_alias_path` and `test_identity_reopen_rejects_reparse` (which previously omitted `expected`) now pass explicit `expected=(0, 0, 0)` values, proving the mandatory-parameter contract is enforced at the call site. Real Windows deletion proof (`test_real_windows_identity_reopen_and_disposition_delete`, `test_real_windows_disposition_delete_never_removes_successor`) continues to pass, confirming the 1-byte BOOLEAN works correctly with the kernel.
- **REFACTOR:** No structural changes needed; Ruff clean.

### Verification

- Focused: `python -m pytest -q --strict-markers tests/test_config_lock.py` → **54 passed** (52 prior + 2 new corrective tests).
- Full: `python -m pytest -q --strict-markers` → **907 passed, 4 skipped**.
- Native: `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` → **11 passed**.
- Ruff: `python -m ruff check src/yasb_limitora/_config_lock.py tests/test_config_lock.py` → **All checks passed**.
- Real Windows deletion proof: `test_real_windows_identity_reopen_and_disposition_delete` and `test_real_windows_disposition_delete_never_removes_successor` both pass with the 1-byte BOOLEAN, confirming kernel acceptance.

### Files changed and corrected accounting

| File | Cumulative D01a3a2b delta from delivered D01a3a2a |
| --- | --- |
| `src/yasb_limitora/_config_lock.py` | 62 additions |
| `tests/test_config_lock.py` | 199 additions |

The independent verifier rejected the first corrective evidence because one new test
triggered Ruff `RUF059`; renaming the unused unpacked handle and typing the dynamic
omission probe fixed it without weakening the mandatory-parameter assertions. A later
read-only cleanup removed a duplicated idempotent `SetFileInformationByHandle` binding.

### Budget and workload

- **Cumulative D01a3a2b:** 261/280 source+test lines (62 source + 199 tests). Within budget.
- Final independent verification: focused **54 passed**; full **907 passed, 4 skipped**; native **11 passed**; scoped Ruff clean; both real Windows deletion/successor tests passed.
- The earlier `244/280` and corrective-delta accounting was inaccurate and is superseded by the directly observed cumulative diff above.
- Rollback boundary: revert only the corrective changes; the original D01a3a2b implementation remains intact.
- Remaining: D01a3b (depends on D01a3a2b); D01b depends on D01a3b.
