# Design: Release and smoke-test the first public 0.2.0 product

The first public `yasb-limitora` 0.2.0 ships as exactly one supported artifact: a per-user,
no-elevation `setup.exe` built by Inno Setup around a PyInstaller **onedir** bundle. Program
files live under `%LOCALAPPDATA%\Programs\yasb-limitora`; mutable state stays in
`%LOCALAPPDATA%\yasb-limitora`. All user-data and environment mutation moves out of Inno Pascal
and into a **private, internal setup-assist entrypoint** of the already-frozen executable, so
every mutation is pytest-testable and reuses the existing redaction and fail-closed discipline.
YASB integration is proven without PATH and without a shell parsing bypass; if no space-free
invocation mechanism passes on the release target, the release fails closed.

This document designs only the mechanisms the approved proposal and the five R11 specs
deliberately left unresolved. It reopens no product decision.

## Quick path for reviewers

1. Read §1.1 to confirm nothing fixed was reopened.
2. Read §10.1 for the selected decisions and their rejected alternatives.
3. Read §6 for the two-checkpoint, release-blocking spaced-path decision table and its fail-closed rule.
4. Read §9.3 for the six <=400-line capability boundaries that task planning will consume.
5. Intentionally out of scope here: task lists, PR topology, and any external evidence claim.

## 1. Context, fixed decisions, constraints, and architecture

### 1.1 Fixed product decisions (not reopened here)

| Fixed decision | Source | Design consequence |
| --- | --- | --- |
| `0.2.0` is the first public release; no retroactive `0.1.0` | release-distribution spec | One version identity; no 0.1.0 tag, notes, or promise |
| No public `-rc` version or tag; RC is internal workflow state | release-distribution spec | RC exists only as CI custody state (§7.1) |
| Selector-free current JSON is the sole output; #137 break documented | release-distribution spec | No compatibility selector, no v1 fallback, no root `version` field |
| Sole public artifact is a per-user Inno Setup `setup.exe`; onedir is an internal input; no portable ZIP | release-distribution spec | Exactly one published download (§3, §7.3) |
| Manifest, SHA-256, SBOM, provenance retained; unsigned + SmartScreen disclosed | release-distribution spec | Immutable identity evidence and separate acceptance custody are defined in §7.1-§7.2 |
| Failed/missing required gate blocks publication; unrun != pass | release-distribution spec | Publish job refuses any `fail`/`unrun` in the bound pre-publication acceptance ledger (§7.3) |
| No Python on target; program files separate from `%LOCALAPPDATA%\yasb-limitora` | installer-lifecycle spec | Two distinct per-user roots (§3.1) |
| Install/reinstall/upgrade keep the product usable; no silent state loss | installer-lifecycle spec | Staged directory swap (§3.3) |
| Failed/cancelled install restores prior program install; state retained by default | installer-lifecycle spec | Executable reverse-swap rollback with quarantine (§3.3); no state deletion on failure |
| Uninstall preserves state; cleanup is visibly opt-in and unchecked | installer-lifecycle spec | Default-negative confirmation (§3.4) |
| YASB integration works with PATH unchanged; User PATH task optional and unchecked | yasb-integration spec | PATH is convenience only (§3.4, §6) |
| Spaced-path proof against the real release target is release-blocking; no shell bypass counts | yasb-integration spec | Decision table + fail-closed rule (§6) |
| Absent or undetected YASB never blocks install; user is informed | yasb-integration spec | Three discovery outcomes, install-independent (§5.1) |
| Never stop/restart/install/uninstall/manage YASB; manual close only | yasb-integration spec | Retry/Cancel prompt, no `TerminateProcess` (§5.2) |
| Only a consented, commented, idempotent `.env` block; no secrets; no YAML/CSS edits | yasb-integration spec | Marker-delimited commented block (§4.2) |
| Wizard is opt-in; runtime-valid config is merged atomically with backup, final validation, and rollback; an invalid existing config is rejected-and-preserved byte-for-byte with bounded enumerated errors, and the abandoned optional operation never fails install/upgrade | configuration-assistance spec | Two-gate transaction in the frozen helper (§4.3) |
| Enabled state changes only by explicit selection; missing secrets/prereqs warn only | configuration-assistance spec | Selection overrides readiness warnings (§4.4) |
| Credentials stay in YASB's startup-loaded environment; never copied anywhere | configuration-assistance spec | No secret in argv, config, logs, evidence (§4.4, §8.3) |
| Frozen runtime preserves Windows gate, helper relaunch, multiprocessing, Job, deadlines, sanitization, no-orphans | runtime-release-acceptance spec | Build must not disturb existing seams (§2.3, §2.4) |
| Smoke matrix + live-provider policy + post-publication clean-machine closeout check | runtime-release-acceptance spec | Pre-publication acceptance and post-publication closeout have separate custody (§8.1) |

### 1.2 Unresolved technical mechanisms this design resolves

Maps to the proposal's twelve open questions.

| # | Open question | Resolved in |
| --- | --- | --- |
| 1 | Per-user program dir, layout, uninstall registration, repair, Inno metadata | §3.1, §3.2, §3.3 |
| 2 | PyInstaller version, hidden imports, build env, determinism | §2.3, §2.4 |
| 3 | Running-YASB detection, manual-close gate, cancellation, stale detection | §5.2 |
| 4 | No-PATH discovery/invocation, spaced path, exact blocking spike result | §5.1, §6 |
| 5 | Distinguishing absent vs undetected YASB for messaging | §5.1 |
| 6 | `.env` block format, ownership marker, atomicity, idempotence, recovery | §4.2 |
| 7 | Wizard schema and merge rules: whole-document validation, reject-and-preserve, backup, atomic write, restore | §4.3 |
| 8 | Installer error/cancellation/rollback/cleanup under locked or malformed state | §3.3, §8.2 |
| 9 | Immutable manifest, separate acceptance ledger, SHA-256, SBOM, provenance formats, SmartScreen text, retention | §7.1, §7.2, §7.3 |
| 10 | CI internal RC state, separate candidate/acceptance custody, hash binding, byte promotion | §7.1, §7.3 |
| 11 | Which version-reporting/doc surfaces change together | §2.2, §9.1 |
| 12 | Which environments are available and how redacted evidence is retained | §8.1 |

### 1.3 Constraints

| Constraint | Evidence | Effect on design |
| --- | --- | --- |
| Closed public argv surface: only `--config`, `-c`, `--config=` | `src/yasb_limitora/cli.py::_config_path` | No `--version` flag may be added (§2.2) |
| Private sentinel precedent: `--__yasb-limitora-codex-helper` handled before argv validation | `cli.py::main` line order | Setup-assist uses the same private-sentinel shape, with the nonce as correlation rather than authorization (§4.1) |
| `multiprocessing.freeze_support()` runs after the platform gate and before the sentinel check | `cli.py::main` | Build must preserve this exact order (§2.4) |
| Frozen detection is bundle-path independent | `codex_helper.py::_is_frozen_runtime` | onedir works without code change (§2.3) |
| Frozen helper relaunches `sys.executable` with the sentinel | `codex_helper.py::_helper_command` | onedir keeps dependencies co-located; onefile rejected (§2.3) |
| PyInstaller 6.x child env keys already propagated | `path.py::_PYINSTALLER_CHILD_ENV_KEYS` | Toolchain floor is PyInstaller >= 6 (§2.3) |
| Default config path is `%LOCALAPPDATA%\yasb-limitora\config.json`; never auto-created | `cli.py::_default_windows_config_path` | State root is fixed; wizard is the only creator (§3.1, §4.3) |
| Cache lives under `%LOCALAPPDATA%\yasb-limitora` with fingerprinted names | `cache.py::_cache_directory` | Uninstall cleanup must target this root only (§3.4) |
| Runtime rejects unknown config fields and credential-like keys | `config.py::_fields`, `_reject_credential_keys` | The same runtime contract is the assist's whole-document pre-mutation gate; an invalid document is rejected-and-preserved, never merged (§4.3) |
| argv is secret-scanned before use | `cli.py::_SECRET` | Assist requests and results travel in a nonce-derived per-user temp transport outside program and state roots, never in argv and never as a stdout contract (§4.1) |
| Pinned example asserts `run_cmd: "yasb-limitora"` exactly twice and `use_shell: false` | `tests/test_customwidget_examples.py` | Read-only discovery and the harness are built before G2a; only S04c may deliberately update the example after G2a selects a feasible mechanism, and only G2b can accept the installed candidate (§6.3) |
| Documentation contract test forbids `0.1.0`/`0.2.0` in guarded doc regions | `tests/test_windows_only_documentation_contract.py` | Release material goes to new files (§9.1) |
| Strict TDD, `--strict-markers`, native Windows proof where supported | `openspec/config.yaml` | Every mechanism needs a test named in §9.2 |
| 400-line review budget per capability | proposal | Six boundaries in §9.3 |

### 1.4 Architecture and data flow

```
                             BUILD TIME (CI, Windows runner, Python present)
      git tag/SHA + pyproject(dynamic) ──> __version__ = "0.2.0"  [single source]
                                                  │
                            ┌─────────────────────┴──────────────────────┐
                            ▼                                            ▼
                PyInstaller onedir spec                         build-info.json
                            │                                  (tool versions,
                            ▼                                   SOURCE_DATE_EPOCH)
            dist/yasb-limitora/  [S02 frozen target]
              yasb-limitora.exe + _internal/
                            │ + S04a real-YASB harness
                            ▼
              G2a FEASIBILITY/SELECTION on disposable/prototype M3/M6/M8
              [full real-target evidence; no publication acceptance or
               installer-guaranteeability claim]
                            │ pass selects exactly what S04c may adopt
                            ▼
              STATIC INSTALLER PATH/IDENTITY CONTRACT (when selection needs it)
                            │
                            ▼
              S04c BOUNDED ADOPTION
                            │
                            ▼
              LATER INSTALLER/BUILD SLICES + Inno Setup /D defines
                            │
                            ▼
              yasb-limitora-0.2.0-setup.exe   <-- SOLE PUBLIC ARTIFACT/CANDIDATE
                            │
              rc-manifest.json + SHA256SUMS.txt + sbom.cdx.json + attestation
              [immutable build identity/integrity; candidate bytes retained]
                            │
                    INTERNAL RC CUSTODY (no public -rc tag)
                            │
                            ▼
              G2b INSTALLED-CANDIDATE CONFIRMATION
              [install exact retained setup.exe; repeat real-YASB spaced-path/
               no-PATH proof against actual adopted behavior and candidate identity]
                            │ only pass closes overall G2
                            ▼
              rc-acceptance.json [separate acceptance workflow/custody]
                build-run + manifest-digest + artifact-hash binding
                pre-publication gates: pass | fail | unrun + evidence refs
                            │ all blocking gates must be pass
                            ▼
              PUBLISH EXACT RETAINED BYTES + VERIFIED EVIDENCE (no rebuild)
                            │
                            ▼
              POST-PUBLICATION CLEAN-MACHINE CLOSEOUT CHECK
              [separate closeout evidence; never rewrites acceptance/identity]

                         INSTALL TIME (user machine, no Python)
  setup.exe (PrivilegesRequired=lowest, no elevation)
      │
      ├─ Inno Pascal owns: consent UI, program-file copy, staged dir swap,
      │                    rollback, uninstall registry, invoking the helper
      │
      ├─> %LOCALAPPDATA%\Programs\yasb-limitora\      [IMMUTABLE PROGRAM]
      │       yasb-limitora.exe, _internal\
      │
      ├─> %LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\
      │       request.json / result.json              [TRANSIENT TRANSPORT]
      │       derived independently by both sides; removed by installer
      │
      └─> frozen private assist entrypoint (sentinel + per-run nonce env value)
              owns ALL user-data and environment mutation:
              ├─ YASB discovery (registry, known dirs, process snapshot)
              ├─ User PATH read-modify-write (HKCU only, opt-in)
              ├─ .env commented managed block (atomic, idempotent, backed up)
              ├─ config.json two-gate transaction (validate whole doc ->
              │    reject-and-preserve, or backup/merge/validate/rollback)
              └─ explicit-consent state cleanup on uninstall; result stays in temp
                        │
                        ▼
      %LOCALAPPDATA%\yasb-limitora\                   [MUTABLE STATE]
          config.json, quota-v2-cache-*.json, backups\

                         RUN TIME (unchanged contract)
  YASB CustomWidget ──run_cmd (no PATH, no shell)──> yasb-limitora.exe
      └─> platform gate ─> freeze_support() ─> argv validation
            └─> ExecutionOrchestrator ─> contained helper (Job, deadline,
                  nonce-bound IPC) ─> Limitora provider calls
            └─> sanitized selector-free JSON on stdout + exit code
```

## 2. Repository layout, single version source, and frozen build design

### 2.1 Repository and component layout

New top-level `packaging/` keeps installer technology out of `src/` and out of the runtime
import surface.

```
packaging/
  pyinstaller/
    yasb-limitora.spec        # onedir, console=True, entry cli:main
    version_info.txt.in       # Windows version resource template
  inno/
    yasb-limitora.iss         # per-user script; Pascal limited to §4.1 duties
    SetupAssistant.isi        # include: staged swap + helper invocation only
scripts/
  build_frozen_bundle.py      # runs PyInstaller, emits build-info.json
  build_setup.py              # runs ISCC with /D defines from __version__
  make_release_manifest.py    # immutable rc-manifest.json + SHA256SUMS.txt
  make_release_acceptance.py  # separate bound rc-acceptance.json
  smoke_frozen.py             # frozen-bundle smoke driver (CI-runnable)
  spacepath_spike.ps1         # release-target spike harness (§6)
docs/release/
  0.2.0/
    RELEASE_NOTES.md          # first-public + #137 break + unsigned disclosure
    MIGRATION.md              # editable-checkout -> setup.exe migration
    SMOKE-0.2.0.md            # matrix checklist and gate sign-off
    evidence/                 # redacted logs and cropped screenshots only
src/yasb_limitora/
  setup_assist.py             # PRIVATE: no public export, no __all__ entry
  discovery.py                # PRIVATE-ish: read-only YASB discovery
```

`setup_assist.py` and `discovery.py` are internal modules. They are not added to
`src/yasb_limitora/__init__.py::__all__` and are not documented as a user CLI. This keeps the
public surface exactly as the specs fixed it.

### 2.2 Single version source

**Selected:** `src/yasb_limitora/__init__.py::__version__` is the single source of truth.
`pyproject.toml` switches to `dynamic = ["version"]` with
`[tool.setuptools.dynamic] version = {attr = "yasb_limitora.__version__"}`. CI reads it once and
passes it to PyInstaller (version resource), Inno (`/DAppVersion`), the manifest, and the
artifact filename.

| Alternative | Verdict | Reason |
| --- | --- | --- |
| Keep `version` static in `pyproject.toml` plus `__version__` | Rejected | The current duplicate already disagrees in intent (both say placeholder `0.1.0`); drift is a release-identity defect |
| Generate `__version__` from the git tag at build time | Rejected | Tags are created after candidate validation; version must exist before the build |
| Read version from `importlib.metadata` at runtime | Rejected | Frozen bundles have no reliable installed-distribution metadata; adds a failure mode |

**No `--version` CLI flag.** `_config_path` accepts only `--config`, `-c`, and `--config=`;
everything else raises `InvocationError` and exits `2`, and `test_cli_output_version.py` locks
that the removed selector surface stays invalid. Adding a version flag would reopen a fixed
invocation contract. Version identity is therefore proven from three places instead:

1. Package metadata (`pyproject` dynamic attr).
2. The installed exe's Windows version resource and the uninstall registry `DisplayVersion`.
3. `build-info.json` inside `_internal/`, which is a build record and never part of JSON output.

**Doc-contract caution:** `test_windows_only_documentation_contract.py` asserts that `0.1.0` and
`0.2.0` do not appear in the guarded regions of `docs/architecture/README.md` and
`docs/research/README.md`, and that `docs/roadmap.md` never says `Limitora 0.2.0`. Those guards
protect **Limitora** version strings. Product release material therefore lands in the new
`docs/release/0.2.0/` tree. If any guarded document must mention the product version, the test
is updated deliberately in the same change and the reason is recorded — never by weakening the
guard.

**Stale placeholder copies.** A repository sweep for `0.1.0` finds a third copy in
`build/lib/yasb_limitora/__init__.py`, a leftover setuptools build directory that is not an active
source path. It must not be edited as if it were source; it is removed from the working tree (and
kept out of the build and release inputs) so that no sweep for the placeholder version returns a
live hit. The frozen bundle must be built from `src/`, never from `build/lib/`.

### 2.3 PyInstaller onedir build design

| Setting | Value | Reason |
| --- | --- | --- |
| Mode | `onedir` | Evidence-backed: `_helper_command()` relaunches `sys.executable` with a sentinel and needs dependencies co-located; exploration records repeated successful onedir native proof and a onefile failure to complete the bounded frozen child path |
| Entry | `yasb_limitora.cli:main` | Same entry as `[project.scripts]`, so the platform gate, `freeze_support()`, and sentinel order are unchanged |
| `console` | `True` | YASB captures stdout; a windowed build breaks pipe capture and the byte-exact JSON contract |
| PyInstaller | Pinned `>=6,<7`, exact version recorded | `path.py` already propagates `_PYI_ARCHIVE_FILE`, `_PYI_APPLICATION_HOME_DIR`, `_PYI_PARENT_PROCESS_LEVEL`, which are PyInstaller 6 onedir variables |
| Python | Pinned to the R10-proven interpreter (3.13.x), exact patch recorded | Matches existing native evidence |
| Dependencies | `limitora[opencode-go]==0.3.1` pinned as today | Limitora keeps provider ownership; no vendoring or duplication |
| Hidden imports | `--collect-submodules limitora` plus explicit collection of any provider plugin resolved by name at runtime | Provider modules are imported dynamically; a missing one would surface only on a clean machine |
| Data files | None from the repository; no `examples/`, no `docs/`, no fixtures in the bundle | Prevents shipping fixtures or evidence into a public artifact |
| UPX | Disabled | Avoids AV false positives and non-deterministic compression |
| Excludes | `tkinter`, test packages, `pytest` | Smaller surface, fewer AV triggers |
| `--clean --noconfirm` | Always | Removes stale build cache between candidates |

**Determinism stance: reproducible-enough, not byte-reproducible.** The specs require that
published bytes equal validated bytes; they do not require that two builds of the same commit
produce identical bytes. The design therefore guarantees identity by **retaining and promoting
the exact candidate** (§7.3), not by rebuild comparison. Deterministic inputs are still
controlled so drift is detectable: pinned tool versions, `SOURCE_DATE_EPOCH` pinned from the
commit, no timestamps or absolute build paths embedded in `build-info.json` beyond recorded
constants, and a fixed runner image.

A rebuild-equality requirement is explicitly **rejected**: it would demand a locked build
container and timestamp-stripped PE post-processing that cannot be validated inside this
change's budget, and it is not needed to satisfy any spec requirement.

### 2.4 freeze_support, helper relaunch, and toolchain design

Invariants the build must preserve, each with a test in §9.2:

1. **Order.** Platform gate → `multiprocessing.freeze_support()` → sentinel dispatch → argv
   validation. The frozen helper child re-enters the same exe, so `freeze_support()` must run
   before the sentinel check. The build may not introduce a wrapper entry that reorders this.
2. **Helper relaunch.** `_helper_command()` returns `(sys.executable, sentinel)` when frozen.
   In onedir, `sys.executable` is `yasb-limitora.exe` in the program directory, which is stable
   across the run and is never inside `%LOCALAPPDATA%\yasb-limitora`. This is why the program and
   state roots must stay separate: a helper relaunch must never traverse mutable state.
3. **Job containment and cleanup.** Windows Job assignment, deadlines, and no-orphan behavior are
   already implemented; the frozen proof must re-establish them on a clean no-Python machine
   because packaging, not source, is the variable under test.
4. **Child environment.** `_PUBLIC_CHILD_ENV_KEYS` plus `_PYINSTALLER_CHILD_ENV_KEYS` are the
   complete propagated set. The build must not add env requirements (for example a bundle path
   variable) that the child filter would drop.
5. **Assist sentinel.** `setup_assist` uses `--__yasb-limitora-setup-assist`, dispatched in
   `main()` immediately after `freeze_support()` and before `_config_path`. Dispatch fires only
   when the per-run nonce environment variable written by `setup.exe` is present; without it,
   the sentinel string is not recognized and falls through to normal argv validation, exiting
   `2` like any other unknown argument without touching any file. The nonce is **correlation
   and accidental-invocation protection, not authorization**: a same-user caller already owns
   every file and registry location the assist can touch, so the security boundary is the
   same-user OS ownership plus the assist's fail-closed schema and path checks. Installer and
   assist independently derive `%LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\` from
   the Windows Local AppData known folder, fixed literal segments, and the validated nonce.
   Request and result are `request.json` and `result.json` there — never under program or state,
   never from a request-supplied path, never in argv, and never on stdout.
6. **No second public surface.** The assist sentinel is undocumented for users, absent from
   `--help`-equivalent behavior (there is none), absent from README instructions, and inert
   when the nonce is missing. The assist also introduces **no second stdout JSON contract** on
   the public executable: its machine-readable result is the result file, and the child's
   stdout during an assist run is not a consumed interface.
