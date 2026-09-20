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

## 3. Per-user `setup.exe` design (Inno Setup as the technology)

`setup.exe` is the artifact; Inno Setup is the technology that produces it. Nothing in this
section makes Inno part of the product contract.

### 3.1 Program/state separation and installed layout

| Root | Path | Mutability | Owner |
| --- | --- | --- | --- |
| Program | `%LOCALAPPDATA%\Programs\yasb-limitora\` | Immutable between lifecycle ops; replaced wholesale | Inno |
| State | `%LOCALAPPDATA%\yasb-limitora\` | Mutable at runtime | Application |

`PrivilegesRequired=lowest` makes Inno map `{autopf}` to `{userpf}` = `%LOCALAPPDATA%\Programs`,
so the default directory is `{autopf}\yasb-limitora` with no elevation and no machine-wide write.
This satisfies the least-privilege per-user requirement without needing an elevation path.

Program layout:

```
%LOCALAPPDATA%\Programs\yasb-limitora\
  yasb-limitora.exe            # frozen console entry; also the helper and assist host
  _internal\                   # PyInstaller onedir payload
    build-info.json            # version, git SHA, tool versions, SOURCE_DATE_EPOCH
    ...                        # limitora + dependencies + bootloader
unins000.exe / unins000.dat    # Inno uninstaller, inside the program root
```

State and transport layouts:

```
%LOCALAPPDATA%\yasb-limitora\
  config.json                  # created ONLY by the opt-in wizard
  quota-v2-cache-*.json        # runtime cache, fingerprinted
  backups\
    config.<UTC-timestamp>.json
    env.<UTC-timestamp>.bak    # YASB .env backups live HERE, never in YASB's dir

%LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\
  request.json                 # transient transport; written by setup.exe
  result.json                  # transient sanitized result; written by the assist
```

Hard separation rules:

- The state root is **never** nested inside the program root, and the program root is never
  nested inside the state root. They are siblings under `%LOCALAPPDATA%`.
- The transport root is a third, transient root under the per-user Local AppData temp directory;
  it is outside both program and mutable-state roots. Read-only discovery therefore never creates
  `%LOCALAPPDATA%\yasb-limitora` merely to exchange a request or result.
- No installer operation may glob, enumerate, or delete `%LOCALAPPDATA%` or its `Temp` directory.
  State cleanup targets the exact literal state root; transient cleanup targets only the exact
  nonce directory independently derived under the fixed transport parent.
- Backups of YASB-owned files are stored in our state root, so the product never adds files to a
  YASB directory.
- The runtime continues to resolve `config.json` from `LOCALAPPDATA` exactly as
  `_default_windows_config_path` does; the installer does not introduce a second resolution path
  and does not set `YASB_LIMITORA_CONFIG`.

### 3.2 Stable identity, upgrade codes, and uninstall registration

| Item | Value | Reason |
| --- | --- | --- |
| `AppId` | One fixed GUID, generated once and committed | Stable identity across versions; drives upgrade detection and the uninstall key |
| `AppVerName` / `AppVersion` | `yasb-limitora 0.2.0` / `0.2.0` from `/DAppVersion` | Single version source (§2.2) |
| `AppName`, `AppPublisher`, `AppSupportURL` | Filled from repository metadata | Registry display quality |
| `DefaultDirName` | `{autopf}\yasb-limitora` | Per-user, no elevation |
| `DisableProgramGroupPage` | `yes` | No Start Menu folder noise; no per-user group decision |
| `PrivilegesRequired` | `lowest` | Per-user ownership model |
| `PrivilegesRequiredOverridesAllowed` | `commandline` **not** enabled | Prevents an elevation path from silently changing the ownership model |
| `ArchitecturesInstallIn64BitMode` | `x64compatible` | Matches the Windows-only, x64 runtime boundary |
| `OutputBaseFilename` | `yasb-limitora-0.2.0-setup` | One public filename; internal RC uses the same name but is never published (§7.1) |
| Uninstall registry | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppId}_is1` (Inno default under `lowest`) | No `HKLM` write; `DisplayVersion=0.2.0`; `NoModify=1`, `NoRepair=1` |
| Version-resource | Generated `version_info.txt` from `__version__` | File properties match registry and metadata |

`NoRepair=1` is deliberate: see the repair decision in §3.3.

### 3.3 Lifecycle and rollback model

**G1 final evidence result: the selected pre-install evacuation fallback is proven.** The historical post-install staged directory rename-swap remains rejected because its exact new `UninstallString` exited `0` while leaving the canonical renamed payload behind. The separate fallback run evacuated the prior canonical directory before Inno copied/registered, retained canonical bookkeeping, passed success uninstall, passed induced post-bookkeeping failure cleanup with a late-failure native-uninstaller harness correction, restored prior HKCU values/types, passed the prior uninstall, and cleaned all exact disposable roots/key under `PrivilegesRequired=lowest`.

The following block is the rejected post-install rename mechanism retained as historical spike context; it is not the selected S10/S11 implementation.

```
install/upgrade (canonical dir = {autopf}\yasb-limitora):
  1. preflight: probe for running YASB and running yasb-limitora.exe (§5.2);
                report any stale .old / .failed directory left by an interrupted run
  2. stage:     copy the onedir payload to  {autopf}\yasb-limitora.new
  3. verify:    confirm yasb-limitora.exe and _internal\build-info.json exist in .new
                and that build-info version == expected version
  4. capture:   record the prior lifecycle bookkeeping verbatim (DisplayVersion,
                UninstallString, InstallLocation under the {AppId}_is1 uninstall key)
                so a rollback can restore it exactly
  5. swap:      5a. if the canonical dir exists -> rename it to yasb-limitora.old
                5b. rename yasb-limitora.new -> canonical
  6. register:  write the new version's uninstall registry entries and version resource
  7. commit:    the program-file transaction COMMITS here; delete yasb-limitora.old
  8. assist:    after commit, run the frozen assist entrypoint for consented mutations (§4).
                ANY assist outcome — refusal, reject-and-preserve of an invalid config
                (§4.3), .env failure — is NONFATAL: it is reported on the summary page and
                never rolls back the committed program, never reopens the transaction.

  on failure at 2/3:  delete .new; prior install intact; registry untouched; state untouched
  on failure at 5a:   abort; canonical dir untouched; delete .new; state untouched
  on failure at 5b:   rename .old back -> canonical; delete .new; registry untouched
  on failure at 6 (the canonical destination is ALREADY OCCUPIED — rollback must still be
  executable): reverse-swap with quarantine, in this exact order:
r1. rename canonical -> yasb-limitora.failed   (quarantine first; never delete in place)
r2. rename yasb-limitora.old -> canonical      (the prior program is live again)
r3. restore the registry values captured at step 4 (the prior version identity is live)
r4. delete any .new remnant; delete .failed only if it is unlocked, otherwise leave it
quarantined and report it
  if r1 or r2 fails (a lock): retry once after a bounded delay; if it still fails, leave
  both directories untouched, keep the registry at its captured prior values, report
  `rollback-incomplete`, and direct the user to rerun the same-version reinstall, which
  completes the transaction. Never delete `.old` while the canonical dir does not hold a
  verified coherent program.
  locked file at 2/5:  do NOT force; report and abort with the prior install intact

uninstall:
  1. preflight running-YASB probe (§5.2)
  2. Inno creates the independently derived nonce temp transport and invokes the assist
  3. assist: remove the User PATH entry if it was added; on explicit consent only,
             delete the literal state root (never anything above it); write the sanitized
             operation result to temp transport outside that deleted tree
  4. Inno reads the result and removes request.json, result.json, and the empty nonce directory
  5. remove the program root and the uninstall registry entries
```

**Historical coherence claim disproven by G1.** The spike's exact new `UninstallString` pointed at
the canonical directory and exited `0`, but the canonical payload remained after the uninstall key
was removed. The post-install rename therefore does not keep the uninstaller pair coherent; this
paragraph is retained only to explain the rejected mechanism and is not an acceptance claim.

**Historical G1 result.** The native run reached commit and rewrote the registry paths, but the exact
new `UninstallString` returned `0` while leaving the canonical disposable payload present. That
proves the post-install rename does not preserve coherent Inno uninstaller bookkeeping and is
rejected/disproven for this mechanism.

**G1-proven selected fallback for S10/S11:** pre-install evacuation. Rename the prior canonical
directory to `.old` **before** Inno copies files, let Inno install and register against the canonical
path natively, and delete `.old` only on success. On induced post-bookkeeping failure, the exact
new native uninstaller removes the new canonical/key, then the captured prior registry values/types
and `.old` are restored. Inno 6.7.3 records its installation complete before `ssPostInstall`, so
the exact native uninstaller is the smallest disposable harness correction for the late failure
hook; it is recorded explicitly rather than claimed as an Inno transaction rollback. The fallback
keeps Inno bookkeeping canonical at the cost of a short window with no canonical directory, which
the running-YASB preflight already makes safe because no product executable is in use. The retained
run's `evidence/integrity.json` is the bounded self-verifying hash record for compile inputs,
retained copies, setup EXEs, and all used logs. Its `evidence/execution-binding.json` is explicitly
post-run-derived: it binds ordered compile/setup/uninstaller actions from the harness source,
native-log headers, process-exit ordering, and exact captured `UninstallString` values. Evidence:
`docs/release/0.2.0/evidence/inno-staged-swap-spike.md` and the retained sanitized run under
`build/g1-fallback/<run-id>/`.

| Alternative | Verdict | Reason |
| --- | --- | --- |
| In-place overwrite into one directory | Rejected | A failed upgrade can leave mixed-version files while still reporting the new `DisplayVersion`; the spec requires the prior install to remain usable or be restored |
| Side-by-side versioned directories plus a `current` pointer | Rejected | The invocation path would change per release or require a junction/symlink; junctions add a failure mode and symlinks need privileges the per-user model refuses. It also destabilizes any `run_cmd` path the user saved |
| Rely solely on Inno's built-in file rollback | Rejected as sufficient | Inno rolls back copied files, but it cannot guarantee that a half-applied directory is the *prior usable* program; the swap makes the prior program a named, restorable object |

**Repair decision (the proposal left this open):** no separate Repair entry is exposed
(`NoRepair=1`). Reinstalling the same version will use the selected pre-install-evacuation
lifecycle once S10/S11 implement it. Rationale: a distinct repair flow is a third lifecycle
state that needs its own locked-file, partial-state, and rollback evidence; the budget does not
allow proving it, and reinstall already delivers the same outcome. This is recorded as a
selected decision, not a spec change.

**Locked or malformed state (proposal question 8):**

| Condition | Behavior |
| --- | --- |
| Program file locked by a running CLI or YASB child | Abort before the swap; prior install intact; manual-close prompt already offered (§5.2); never kill a process |
| `yasb-limitora.old` or `yasb-limitora.failed` left over from an interrupted run | Detected at preflight; reported; removed only after a successful swap and only when the canonical dir holds a verified coherent program |
| `config.json` malformed or unreadable | Assist refuses before any backup, merge, or write: the original bytes are preserved exactly, bounded validation errors are enumerated on the summary page, and the install/upgrade continues (§4.3). The runtime already fails closed with `configuration_invalid` |
| Registration fails after the swap (canonical dir occupied) | Reverse-swap with quarantine per §3.3 step 6; registry values captured beforehand are restored; `rollback-incomplete` is reported when a rename is blocked; `.old` is never deleted while the canonical dir is incoherent |
| State root exists but is a file, not a directory | Assist reports and performs no deletion; install still succeeds |
| Insufficient disk space during staging | Fail at step 2 before any rename; prior install intact |
| User cancels mid-wizard | Assist rolls back its own transaction (§4.3); the program swap already committed and stays committed, because cancelling a data wizard is not a failed install |

Install, reinstall, upgrade, cancellation, and rollback failures never delete state. The sole
state-deletion path is a successfully validated `state-cleanup` operation after the explicit
uninstall choice (§3.4); its result transport is outside state and is cleaned separately by Inno.

### 3.4 PATH and cleanup tasks

**User PATH task (opt-in convenience).**

| Property | Value |
| --- | --- |
| `[Tasks]` entry | `Name: "addtopath"`, `Flags: unchecked`, description states it is optional and not required for YASB |
| Scope | `HKCU\Environment` `Path` only; System PATH is never read or written |
| Executor | The frozen assist entrypoint, not Inno Pascal (§4.1) |
| Algorithm | Read the current `REG_EXPAND_SZ`/`REG_SZ` value verbatim; if the exact program directory is already present as a path element, do nothing; otherwise append `;<dir>` to the verbatim string and write it back with the original value type |
| Never | Parse PATH into a list and rejoin it; normalize case or separators; drop empty elements; expand `%VAR%`; truncate |
| Record | The exact appended element is stored under the app's uninstall registry key so removal is precise |
| Removal | On uninstall, the assist removes exactly that recorded element, again by verbatim string surgery, and broadcasts `WM_SETTINGCHANGE` |
| Disclosure | Installer text and `MIGRATION.md` state that a PATH change takes effect only in newly started processes and that YASB must be restarted by the user for direct CLI discovery — while YASB integration itself never depends on PATH |

**Cleanup task (destructive, default-negative).** Inno provides no uninstall-page checkbox, so
cleanup is an explicit confirmation with **No** as the default button:

- Presented only during uninstall, after the running-YASB preflight.
- Wording names the exact directory that would be deleted and states that configuration, cache,
  and backups are included.
- `MB_YESNO | MB_DEFBUTTON2`; only an affirmative `YES` sets the flag the assist consumes.
- Cancel, dismissal, or any non-`YES` result means "preserve state".
- The request contains only the selected `state-cleanup` operation and the affirmative consent
  choice; it contains no target path. The assist independently resolves the literal mutable-state
  root from the Windows Local AppData known folder, verifies every existing path component is not a
  reparse point, and verifies the target is neither the program root, the transport root,
  `%LOCALAPPDATA%`, nor a parent of any of them.
- Only after those checks and explicit `YES` consent does the assist delete that literal state root.
  It then writes the bounded, sanitized result to the separately derived temp transport directory,
  which remains available even though the state tree is gone. Inno reads the result and removes the
  exact transient nonce directory afterward.

| Alternative | Verdict | Reason |
| --- | --- | --- |
| Custom `TNewCheckBox` uninstall page | Rejected | Adds a wizard-page implementation and its own test surface for one boolean; the default-negative confirmation is equally explicit and far smaller |
| `Flags: unchecked` task shown at install time to pre-authorize future deletion | Rejected | Pre-authorizing destruction of data that does not yet exist inverts the spec's "only when the user explicitly selects it" |

## 4. Configuration-assistance boundary: application-owned helper vs Inno Pascal

### 4.1 Ownership split

**Selected: a private, internal setup-assist entrypoint inside the already-frozen executable
owns every user-data and environment mutation. Inno Pascal owns only the installer's own
program-file transaction, consent UI, and registry identity.**

| Responsibility | Owner | Why |
| --- | --- | --- |
| Consent capture: wizard checkbox, `.env` checkbox, cleanup confirmation | Inno Pascal | UI is Inno's job; it produces booleans, not file edits |
| Program-file copy, staged swap, rollback, program-root deletion | Inno Pascal | It is the installer's own transaction and must work on a first install before any application code exists on disk |
| Uninstall registry identity | Inno Pascal | Registry identity is installer metadata |
| Invoking the assist: derive/create the nonce temp transport, write `request.json`, `Exec` the sentinel with the nonce env value, read `result.json`, then delete the exact transport | Inno Pascal | One `Exec` call plus bounded UTF-8 transport operations outside state; all mutation semantics stay in testable Python |
| YASB discovery and outcome classification | Assist | Needs registry, filesystem, and process-snapshot logic that must be unit-testable |
| User PATH read-modify-write and removal | Assist | String surgery on a user-critical registry value must be pytest-proven, never Pascal-proven |
| `.env` managed block create/update | Assist | Needs byte-exact preservation, encoding detection, backup, atomic replace |
| `config.json` two-gate transaction: whole-document validation, reject-and-preserve, safe merge, backup, rollback | Assist | Needs JSON parsing, full reuse of `config.py` runtime-contract validation, and byte-identity guarantees |
| Explicit-consent state cleanup | Assist | Deletion needs the same path-safety proofs as the rest of the state model |
| Any YAML or CSS edit | **Nobody** | Forbidden by spec |
| Any secret read, write, or transport | **Nobody** | Forbidden by spec |

Why this reduces unsafe installer script logic:

- **Testability.** Assist behavior runs through pytest on the same source path as the runtime,
  under the repository's strict-TDD rule. Inno Pascal has no test harness here; every line of
  Pascal is unverifiable except by manual native runs.
- **Reuse of existing safety invariants.** The assist reuses `_reject_credential_keys` for
  secret refusal, the strict JSON parsing discipline from `cli.py`, the deadline discipline from
  `deadline.py`, and the mutex/lock discipline from `guard.py`. Pascal would reimplement all of
  these badly.
- **Encoding and byte safety.** `config.json` and `.env` are user data with possibly non-ASCII
  content and BOM/CRLF variation. Python byte-level handling is provable; Pascal string handling
  is a known corruption source.
- **Smallest Pascal surface.** Pascal is reduced to consent booleans, a directory transaction it
  already owns, one invocation, and two small request/result file operations. That is reviewable
  inside the 400-line budget.

**Keeping the helper private and internal:**

- No new public console script in `pyproject.toml`; `[project.scripts]` stays
  `yasb-limitora = "yasb_limitora.cli:main"`.
- No new frozen executable. The assist is the same `yasb-limitora.exe` with a private sentinel,
  mirroring the existing `--__yasb-limitora-codex-helper` precedent, so there is one artifact to
  hash, one bundle to prove, and no second PyInstaller target.
- The sentinel is inert unless `setup.exe` set the per-run nonce environment value for that
  invocation; without it, the sentinel string is not recognized at all and the invocation fails
  exactly like any other unknown argument (`InvocationError`, exit `2`), touching nothing.
- The nonce is **correlation and accidental-invocation protection, not authorization**. A
  same-user caller already owns every file and registry location the assist can touch, so the
  assist's security model is the same-user OS boundary plus its fail-closed schema, path, and
  credential checks — never the secrecy of the nonce. The assist runs with no elevated
  privilege.
- The sentinel stays outside the public CLI contract: it is dispatched before `_config_path`,
  the public argv surface (`--config`, `-c`, `--config=`) is unchanged, and no README, release
  note, migration guidance, or example mentions the sentinel, the nonce variable, or the
  protocol. `test_frozen_entry_order.py` and `test_setup_assist_protocol.py` lock both
  properties.
- The assist never emits the runtime JSON contract and introduces **no second stdout
  contract**: its bounded, sanitized, machine-readable result is `result.json` in the independently
  derived per-user temp transport, which the installer reads and renders. The executable's stdout
  during an assist run is not a consumed interface.

**Interface.** Inno writes a request file, calls the exe, and reads a result file:

```
setup.exe side:
  1. generate a cryptographically random nonce encoded as exactly 32 lowercase hex characters
  2. resolve Local AppData via Inno's trusted `{localappdata}` constant; derive only:
       %LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\
     validate/create the fixed parent without enumerating Temp; refuse any reparse component or a
     pre-existing nonce directory; create that nonce directory exclusively
  3. write request.json exclusively (UTF-8, <=64 KiB, strict schema, no secrets or target paths)
  4. Exec: yasb-limitora.exe --__yasb-limitora-setup-assist
     env: <private nonce var>=<nonce>   (correlation + accidental-invocation protection,
                                         NOT authorization; no elevated privilege)
  5. read result.json only if it is a regular, non-reparse file <=64 KiB and schema-valid
  6. render the sanitized result; delete only request.json/result.json and the now-empty exact
     nonce directory, refusing rather than following or recursively traversing a reparse point

assist side:
  1. validate the nonce grammar before any filesystem access
  2. resolve Local AppData through the Windows known-folder API; append only the fixed
     Temp\yasb-limitora-setup-assist segments and nonce; never accept a transport/target path
     from the request
  3. refuse a missing, malformed, over-size, non-regular, or reparse-point request/transport
  4. execute only schema-listed operations; for state-cleanup, delete only the independently
     resolved literal mutable-state root after default-negative consent, then write result.json
     outside the deleted tree
  5. exit 0 on success and non-zero on refusal/failure; whenever the safe transport remains
     writable, create `result.json` exclusively with the bounded sanitized result; stdout is never
     parsed
```

**Transport selection.** Inno's `Exec`/`[Run]` cannot pipe stdin to a child, and a stdout
result would create a second stdout JSON contract on the public executable, so the transport
is a nonce-derived directory under the per-user Local AppData temp root:

| Transport | Verdict | Reason |
| --- | --- | --- |
| Request in argv | Rejected | `_SECRET` argv scanning; process-listing visibility |
| stdin/stdout JSON | Rejected | Inno cannot pipe stdin through `Exec`/`[Run]`; a stdout result is a second public stdout contract |
| Inherited-handle / named-pipe IPC | Rejected | No mechanism is proven inside Inno's constraints without extra native code or a broker process; unproven here, so it is not selected |
| `%LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\{request,result}.json` | **Selected** | Outside program and state roots, survives state cleanup, does not create mutable application state during discovery, and is independently derivable without honoring a supplied path |

**Schemas and hardening.** `request.json` is an object with exactly `schema:
"gentle-ai.yasb-limitora.setup-assist-request/v1"` and `operations`; `operations` is a bounded,
non-empty array of unique operation objects. Each object has exactly an allowed operation name and
its fixed typed user choices; unknown/duplicate fields, unknown operations, values outside their
bounded domains, and all path-bearing keys are refused. The allowed operations are `discover`,
`yasb-running`, `path-add`, `path-remove`, `env-block-apply`, `config-apply`, and `state-cleanup`.
`result.json` has exactly `schema: "gentle-ai.yasb-limitora.setup-assist-result/v1"`, `status`, and
bounded per-operation reason/warning records; it carries no secret values or unsanitized absolute
user paths. Both files have a 64 KiB maximum.

Installer and assist each derive roots independently; the nonce selects correlation only. Before
create/read/write/delete, each side rejects any reparse-point component and any non-regular file.
The assist never recursively follows a reparse point. `state-cleanup` also refuses if the literal
state root or any descendant is a reparse point, so deletion cannot escape through a link. The
request contains only operations and choices, never a target path. Missing nonce/request,
malformed/over-size data, unsafe roots, schema violations, or cleanup ambiguity fail closed with no
target mutation. Inno owns final transport removal after consuming the result; it removes only the
two literal files and empty nonce directory, never a caller-selected or recursively discovered path.

### 4.2 `.env` managed block design

Runs only after explicit consent. The block is **entirely commented**, so it cannot change YASB
behavior even if YASB parses the file naively.

```
# >>> yasb-limitora managed block v1 (id: yasb-limitora) >>>
# Managed by yasb-limitora setup. YASB loads this file at startup.
# This block is documentation only: every line is a comment.
# It never contains secrets. Provider credentials stay in your own .env entries.
#
# Default configuration location:
#   %LOCALAPPDATA%\yasb-limitora\config.json
# Invoke without PATH from YASB CustomWidget using the full path:
#   <resolved invocation path, see the spaced-path gate>
# <<< yasb-limitora managed block v1 (id: yasb-limitora) <<<
```

| Rule | Design |
| --- | --- |
| Ownership markers | The exact `# >>> ... >>>` and `# <<< ... <<<` lines, including `v1` and `id: yasb-limitora`. Only bytes between a matched marker pair are ever rewritten |
| Commented | Every emitted line starts with `#`. The assist refuses to emit a non-comment line |
| Idempotent | If a matching marker pair exists, the region is replaced in place; the block is never appended twice. Marker count must be exactly 0 or exactly 1 pair; more than one pair is a refusal, not a guess |
| Unrelated content | Read as **bytes**, split on marker lines, and rejoined so every byte outside the region survives verbatim, including trailing newline state |
| Encoding | Detect UTF-8 with or without BOM and preserve the original BOM and dominant newline style. If the file is not decodable as UTF-8, refuse and report `env-undecodable`; do not modify |
| Location | Exactly `<resolved YASB config home>\.env`. A resolved safe home with no `.env` is a valid creatable target after explicit consent, not `inconclusive`; unresolved/unsafe home or absent YASB remains a non-fatal refusal. Discovery itself creates nothing |
| Atomicity | If the safe config home is absent, create only that exact directory after consent and re-run the non-reparse safety check. Write `<home>\.env.yasb-limitora.tmp-*`, flush, `os.fsync`, then `os.replace` to `.env`; remove the temp on failure |
| Backup | If `.env` exists, copy its original bytes to `%LOCALAPPDATA%\yasb-limitora\backups\env.<UTC-timestamp>.bak`, bounded to the most recent 5. If absent, record `create` as the recovery point; no fictional backup is made |
| Rollback | On any error after the recovery point, restore the backup with `os.replace`, or delete the newly created `.env` for `create`; remove an empty home created by this operation. A restore failure reports `env-rollback-failed`; the temp is never promoted on a failed path |
| Secrets | The assist refuses if the rendered region would contain any key or token matching the existing `_CREDENTIAL_KEY` pattern from `config.py`. It writes no credential-like name at all, so the check is a belt-and-braces gate |
| YAML/CSS | Never opened, never read for mutation, never written. Only `.env` is in scope, and only between markers |
| Failure recovery | The installer reports the reason code verbatim in its summary page and completes successfully; consented assistance is not a precondition for installation |

### 4.3 `config.json` transaction: whole-document validation, reject-and-preserve, safe merge

**Owned paths.** The wizard writes only these keys, and only when explicitly selected:

```
deadline_seconds
codex.enabled            codex.runner            codex.timeout_seconds
opencode_go.enabled      opencode_go.timeout_seconds
```

Everything else in the document is *unowned*. In the safe-merge path every other
contract-valid field survives unchanged in its original position and structure.

**One validator, two gates.** The assist validates the **complete** document against the
current runtime contract — the same `config.py` validation the CLI applies, including
unknown-field rejection (`_fields`) and credential-key rejection (`_reject_credential_keys`)
— once before any mutation is planned, and once on the final merged document before the
write. There is no split between "owned-projection validation" and a "whole-document
warning", and no path in which a document that fails the runtime contract is committed
successfully.

**Gate 1 — reject-and-preserve (invalid existing document).** If the existing `config.json`
fails the runtime contract for any reason — an unknown field, a wrong type, an out-of-range
number, a credential-like key, a duplicate key, a non-finite number, undecodable bytes:

- the optional configuration operation is abandoned **before** any backup, merge, write,
  normalization, or reserialization; no temp file is even created;
- the original file remains **byte-for-byte identical** and authoritative;
- the result document enumerates the detected validation errors — field path plus reason
  code per error, capped at a fixed maximum count, never including values — so diagnostics
  stay bounded and non-secret;
- the install/upgrade **continues**: this outcome is nonfatal to the program-file
  transaction (§3.3 step 8) and appears on the installer summary page as a skipped optional
  step with the enumerated errors;
- the document is never repaired, normalized, partially rewritten, reserialized, or deleted,
  and runtime validation is never loosened to accept it. The runtime's own behavior is
  unchanged: the CLI still fails closed on that document with `configuration_invalid`.

**Gate 2 — safe merge (runtime-valid existing document, or no document).**

Gate 2 is split into implementation boundaries: **D01a1** establishes the context-managed
primary Guard lease keyed by the exact fixed config.json path with the real 5-second deadline;
**D01a2a** defines the bounded canonical marker codec with exact schema/size and strict
validation; **D01a2b** defines the Win32 process-identity token; **D01a3a1** implements safe
marker create and identity — verified parent hold/non-reparse/final identity,
correct Win32 CreateFileW CREATE_NEW handle with explicit DELETE+read/write/attributes access,
FILE_SHARE_DELETE compatibility, and NULL template, verify leaf final
path/reparse/regular/identity after create, reuse repo-validated
FILETIME/BY_HANDLE_FILE_INFORMATION/native helpers, at least one real Windows test,
real native create/close proof, no IO or delete; **D01a3a2** implements safe marker IO
and disposition delete — bounded ≤256 read, partial/full write+FlushFileBuffers through
same acquired handle, identity re-open before delete, handle disposition delete and
successor/no-residue proof, low-level sanitized errors, no Guard/reclaim/deadline
policy; **D01a3b** implements fallback policy and integration — typed
ConfigLease, one shared DeadlineContext, fallback only on `guard_acquisition_failed`,
retry/contention, decode/owner predicate, conservative busy rules, reclaim only for
missing/mismatch, and cleanup outcome; **D01b** reads, validates,
and yields an immutable snapshot under a context-managed lease owned by D01a; **D02** consumes
that snapshot to merge, write, and verify. The D01b snapshot is valid only while the D01a lease
remains owned; D02 must consume it inside that same ownership scope. D01a1, D01a2a, D01a2b,
D01a3a1, D01a3a2, D01a3b, and D01b perform no backup, merge, or write. The S08 reject-and-preserve byte-identity
contract is preserved: an invalid document is never touched, backed up, or reserialized.

> **D01 split note.** The original combined D01 candidate (evidence
> `sha256:115ba0a3f1bbde7832d80d544939877db44a24df0845d928de09c67c36548deb`) was rejected
> after native failure settlement/reset and rolled back to the clean baseline. It supplies
> no passing evidence. The maintainer authorized splitting D01 into D01a (≤300 lines) and
> D01b (≤350 lines), each with one rollback boundary.
>
> **D01a finer split.** The D01a candidate (evidence
> `sha256:f2d6e7e39089a09d284da0355fdf39db5be4c2acd2c98a527d5dd0f488e14fb9`) was rejected
> and rolled back with no passing evidence. The maintainer authorized splitting D01a into
> three sequential bounded sub-units — D01a1 (≤180 lines), D01a2 (≤220 lines), and D01a3
> (≤280 lines) — while keeping D01a as the umbrella name. D01b depends on D01a3.
>
> **D01a2 budget raised.** The D01a2 candidate (evidence
> `sha256:15a3e99d15c8e6d06d899dfbb60bce047e85a73a48355722bbe52b319f0d3bde`)
> produced green behavioral tests but exceeded the 220-line budget at 247 code+test lines,
> left the version schema undefined, had CloseHandle ambiguity, an incorrect PID upper
> bound, and exception-handling inconsistency. It supplies no passing evidence. The
> maintainer raised the D01a2 budget to ≤280 lines and defined the exact canonical marker
> schema to resolve the ambiguity.
>
> **D01a2 further split.** After the budget raise to ≤280, a subsequent D01a2 candidate
> (evidence `sha256:4405cb265935e8dffe8d56f96f597e7aca8e730f9d1bcca242121b0c9f0f1c6b`)
> produced a dirty working state with semantically passing marker+Win32 identity but
> exceeded the review budget. The maintainer split D01a2 into D01a2a (marker codec,
> ≤260 lines) and D01a2b (Win32 process identity, ≤220 lines, depends D01a2a). D01a3
> depends on D01a2b. No passing evidence is inherited by D01a2a or D01a2b.
>
> **D01a2b budget raised.** The D01a2b candidate (evidence
> `sha256:9336fb10360083509dbee533ebb2ea1385d98186f04abd4ee605320a499025f5`)
> was rejected with no passing evidence. Rejection reasons: real PID4
> ERROR_ACCESS_DENIED was falsely missing; last error unused; API/query/CloseHandle
> exceptions escaped; close could leak; padded token diverged from cache pattern.
> The maintainer raised the D01a2b budget to ≤280 lines and pinned the correction
> contract: only OpenProcess error87 missing is a valid refusal; all other ambiguity
> is unprovable; use unpadded lowercase hex matching `cache.py`; token is emitted only
> after successful close; invalid caller PID is unprovable/refused rather than proof
> the OS process is missing. D01a3 dependency and cohesive Win32 identity scope are
> preserved.
>
> **D01a3 split.** The D01a3 candidate (evidence
> `sha256:cdfae75a600fc33e170ed1e6d2b5f90b5cacec6e0fc9b99cce071913618e824d`)
> was rejected with no passing evidence. Rejection reasons: 294/280 lines before
> adequate tests, one focused failure, no full/native/Ruff validation. The
> maintainer split D01a3 into D01a3a (safe marker primitives, ≤280 lines) and
> D01a3b (fallback policy and integration, ≤280 lines, depends D01a3a). D01b
> depends on D01a3b. No passing evidence is inherited by D01a3a or D01a3b.

**D01a1 — Guard domain and real deadline.**

Context-managed primary Guard lease keyed by the exact fixed `config.json` path so it
shares the runtime mutex domain; retry Guard's 250ms waits against one 5-second
DeadlineContext; `guard_wait_timeout` remains contention and never activates fallback;
real/injected tests must prove `Global\` naming, exact path key, elapsed/retry semantics,
guaranteed release, and no config/state writes. Target ≤180 changed lines and one rollback
boundary.

**D01a2a — Marker codec.**

Depends on D01a1. The canonical marker is exactly the UTF-8 JSON object
`{"pid": <DWORD 1..4294967295>, "token": <1..64 lowercase hex chars>, "version": 1}`
with sorted keys and no whitespace. Hard preparse maximum is 256 bytes; input exceeding
this limit is refused before field parsing. Duplicate keys, extra fields, missing fields,
boolean values, invalid types, uppercase hex, non-hex characters, oversize output, and
non-object input are all refused with one sanitized marker-validation error. Deterministic
roundtrip; zero file I/O. No Win32/process identity code in this sub-unit.

Target ≤260 changed lines and one rollback boundary.

> **Failed evidence (parent D01a2).** The D01a2 candidate
> `sha256:15a3e99d15c8e6d06d899dfbb60bce047e85a73a48355722bbe52b319f0d3bde`
> produced green behavioral tests but exceeded the 220-line budget at 247 code+test lines,
> left the version schema undefined, had CloseHandle ambiguity, an incorrect PID upper
> bound, and exception-handling inconsistency. It supplies no passing evidence. No passing
> evidence is inherited by D01a2a or D01a2b.

**D01a2b — Win32 process identity.**

Depends on D01a2a. Win32 OpenProcess/GetProcessTimes creation token via a reusable safe
primitive/pattern with no os.kill/process control. A CloseHandle failure or unavailability
during process-identity acquisition is **unprovable** — it produces no usable token and
the marker is refused, not approximated. Tests exercise real Windows identity where
supported and injected edge cases covering every refusal category; no
acquisition/reclaim/unlink yet.

Target ≤280 changed lines and one rollback boundary.

> **Failed evidence (D01a2b).** The D01a2b candidate
> `sha256:9336fb10360083509dbee533ebb2ea1385d98186f04abd4ee605320a499025f5`
> was rejected with no passing evidence. Rejection reasons: real PID4
> ERROR_ACCESS_DENIED was falsely missing; last error unused; API/query/CloseHandle
> exceptions escaped; close could leak; padded token diverged from cache pattern.
> Correction contract pinned: only OpenProcess error87 missing is a valid refusal;
> all other ambiguity is unprovable; use unpadded lowercase hex matching `cache.py`;
> token is emitted only after successful close; invalid caller PID is
> unprovable/refused rather than proof the OS process is missing.

**D01a3a1 — Safe marker create and identity.**

Depends on D01a2b. Verified parent hold/non-reparse/final identity; correct Win32
`CreateFileW` `CREATE_NEW` handle with explicit `DELETE` + read/write + attributes
access, `FILE_SHARE_DELETE` compatibility, and NULL `hTemplateFile`; verify leaf final
path, reparse status, regular-file status, and handle identity after create; reuse and
cross-check repo-validated `FILETIME`/`BY_HANDLE_FILE_INFORMATION`/native helpers from
`_native_state_cleanup.py` — fakes cannot redefine API semantics; at least one real
Windows test is required; real native create/close proof. No IO, no delete, no Guard,
reclaim, or deadline policy in this sub-unit. Target ≤280 changed lines and one rollback
boundary.

**D01a3a2 — Safe marker IO and disposition delete.**

Depends on D01a3a1. Bounded ≤256 read through the same acquired handle; partial/full
write + `FlushFileBuffers` through the same acquired handle; identity re-open before
delete; handle disposition delete and successor/no-residue proof; low-level sanitized
errors. No Guard, reclaim, or deadline policy in this sub-unit. Target ≤280 changed
lines and one rollback boundary.

> **Failed evidence (D01a3).** The D01a3 candidate
> `sha256:cdfae75a600fc33e170ed1e6d2b5f90b5cacec6e0fc9b99cce071913618e824d`
> was rejected with no passing evidence. Rejection reasons: 294/280 lines before
> adequate tests, one focused failure, no full/native/Ruff validation. The maintainer
> split D01a3 into D01a3a (safe marker primitives, ≤280 lines) and D01a3b (fallback
> policy and integration, ≤280 lines, depends D01a3a). No passing evidence is inherited
> by D01a3a or D01a3b.
>
> **Failed evidence (D01a3a) and correction.** The D01a3a candidate
> `sha256:d9ad0c388c0603cbd6e1548e01c63e2b82b64d89654ae1e2304d44c86299213c`
> was rejected with no passing evidence. The maintainer corrects the exclusive-create
> mechanism: the CRT `O_CREAT|O_EXCL` create-then-verify approach is replaced with
> Win32 `CreateFileW` `CREATE_NEW` as the OS-native exclusive-create equivalent,
> requesting explicit `DELETE` + read/write + attributes access and `FILE_SHARE_DELETE`
> compatibility so the same verified handle can be disposition-deleted safely. Held
> verified parent and final-path/regular/non-reparse/identity verification are preserved.
> The implementation must reuse and cross-check repo-validated
> `FILETIME`/`BY_HANDLE_FILE_INFORMATION`/native helpers from `_native_state_cleanup.py`
> and include at least one real Windows test; fakes cannot redefine API semantics.
> Rejected defects recorded: malformed 56-byte ABI `BY_HANDLE_FILE_INFORMATION` struct,
> `hTemplateFile` misuse (non-NULL template on create), missing `DELETE` access or
> `FILE_SHARE_DELETE` incompatibility preventing safe disposition-delete through the
> verified handle, no final-path comparison after create, partial writes without
> flush+fsync, handle leaks on error paths, and no real Windows test. D01a3a budget
> remains ≤280 lines; D01a3b is unchanged; tasks remain unchecked. No source, tests,
> progress, or delivery.
>
> **D01a3a split after failed budget evidence.** The corrected D01a3a candidate
> (evidence `sha256:df157a419b096c9ab12a04b5c23295e3d605355c183c6b105a9303d52863382d`)
> passed focused 45, native 11, full 898+4skip, and Ruff but exceeded the ≤280 budget
> at 563 lines (228 code, 335 tests). It supplies no passing evidence. The maintainer
> split D01a3a into two sequential bounded sub-units — D01a3a1 (safe marker create and
> identity, ≤280 lines) and D01a3a2 (safe marker IO and disposition delete, ≤280 lines,
> depends D01a3a1). D01a3a1 owns verified parent hold, correct Win32 CREATE_NEW handle
> with explicit access/share/NULL template, final/reparse/regular and handle identity,
> and real native create/close proof; no IO, no delete. D01a3a2 owns bounded ≤256 read,
> partial/full write+FlushFileBuffers, identity re-open, handle disposition delete and
> successor/no-residue proof; no Guard/policy. D01a3b now depends on D01a3a2. D01b
> depends on D01a3b. The CREATE_NEW decision is preserved. No passing evidence is
> inherited by D01a3a1 or D01a3a2. Tasks remain unchecked. No source, tests, progress,
> or delivery.

**D01a3b — Fallback policy and integration.**

Depends on D01a3a2. Private typed `ConfigLease` unifies mutex (primary) and marker
(fallback) ownership; one shared `DeadlineContext` serves both D01a3b and D01b.
Fallback only on `guard_acquisition_failed`; retry/contention under the shared
deadline; decode/owner predicate; conservative busy rules — empty, partial, malformed,
oversize, or unverifiable marker content and own-process markers refuse conservatively
as sanitized `config-lock-busy` and are never reclaimed (manual cleanup may be needed
after a pre-write crash). Only `ProcessTokenMissing` or a returned token mismatch
permits reclaim; `ProcessTokenUnprovable` or an equal token refuses. Cleanup failure
maps to `config-lock-release-failed`. One shared five-second deadline is checked on
every Guard and marker retry; no fallback on `guard_wait_timeout`. Fixed existing
parent directory, no creation. Race tests clean exact residues. Target ≤280 changed
lines and one rollback boundary.

**D01b — Immutable config snapshot and assist wiring.**

Depends on D01a3b. Uses the one shared `DeadlineContext` from D01a3b. Safe parent
tri-state, handle-bound fstat read, exactly-once validation under the owned lease,
deeply immutable diagnostic/provider state, explicit lease lifetime, preserved
absent/unsafe/S08 behavior, setup-assist wiring, focused snapshot/protocol tests.
Target ≤350 changed lines and one rollback boundary.

The fixed config path is `%LOCALAPPDATA%\yasb-limitora\config.json`. If the fixed config
parent directory (`%LOCALAPPDATA%\yasb-limitora\`) does not exist, return `config-absent`
before any lock acquisition and do not create the state root. The file-level fallback
marker uses one fixed literal name (`yasb-limitora.lock`) under the verified existing
non-reparse parent directory; D01 invents no caller-supplied path.

```
1. resolve      path = %LOCALAPPDATA%\yasb-limitora\config.json (fixed; no override invented)
2. pre-check    if the fixed config parent directory is absent -> return `config-absent`;
                do not create the state root; no lock is acquired
3. acquire      [D01a1/D01a2a/D01a2b/D01a3a1/D01a3a2/D01a3b] single-writer lock with a 5-second bounded wait:
                  primary:   [D01a1] Guard's SID/path-derived `Global\` named mutex,
                             context-managed lease keyed by exact fixed config.json path,
                             retry Guard's 250ms waits against one 5-second DeadlineContext
                  marker:    [D01a2a] canonical UTF-8 JSON marker with sorted keys,
                             no whitespace, 256-byte preparse max, and one sanitized
                             validation error; deterministic roundtrip; zero file I/O
                  identity:  [D01a2b] Win32 process-identity token via reusable safe
                             primitive; CloseHandle failure/unavailability is
                             unprovable; no acquisition/reclaim/unlink in this sub-unit
                  fallback:  [D01a3a1/D01a3a2/D01a3b] permitted ONLY for `guard_acquisition_failed`
                             (native mutex unavailable); [D01a3a1] verified parent hold/
                             non-reparse/final identity; correct Win32 CreateFileW CREATE_NEW
                             handle with explicit DELETE+read/write+attributes
                             access, FILE_SHARE_DELETE compatibility, and NULL template;
                             verify leaf final path, reparse status, regular-file status, and
                             handle identity after create; reuse repo-validated
                             FILETIME/BY_HANDLE_FILE_INFORMATION/native helpers from
                             _native_state_cleanup.py; at least one real Windows test;
                             real native create/close proof; no IO, no delete;
                             [D01a3a2] bounded ≤256 read; partial/full write+
                             FlushFileBuffers through same acquired handle; identity
                             re-open before delete; handle disposition delete and
                             successor/no-residue proof; low-level sanitized errors;
                             fixed literal name `yasb-limitora.lock`
                             under fixed existing parent (no creation); marker records
                             bounded PID/process-identity ownership via D01a2a/D01a2b's
                             codec; [D01a3b] private typed `ConfigLease` unifies
                             mutex/marker ownership; one shared DeadlineContext;
                             decode/owner predicate; conservative busy rules — empty/
                             partial/malformed/oversize/unverifiable and own-process
                             marker refuse conservatively as sanitized `config-lock-busy`
                             and are never reclaimed (manual cleanup may be needed
                             after pre-write crash); only ProcessTokenMissing or
                             returned token mismatch permits reclaim;
                             ProcessTokenUnprovable/equal token refuses
                  timeout:   [D01a1] `guard_wait_timeout` maps directly to sanitized
                             `config-lock-busy` and never tries a separate lock domain
                             or the file fallback; one shared five-second deadline
                             checked on every Guard and marker retry; no fallback on
                             guard_wait_timeout
                  cleanup:   [D01a3a2] handle-derived identity and identity re-open before
                             delete; handle-bound deletion never removes successor;
                             low-level sanitized errors; [D01a3b] cleanup failure maps
                             to `config-lock-release-failed`; race tests clean exact
                             residues
4. read         [D01b] original bytes via handle-bound fstat, or record "absent";
                safe parent tri-state (present/absent/unsafe)
5. validate     [D01b] the WHOLE document against the runtime contract exactly once
                under the lock using `validate_config_document`: ordered parse with
                duplicate-key and non-finite rejection (same discipline as
                cli.py::_load_explicit), then LocalConfig.from_mapping plus
                credential-key rejection.
                failure  -> Gate 1 reject-and-preserve: release the lock, report, done.
                            The S08 byte-identity contract is preserved: the original
                            file remains byte-for-byte untouched.
                "absent" -> nothing to validate; record present/absent state
6. snapshot     [D01b] yield a deeply immutable typed snapshot containing:
                  - original bytes (or absent marker)
                  - the existing validator's returned LocalConfig (or absent)
                  - immutable provider-error keys (if any)
                  - present/absent state
                The snapshot is valid only while the D01a lease remains owned.
                D02 must consume the snapshot inside that same ownership scope.
                Lock release occurs in guaranteed cleanup after the consumer
                finishes (or immediately after D01a-only inspection/refusal
                until D01b exists). Never release before D02 consumes the
                snapshot. D01a and D01b perform no backup, merge, or write.
```

**D02 — Owned-field merge, atomic write, and verification** (consumes the D01 snapshot):

```
7. backup       if present -> backups\config.<UTC-timestamp>.json (bounded to 5)
                if absent -> record "create" as the recovery point (recovery = delete)
8. merge        apply only the explicitly selected owned paths from the request; keep key
                order via an ordered mapping; leave every other contract-valid field as parsed
9. validate     the final merged document, whole, against the runtime contract BEFORE writing
10. write       temp file in the same directory, flush, os.fsync, os.replace
11. verify      re-read, re-parse, re-validate; confirm owned paths equal the request and
                unowned fields equal the original
12. release     lock in guaranteed cleanup (context-manager exit); report success
on any failure at 7-11: restore from the backup with os.replace (or delete for "create"),
                        re-verify, remove the temp file, report the reason code. A failed
                        update leaves the prior configuration restored or authoritative —
                        never a partial or malformed replacement.
```

The backup deliberately sits **after** the D01 validation gate (in D02): an invalid
document receives no backup, no merge, no write, no normalization, and no reserialization
at all. Only a document that passes the runtime contract is ever backed up and merged.

| Alternative | Verdict | Reason |
| --- | --- | --- |
| Preserve unknown fields, commit the merge, and warn that the runtime will reject the document | Rejected | It commits a document the current runtime contract rejects. The corrected configuration-assistance spec requires reject-and-preserve instead: an invalid existing config abandons the optional operation and is never mutated |
| Delete or repair unknown fields so the runtime accepts the result | Rejected | Repair, normalization, and field-dropping on an invalid document are forbidden and would silently destroy user data |
| Loosen `_fields` to ignore unknown keys | Rejected | Reopens a fixed runtime contract and weakens a fail-closed boundary |
| Split validation: owned-projection shape/type checks gate the write; whole-document runtime acceptance is only a warning | Rejected | Same commit-an-invalid-document defect as the first row, and it gives the assist a second, weaker validator that can drift from `config.py` |

**Never auto-create.** The runtime continues to only select `config.json`; it never creates it.
The wizard is the sole creator, and only after explicit opt-in; a newly created document must
itself pass whole-document validation before the write. The state directory is created
only when the wizard actually writes.

### 4.4 No secrets and choice-only enabled state

| Rule | Design |
| --- | --- |
| Secret values are never read into the assist | Prerequisite checks test **key-name presence** in the effective environment only; the value is never fetched, never compared, never logged |
| No secret in argv | The request is fixed-name `request.json` inside the nonce-derived temp directory; argv carries only the sentinel. `_SECRET` argv rejection remains intact and is never bypassed |
| No secret in the result document | The assist output schema has no value-carrying field; it reports names, booleans, and reason codes |
| No secret in installer logs, evidence, or artifacts | The existing `Scan-Candidates`/`Assert-SafeScan` discipline from `windows-proof.yml` is applied to build logs, `rc-manifest.json`, the SBOM, assist output, and every committed evidence file |
| Enabled state source | `enabled` is written **only** from an explicit selection in the request. There is no code path that derives it from discovery, from secret presence, or from prerequisite availability |
| Missing secret or prerequisite | Produces a `warnings[]` entry naming the missing requirement. It does not change `enabled`, does not block the commit, and does not disable the provider |
| Provider selection overrides readiness warnings | **Normative and preserved:** if the user explicitly selects a provider state and a required secret or external prerequisite is missing, the commit succeeds, `enabled` reflects the selection, and the wizard warns that the provider may not work until the requirement is met. Warnings never veto a selection |
| Warnings are not the contract gate | Readiness warnings (missing secrets/prerequisites) are advisory and never block a commit of a runtime-valid document. Runtime-contract invalidity is a gate: it abandons the optional operation before any write (§4.3). The two are never conflated |
| No explicit selection | `enabled` is left exactly as found (or absent for a new document). Discovery outcome, secret presence, and prerequisite presence are all irrelevant to state |
| Provider logic ownership | The assist contains no authentication, transport, selection, or interpretation logic. It writes booleans, numbers, and a runner string. Limitora remains the owner |

## 5. YASB discovery and manual-close design

### 5.1 Discovery outcomes

Discovery is read-only, time-bounded by the existing deadline discipline, and can never fail the
installation. Probe errors/timeouts that prevent a safe classification yield `inconclusive`; an
absent `.env` under an otherwise resolved safe config home is a complete result, not a partial error.

Ordered probes:

1. `HKCU` and `HKLM` `...\CurrentVersion\Uninstall\*` for a display name matching YASB →
   `InstallLocation`.
2. Known directories: `%LOCALAPPDATA%\Programs\yasb`, `%PROGRAMFILES%\YASB`,
   `%PROGRAMFILES(X86)%\YASB`.
3. Process snapshot for a YASB process (§5.2).
4. Resolve the configuration home without reading `.env`:
   - if the inherited OS environment contains `YASB_CONFIG_HOME`, it is authoritative only when
     non-empty and an absolute normalized local Windows path that contains no device/UNC prefix or
     `..` segment, is not a drive/root directory, and whose existing components are directories and
     not reparse points;
   - an explicitly present but empty or unsafe `YASB_CONFIG_HOME` makes configuration discovery
     `inconclusive`; never fall back and write to a different directory that YASB did not select;
   - only when `YASB_CONFIG_HOME` is absent, resolve `%USERPROFILE%\.config\yasb` from the inherited
     OS `USERPROFILE` using the same safety checks; failure leaves the config home unresolved/unsafe;
   - never inspect or parse `.env`, YAML, CSS, or any YASB content to discover the config home.
5. After the home is resolved, inspect only filesystem metadata for `<home>\.env` to classify it
   as `present`, `absent-creatable`, or `unsafe/unreadable`; discovery neither opens/parses its
   contents nor creates any directory or file.

| Outcome | Condition | Installer behavior |
| --- | --- | --- |
| `detected` | Install evidence and a safe configuration home are resolved; `.env` is either `present` or `absent-creatable` | Offer consented `.env` assistance; when absent, identify it as a new file that will be created only after consent; report only the S04c-adopted invocation behavior; G2a selection evidence is not final acceptance, and only G2b may accept the installed candidate (§6) |
| `absent` | No install evidence from any install/process probe | Install succeeds; skip YASB-specific integration; inform "YASB was not found" |
| `inconclusive` | Install evidence exists but the config home is unresolved/unsafe, `.env` is unsafe/unreadable, or a required probe errored/timed out | Install succeeds; skip or defer integration; inform "detection was inconclusive" |

Absent versus inconclusive is distinguished first by **whether any install evidence was found**.
Within `detected`, `.env` presence is a separate field: absence means a creatable consented target,
not failed discovery. This avoids elevating, scanning the filesystem broadly, or using a file to
discover its own parent.

Discovery never creates application state, never edits YAML or CSS, never writes to a YASB
directory, and never treats a discovery failure as an install failure. Only the later explicitly
consented `env-block-apply` operation may create or modify the resolved `.env`.

### 5.2 Running-YASB manual-close gate

Applies at install, upgrade, and uninstall, before any file mutation.

```
probe -> yasb process present?
  no  -> continue
  yes -> modal page:
           "YASB is currently running. Close YASB manually, then choose Retry.
            yasb-limitora will never close, restart, or manage YASB for you."
           [ Retry ]  re-probe (bounded; each Retry is a fresh probe)
           [ Cancel ] abort; prior installation and all state remain intact
         no third option, no timeout that auto-continues, no "continue anyway"
```

| Concern | Design |
| --- | --- |
| Detection method | Process snapshot via the repository's existing native Win32 discipline (`CreateToolhelp32Snapshot` through `ctypes`), matching the fail-closed style of `isolation/windows_job.py`. No WMI dependency, no external binary |
| Match rule | Exact executable name match against a small known set; no substring matching that could catch an unrelated process |
| Never manage lifecycle | No `TerminateProcess`, no `CloseMainWindow`, no service control, no restart, no install or uninstall of YASB. The assist has no code path that sends a signal to a foreign process |
| Cancellation | `Cancel` aborts before staging; nothing is copied, renamed, or deleted; the report says the operation was cancelled by the user |
| Stale detection | Every `Retry` re-probes from scratch; the result is never cached across the prompt. If the snapshot itself fails, the outcome is `inconclusive` and the user is told detection failed rather than being told YASB is closed |
| Failed continuation | If the user retries, the probe clears, and the swap then fails on a lock, the rollback in §3.3 applies and the prior install is restored |
| Own process | A running `yasb-limitora.exe` (a YASB-spawned child) triggers the same manual-only prompt. It is never killed either, so one rule covers both cases |
| Unbounded waiting | Retry count is bounded only by the user; there is no auto-continue timer, because auto-continue would proceed into a locked-file failure |

### 5.3 No lifecycle ownership

The product never stops, restarts, installs, uninstalls, patches, configures beyond the consented
`.env` block, or otherwise controls YASB. Concretely: the assist has no process-control API
surface at all; discovery is read-only; the only YASB-directed write in the entire design is the
commented block between markers in `.env`, and only after explicit consent. YASB restart after a
PATH change is always a **user** action described in documentation, never a product action.

## 6. No-PATH/spaced-path spike decision table

### 6.1 Bounded candidate mechanisms

The spike runs against the **real release-target YASB installation**, with its actual `run_cmd`
handling, PATH unchanged, and `use_shell` as stated. Exploration records that upstream YASB
currently splits `run_cmd` with `.split(" ")` and that upstream issue #815 remains open; the
archived split evidence is pinned-v2.0.5 historical, so the release target's behavior must be
re-observed rather than assumed.

| ID | Mechanism | `run_cmd` | `use_shell` | Needs PATH | Role |
| --- | --- | --- | --- | --- | --- |
| M1 | Bare name, PATH task enabled | `yasb-limitora` | `false` | Yes | Control: proves the convenience task works; **cannot** be the integration path |
| M2 | Bare name, PATH unchanged | `yasb-limitora` | `false` | No | Control: expected to fail; proves the no-PATH requirement is real |
| M3 | Full path, resolved path contains **no** space | `<progdir>\yasb-limitora.exe` | `false` | No | Primary candidate |
| M4 | Quoted full path, resolved path **contains a space** | `"<spaced>\yasb-limitora.exe"` | `false` | No | Must be run and recorded; expected to fail under `split(" ")` |
| M5 | Unquoted full path with a space | `<spaced>\yasb-limitora.exe` | `false` | No | Must be run and recorded; expected to fail |
| M6 | 8.3 short-path alias of the spaced path (space-free) | `<shortpath>\yasb-limitor.exe` or generated short name | `false` | No | Rescue candidate when the profile path contains a space; requires short-name generation enabled on the volume |
| M7 | Shell-enabled spaced path | any spaced form | `true` | No | **Diagnostic only.** Run to confirm the parser is the cause; the result is recorded and **never counts as a pass** |
| M8 | Launcher in a space-free directory reachable without elevation | `<space-free>\yasb-limitora.exe` | `false` | No | Rescue candidate; viable only if such a directory exists without elevation or a machine-wide write |

**Evaluated and rejected discovery mechanisms.** The following materially relevant Windows
executable-discovery mechanisms were explicitly evaluated and are rejected with recorded
dispositions rather than silence:

| ID | Mechanism | Disposition | Reason |
| --- | --- | --- | --- |
| M9 | Per-user drive alias: `SUBST` or `DefineDosDevice` mapping a space-free drive letter to the spaced program dir | **Rejected** | DOS-device mappings are per-session and non-persistent: they vanish at logoff/reboot, and nothing in a no-elevation install may register a logon task to recreate them without adding a durable mechanism with its own lifecycle. A chosen drive letter can collide with existing, removable, or network drives, and collision handling would be a guess. A `run_cmd` that depends on a letter that may not exist at widget-spawn time is exactly the silent environment dependence the fail-closed rule prohibits, and uninstall would own yet another cleanup surface. Reconsider only if release-target evidence demonstrates persistence, collision-freedom, and cleanup guarantees that current Windows behavior does not provide |
| M10 | `App Paths` registry entry (`HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\yasb-limitora.exe`) | **Rejected** | `App Paths` is consulted by `ShellExecute`, not by the bare-name `CreateProcess` resolution a no-shell spawn uses; honoring it would route discovery through a shell intermediary, which §6.2 evidence rule 7 forbids. It is also a second registry mutation surface with its own removal duty and no benefit without PATH |
| M11 | NTFS junction/symlink alias from a space-free location to the program dir | **Rejected** | Symlinks need a privilege the per-user model refuses; a junction needs a space-free user-writable parent (for example a drive root), which does not exist without elevation — the same structural constraint that makes M8 unguaranteed — and machine-wide writes are excluded by the proposal's non-goals |

**Scope statement.** The M1–M8 candidates plus the M9–M11 rejections cover the materially
relevant Windows executable-discovery mechanisms for a no-shell, per-user, no-PATH spawn:
PATH (M1/M2), literal absolute paths (M3–M5), 8.3 short names (M6), shell parsing (M7,
diagnostic only), a space-free relocated launcher (M8), DOS-device drive aliases (M9),
App Paths (M10), and reparse-point aliases (M11). Any mechanism not listed here would
require elevation, machine-wide writes, shell intermediation, or editing YASB — all
excluded by the proposal's non-goals. If the spike surfaces a materially different
mechanism, it must be added to this table with an explicit disposition before use; nothing
may be adopted silently outside these dispositions.

### 6.2 Exact two-checkpoint evidence and pass/fail language

G2 is one overall release gate with two distinct checkpoints. G2a and G2b use the same real
release-target YASB harness and evidence criteria, but their claims and artifact bindings differ.
Every mechanism execution at either checkpoint captures:

1. YASB version and installation path.
2. The exact `run_cmd` and `use_shell` values, quoted from the test YAML.
3. The widget rendering the expected label from a real run (screenshot, cropped, redacted).
4. **Rules 4–7 (observability):** live YASB evidence must bind the exact YAML `run_cmd`/`use_shell`,
   widget rendering, child argv (`argv[0]` = intended path, no extra tokens), and direct YASB→child
   relationship in one session. Passing mechanisms use `use_shell:false`; no cmd/powershell/pwsh/conhost
   may occur **between YASB and child**; ancestors above YASB are recorded but do not fail.
   Raw stdout (current selector-free JSON, no root `version`) and contract-matching exit may instead
   come from a complementary direct execution of the **verbatim same `run_cmd`**, `shell=false`,
   one-token argv, unchanged environment/PATH, immutably bound to the same complete PyInstaller
   onedir/exe/build-info. It supplies only stdout/exit, never YASB spawn/render/ancestry or YASB stdout
   interception. Missing/mismatched live or complementary binding fails; equivalent paths, different
   short spellings, or merely matching exe hashes do not qualify.
8. The machine's PATH at test time, shown unchanged from before the arrangement or candidate was
   installed.
9. Secret-scan and redaction results before evidence retention.

A mechanism execution **fails** when any of these hold: the widget is empty or error-state; the
child command line shows the path split into multiple tokens; the run exits non-zero without a
valid document; stdout is not the current contract; the mechanism required `use_shell: true`; PATH
had to change; or any required evidence is absent.

**G2a feasibility/selection evidence** additionally records the S02 frozen-target digest, S04a
harness revision, every disposable/prototype M3/M6/M8 arrangement created for the run, and exactly one mechanism,
including its bounded machine-class behavior, selected for S04c. A G2a pass means only that
the selected arrangement is feasible against the real release-target YASB under the criteria above.
Prototype paths, aliases, launchers, and installer-shaped scaffolding are explicitly labeled
non-candidate and disposable. G2a evidence is full execution evidence, but it **must not** claim
that S04c has adopted the mechanism, that an installer can guarantee it, that any retained setup
candidate contains it, or that the `yasb-spaced-path` acceptance-ledger gate has passed. G2a is
`fail` when no permitted arrangement is feasible or selection evidence is incomplete, and `unrun`
when the external execution did not occur; either status blocks S04c.

**G2b installed-candidate acceptance evidence** additionally records the selected build run ID,
`rc-manifest.json` digest, retained `setup.exe` name and SHA-256, installed program identity/path,
and the G2a selection-evidence reference. It is collected only after installing those exact
retained candidate bytes. A G2b pass requires the real-YASB spaced-path/no-PATH proof to pass
against the actual S04c-adopted behavior, not against a prototype or manually substituted alias.
Only that candidate-bound G2b pass may set the acceptance ledger's `yasb-spaced-path` gate to
`pass`; its evidence references include G2b and the traced G2a selection record. G2b is `fail` on
any behavioral, evidence, or candidate-binding failure and `unrun` if the installed-candidate
execution did not occur. Neither status can be promoted to pass by G2a evidence.

### 6.3 Fail-closed rule and non-circular adoption order

```
Overall release-blocking G2 gate:

  S02 frozen target + S04a harness
            │
            ▼
  G2a FEASIBILITY/SELECTION
    PASS  <=> a permitted M3/M6/M8 mechanism passes on the real release target
              with PATH unchanged and use_shell false, and exactly one mechanism is selected
    FAIL/UNRUN -> no S04c adoption; publication remains blocked
            │ pass (selection evidence only)
            ▼
  static installer path/identity contract, when the selection depends on it
            │
            ▼
  S04c BOUNDED ADOPTION
    encode exactly the selected mechanism and only its deliberate paired example/test change
            │
            ▼
  later installer/build slices -> exact retained setup candidate + manifest identity
            │
            ▼
  G2b INSTALLED-CANDIDATE CONFIRMATION
    PASS  <=> install the exact retained candidate and repeat the real-YASB
              spaced-path/no-PATH proof against the actual adopted behavior,
              satisfying every §6.2 criterion and candidate-identity binding
    FAIL/UNRUN -> overall G2 is not pass; publication is blocked
            │ pass only
            ▼
  overall G2 PASS -> yasb-spaced-path ledger acceptance may be pass -> publication may proceed
```

If the release-target profile path contains no space, M3 may pass for that machine class only. M4
and M5 must still be executed and recorded, and G2a cannot select an M3-only release arrangement as
coverage for a spaced-path machine class. The installer must not silently depend on a space-free
username: under the selected arrangement it computes the resolved invocation path at install time
and, if that path contains a space and no G2a-selected M6/M8 behavior is available, it must (a)
still install successfully, (b) skip writing any integration command, (c) inform the user that
automatic YASB command integration is unavailable on this machine, and (d) report that machine
class as unproven, not passed. Such an unproven required class prevents G2b from passing.

If a spaced candidate path has neither a selected M6 nor M8 behavior that passes, G2a fails before
adoption or G2b fails against the installed candidate, depending on where the defect is observed.
In either case publication is blocked. Prohibited substitutions remain `use_shell: true`, making
the PATH task a hidden prerequisite, documenting M1 as the integration path, shipping an example
that only works on space-free machines, editing YASB's parser, or shipping widget code.

M6 has a real limitation that must be recorded honestly: 8.3 short-name generation can be disabled
per volume, in which case M6 is unavailable and selection falls to M8 or fails. M8 has no guaranteed
space-free, user-writable, non-elevated location on Windows, so it may be structurally unavailable.
G2a may establish feasibility for a concrete arrangement but cannot turn either limitation into an
installer guarantee; only G2b can accept the actual behavior installed from a bound candidate.

**S04 ↔ overall-G2 implementation/adoption seam.**
`examples/customwidget/customwidget.yaml` currently uses a bare `run_cmd: "yasb-limitora"` with
`use_shell: false`, and `tests/test_customwidget_examples.py` asserts that exact string appears
twice plus `use_shell: false` and the absence of shell metacharacters. Boundary 4 is therefore
sequenced into five non-overlapping units:

1. **S04a — pre-selection construction:** after S02 supplies the frozen target, implement read-only
   discovery, process probing, PATH support, and `spacepath_spike.ps1` as a harness capable of
   exercising M1-M8. Unit tests may prove classification and evidence-capture shape, but this slice
   leaves the shipped example and its pinned test unchanged and records no adopted mechanism.
2. **G2a — feasibility/selection checkpoint:** run that harness against the real release-target YASB,
   using disposable/prototype M3/M6/M8 arrangements as needed, and retain all §6.2 selection
   evidence. Only a G2a pass selects what S04c may encode; it does not accept a release candidate or
   prove installer guaranteeability.
3. **S04c — bounded adoption:** only after G2a passes, and after the static installer path/identity
   contract exists when the selection relies on it, encode exactly the selected mechanism. If that
   mechanism requires an example change, update `examples/customwidget/customwidget.yaml` and
   `tests/test_customwidget_examples.py` together with the recorded rationale. The example keeps
   `use_shell: false`, a single literal command, and no shell metacharacters. No adoption occurs when
   G2a is `fail` or `unrun`.
4. **Integrated candidate construction:** the later installer/build slices incorporate S04c and
   produce one exact retained `setup.exe` candidate with immutable manifest identity. Prototype G2a
   bytes or arrangements are not promoted.
5. **G2b — installed-candidate confirmation:** install that exact candidate and repeat the real-YASB
   spaced-path/no-PATH proof against its actual adopted behavior. Only G2b pass closes overall G2 for
   the acceptance ledger and publication.

A G2b `fail` or `unrun` blocks publication and cannot silently reopen S04c or substitute another
mechanism under the same candidate identity. Selecting a different mechanism requires returning to
G2a, recording a new selection, performing a new bounded S04c adoption, and producing a new retained
candidate identity before G2b runs again.

## 7. CI internal-RC custody and artifact promotion

### 7.1 Internal RC state

Three workflows separate candidate construction, acceptance, and byte promotion:

| Workflow | Trigger | Produces |
| --- | --- | --- |
| `.github/workflows/release-build.yml` | `workflow_dispatch` with the release commit, plus exact final-tag validation when applicable | Frozen bundle, `setup.exe`, immutable `rc-manifest.json`, `SHA256SUMS.txt`, `sbom.cdx.json`, `build-info.json`, and provenance attestation over the final artifact digest; uploads one immutable candidate artifact bundle and automated-check evidence |
| `.github/workflows/release-acceptance.yml` | `workflow_dispatch` selecting a completed build run after the candidate exists and available evidence has been collected | Reads the retained identity metadata, validates the candidate binding/evidence set, then emits a separate `rc-acceptance.json` Actions artifact; it never includes or repackages candidate files in that ledger artifact |
| `.github/workflows/release-publish.yml` | `workflow_dispatch` selecting both a build run and an acceptance run, gated by the protected `release-candidate` environment with required reviewers | Downloads the two separately custodied artifacts, verifies their binding, attestation, and all blocking pre-publication statuses, then publishes exact retained candidate bytes |

Internal RC representation:

- **No git tag and no `-rc` version.** The candidate's product version is `0.2.0` from the first
  build; "RC" describes CI custody only.
- `rc-manifest.json` is immutable **build-time identity/integrity metadata**, not an acceptance
  record. It contains only `schema: gentle-ai.yasb-limitora.release-manifest/v1`, `version`,
  `source_commit`, `source_date_epoch`, exact `tools`, `artifacts[]` (`name`, `size`, `sha256`), the
  `sbom` (`name`, `sha256`), and the bound `build_info` digest. It has no gate status, approval,
  evidence-reference, mutable custody-location, or post-publication field.
- After the candidate exists, `.github/workflows/release-acceptance.yml` creates
  `rc-acceptance.json` with schema `gentle-ai.yasb-limitora.release-acceptance/v1`. It contains
  `build_run_id`, `acceptance_run_id`, `created_at`, `manifest: {name, sha256}`, a copied
  `artifacts[]: {name, sha256}` binding, and `gates`, an object keyed by the stable pre-publication
  gate IDs in §8.1. Each gate is exactly `{status: pass|fail|unrun, reason_code, evidence_refs}`.
  `pass` requires `reason_code: null` plus at least one content-addressed or immutable-workflow
  evidence reference; `fail`/`unrun` requires a bounded non-empty reason code and keeps any truthful
  evidence references without being coerced to pass. For `yasb-spaced-path`, `pass` specifically
  requires G2b evidence bound to this build run, manifest digest, and setup hash, with a reference
  to the G2a selection record; G2a evidence alone cannot set that ledger status to `pass`.
- Candidate custody and acceptance custody are separate `actions/upload-artifact` records, each
  with `retention-days: 90`, plus separate checksummed objects in the private release cache. The
  acceptance artifact contains the ledger only; creating it or a later ledger run never repacks the
  candidate, changes candidate bytes, or edits `rc-manifest.json`. Publish selects explicit build
  and acceptance run IDs rather than a mutable "latest" pointer.
- The post-publication closeout check is excluded from `rc-acceptance.json`; it has its own evidence
  under the closeout section of `SMOKE-0.2.0.md` (§8.1).

### 7.2 Hashes, manifest, acceptance ledger, SBOM, provenance

| Evidence | Format | Generation |
| --- | --- | --- |
| Integrity hashes | `SHA256SUMS.txt`, coreutils style (`<hex>  <filename>`) | `scripts/make_release_manifest.py` over every candidate artifact |
| Immutable manifest | `rc-manifest.json`, release-manifest/v1 schema above | Build workflow only; deterministic key order; no acceptance state or build-machine absolute paths |
| Acceptance ledger | `rc-acceptance.json`, release-acceptance/v1 schema above | Acceptance workflow only, after candidate creation; binds build run ID, manifest digest, and artifact hashes to pre-publication statuses/evidence without changing the candidate bundle |
| SBOM | CycloneDX JSON, `sbom.cdx.json`, with its digest bound by the manifest | Generated from the **build environment's** resolved dependency set (`pip freeze` captured at build time inside the pinned build job), not from a developer environment, so it describes the bundle |
| Provenance / attestation | SLSA-style build provenance via `actions/attest-build-provenance` over the final candidate artifact digest | Build workflow after final hashing; acceptance ledger references the immutable attestation record, and publish verifies its subject digest before release creation |
| Build record | `build-info.json` inside `_internal/`, digest bound by the manifest | Version, commit SHA, Python patch, PyInstaller version, limitora version, `SOURCE_DATE_EPOCH` |
| Secret scan | Existing `Scan-Candidates`/`Assert-SafeScan` PowerShell functions, plus scans over manifest, ledger, SBOM, assist output, and all referenced evidence | Build, acceptance, and publish jobs; any hit is a blocking pre-publication failure |

### 7.3 Promotion and unsigned disclosure

**Promotion is by download, never by rebuild or repack.**

```
publish job:
  1. resolve the explicitly selected build run ID and acceptance run ID
  2. download the immutable candidate bundle and separately custodied rc-acceptance.json
  3. recompute the digest of rc-manifest.json and every candidate artifact/SBOM/build record
  4. assert candidate bytes match rc-manifest.json, including the SBOM/build-info bindings,
     and verify the retained provenance attestation subject is the same setup.exe digest
  5. assert ledger.build_run_id == selected build run ID
  6. assert ledger.manifest.sha256 == recomputed manifest digest
     and ledger.artifacts exactly equal the manifest artifact name/hash set
  7. validate the strict ledger schema and exact required pre-publication gate-ID set
  8. require every blocking pre-publication gate status to be "pass" with valid evidence refs
     - for yasb-spaced-path, require candidate-bound G2b evidence; G2a selection alone is insufficient
     - any "fail"  -> refuse, quarantine, report
     - any "unrun" -> refuse and report the gate as outstanding (never a pass)
  9. require the ledger's build-integrity evidence to reference that verified attestation
 10. publish the identical retained setup.exe bytes and attach the immutable manifest, hashes,
     SBOM, acceptance ledger, and attestation; generate the release body without rewriting them
```

Byte identity is guaranteed by construction: the publish job never invokes PyInstaller or ISCC,
never updates `rc-manifest.json`, and never repacks the candidate. Acceptance can evolve only by a
new separately custodied ledger run bound to the same immutable candidate; it cannot alter identity.

Unsigned disclosure, in fixed wording in both `RELEASE_NOTES.md` and the release body:

- The 0.2.0 `setup.exe` is **not Authenticode-signed**.
- Windows SmartScreen may show "Windows protected your PC"; the user chooses **More info → Run
  anyway**.
- The published SHA-256 lets a user verify the download with
  `Get-FileHash -Algorithm SHA256`.
- No code-signing assurance, publisher identity, or trust is implied. Signing is not required for
  0.2.0, and nothing in this release establishes signing-key custody for a future release.

## 8. Smoke matrix, evidence ownership, failure modes, security, migration, rollback

### 8.1 Smoke matrix and evidence ownership

The acceptance ledger's exact pre-publication gate-ID set is:
`build-integrity`, `source-full-suite`, `native-windows`, `frozen-runtime`, `clean-install`,
`installer-lifecycle`, `yasb-spaced-path`, `yasb-boundaries`, `configuration-assistance`,
`secret-scan`, and `representative-live-provider`. A gate may aggregate the related matrix rows
below, but each `pass` points to every constituent evidence item. `yasb-spaced-path` is `pass` only
from G2b's installed-candidate evidence, with its G2a selection trace; G2a by itself is not a ledger
acceptance. `post-publication-closeout` is intentionally **not** a ledger gate ID.

| Case | Evidence | Owner | Blocking |
| --- | --- | --- | --- |
| Clean Windows, no Python: install succeeds | Installer log, screenshot, `where python` empty | External manual | Yes |
| Frozen CLI produces the current contract | stdout JSON, exit code, stderr | External manual + `smoke_frozen.py` | Yes |
| Frozen helper relaunch works | Process-tree capture showing the sentinel child | External manual | Yes |
| Multiprocessing bootstrap under freeze | Run log with no bootstrap error | External manual | Yes |
| Job containment | Native proof of Job assignment | Native automated (`tests/test_windows_native_proof.py`) where supported | Yes |
| Deadlines honored | Timeout run with bounded duration | Native automated + external manual | Yes |
| Sanitized streams | No internal detail in stdout/stderr | Automated (existing suite) | Yes |
| No-descendant / no-orphan cleanup | Process-tree empty after completion and after timeout | Native automated + external manual | Yes |
| Optional PATH enabled: direct CLI works | New shell resolves `yasb-limitora` | External manual | Yes |
| Optional PATH disabled: YASB integration still works | G2b installed-candidate record bound to the retained setup hash, plus its G2a selection trace (§6) | External manual | Yes |
| PATH task unchecked by default | Installer screenshot | External manual | Yes |
| Install / reinstall / upgrade | Logs + state listing before and after | External manual | Yes |
| Failed-upgrade rollback | Induced failure, prior install usable, state intact | External manual | Yes |
| Uninstall default preserves state | State listing after uninstall | External manual | Yes |
| Uninstall with explicit cleanup deletes state | Confirmation screenshot + state listing | External manual | Yes |
| YASB present / absent / undetected messaging | Three installer summaries | External manual | Yes |
| YASB running → manual-close prompt, no lifecycle action | Screenshot; process list showing YASB still running after cancel | External manual | Yes |
| Consented `.env` block: commented, idempotent, no secret | Before/after bytes, second run shows no duplication | Automated (assist unit tests) + external manual confirmation | Yes |
| No YAML/CSS edit | File hashes of `config.yaml` and `styles.css` unchanged | External manual | Yes |
| Wizard safe-merge on runtime-valid config: backup, merge of explicit selections only, final whole-document validation, atomic write, rollback; invalid existing config: reject-and-preserve byte-identity, enumerated bounded errors, install continues | Assist unit tests + external manual run | Automated + external manual | Yes |
| Enabled state changes only by explicit selection; missing prereq warns but commits | Assist unit tests covering the override case | Automated | Yes |
| Artifact integrity and custody: manifest, ledger, SHA-256, SBOM, provenance | Immutable `rc-manifest.json`, separate bound `rc-acceptance.json`, `SHA256SUMS.txt`, `sbom.cdx.json`, attestation | CI automated | Yes, pre-publication |
| Secret scan clean across logs, evidence, artifacts | Scan output referenced by the ledger | CI automated | Yes, pre-publication |
| Internal RC without a public `-rc` tag | Tag list, build-run candidate custody, separate acceptance-run ledger | CI automated | Yes, pre-publication |
| Candidate-to-final byte identity | Publish-job manifest + ledger binding and hash-equality assertions | CI automated | Yes, pre-publication |
| Representative live supported-provider flow | Redacted run record referenced by the ledger | External manual | Yes, pre-publication |
| Post-publication clean-machine closeout check on published bytes | Install + run record on a clean machine after publication | External manual | **No — closeout only; never a publication gate or ledger entry** |
| Native Windows proof where the environment supports it | `python -m pytest -q --strict-markers tests/test_windows_native_proof.py` | CI automated | Yes where runnable; otherwise reported `unrun` |
| Full suite | `python -m pytest -q --strict-markers` | CI automated | Yes |

Evidence ownership and retention:

- `docs/release/0.2.0/evidence/` holds redacted logs and cropped screenshots, committed only after
  secret scanning.
- `docs/release/0.2.0/SMOKE-0.2.0.md` is the human-readable checklist of record: each
  pre-publication case is `pass`, `fail`, or `unrun (external)`, with a pointer to its evidence.
  No `unrun` case may be recorded as a pass.
- The separately custodied `rc-acceptance.json` mirrors only the blocking **pre-publication** cases
  so CI can enforce them mechanically. Its manifest digest and artifact hashes bind those statuses
  to one immutable build run; `rc-manifest.json` carries no status. For `yasb-spaced-path`, that
  bound status comes from G2b; the referenced G2a record explains selection but carries no
  candidate-acceptance status.
- The post-publication clean-machine closeout check is recorded in a distinct closeout section and
  evidence path after release creation. It is never copied into the pre-publication ledger. Failure
  keeps R11 closeout open and triggers a documented incident/rollback decision with truthful
  evidence; it cannot unpublish retroactively or rewrite prior approval, ledger status, hashes, or
  artifact identity.
- Screenshots are cropped to exclude any credential material, environment variable values, and
  unrelated user files. `.env` contents are never committed; only before/after **hashes** and the
  managed-block region are recorded.
- Environment availability (which clean machines, which real-YASB versions, which live provider)
  is recorded in `SMOKE-0.2.0.md` at the start of execution, so an unavailable environment is
  visible as a gap rather than discovered at closeout.

### 8.2 Failure modes

| Failure mode | Detection | Response |
| --- | --- | --- |
| Frozen bundle breaks helper relaunch, multiprocessing, or Job cleanup | Clean no-Python frozen smoke; process-tree capture | Block publication; treat as a packaging defect, not a source defect |
| Missing hidden import surfaces only on a clean machine | Frozen smoke on a machine with no Python | Add the explicit collection; re-run the whole matrix, not just the failing case |
| Antivirus flags the unsigned frozen exe | Clean-machine install; SmartScreen record | Disclose; do not disable AV; do not switch to onefile to dodge it |
| User PATH corruption | Assist unit tests on verbatim string surgery; manual PATH before/after capture | Refuse to rewrite PATH from a parsed list; removal uses the recorded exact element |
| Accidental state deletion | Path-safety/reparse unit tests; uninstall smoke with state listing | Cleanup only on affirmative `YES`; request supplies no path; deletion only of the independently resolved literal state root; result survives in temp transport |
| `.env` corruption or duplication | Byte-level before/after comparison; idempotence test | Marker-delimited region only; refuse on malformed markers; restore from backup |
| Wizard mutates or commits an invalid existing config | Byte-identity and enumerated-error assertions in assist unit tests | Whole-document validation gates before any backup/temp/write (§4.3 Gate 1); the failure is nonfatal to the install |
| Registration fails after the swap committed (canonical dir occupied) | Pascal step exit codes | Reverse-swap with quarantine ordering (§3.3 step 6); captured registry values restored; `rollback-incomplete` reported when a rename is blocked |
| No feasible spaced-path arrangement at G2a | G2a real-target prototype/disposable evidence (§6) | Fail closed; do not run S04c or adopt a mechanism; publication remains blocked |
| Adopted spaced-path behavior or candidate binding fails at G2b | G2b run against the installed retained candidate (§6) | Block publication; do not substitute a mechanism under the same identity; return to G2a/S04c and build a new candidate identity |
| YASB running locks program files | Preflight probe; rename failure | Manual-close prompt; abort with prior install intact |
| SmartScreen blocks a user | Disclosure record | Documented workaround; no implied trust |
| Candidate, manifest, or ledger binding drift | Publish-job digest and build-run binding checks | Refuse to publish; rebuild is a new candidate, and a corrected acceptance record is a new separately custodied ledger run |
| Live-provider evidence unavailable or unsafe | Matrix `unrun` state | Report `unrun`; never substitute a mocked provider for the live gate |
| Secret leaks into evidence | Secret scan gate | Fail the job; purge and re-collect the evidence |
| Stale `.old` program directory confuses a later upgrade | Preflight detection | Reported; removed only after a successful swap |
| Post-publication clean-machine closeout check fails | Closeout run against published bytes | Keep R11 closeout open; retain truthful failure evidence; trigger incident triage and an explicit rollback/follow-up-release decision without rewriting the pre-publication ledger, approval, manifest, or hashes |

### 8.3 Security and privacy

- **Least privilege.** `PrivilegesRequired=lowest`; no `HKLM` write; no machine-wide directory; no
  elevation override. No design element requires elevation.
- **No secrets anywhere.** Credentials stay in YASB's startup-loaded `.env`/effective environment.
  They are never copied into `config.json`, installer arguments, assist request or result files,
  logs, JSON output, fixtures, reports, SBOM, or release artifacts. `_reject_credential_keys` is
  the single shared refusal rule.
- **Ownership.** Provider selection, authentication, transport, and interpretation remain in
  Limitora. The assist writes booleans, numbers, and a runner string and contains no provider
  logic.
- **No automatic YASB mutation.** No YAML, CSS, credential, argv, log, output, fixture, or report
  edit. The single permitted YASB write is the consented commented `.env` region.
- **Private helper.** The assist is internal and undocumented for users. It runs only when
  `setup.exe` set the per-run nonce environment value and wrote `request.json` in the independently
  derived per-user temp transport. The nonce is correlation and accidental-invocation protection,
  **not authorization**: a same-user caller already owns every affected file and registry location,
  so the security boundary is same-user OS ownership plus fail-closed schema, known-folder,
  no-reparse, path, and credential checks. No assist path uses elevated privilege.
- **No second stdout contract.** The public executable's stdout JSON contract remains the only
  one; assist results travel in the temp `result.json`, and the installer never parses the child's
  stdout.
- **Fail-closed defaults.** Every assist operation refuses on a malformed, over-size, missing, or
  reparse-point request/transport, an unknown operation or field, a missing/invalid nonce env value,
  an undecodable target file, a request-supplied path, or an unresolved/unsafe independently derived
  root.
- **Redaction reuse.** Assist output is sanitized with the same discipline as the runtime, so no
  internal detail, absolute user path, or environment value escapes into installer logs.
- **Unsigned honesty.** The disclosure states the artifact is unsigned and explains SmartScreen
  behavior without implying assurance.

### 8.4 Migration

`MIGRATION.md` and `RELEASE_NOTES.md` carry, in this order:

1. **0.2.0 is the first public release.** There is no 0.1.0 release, tag, or compatibility
   promise. Existing repository metadata that said `0.1.0` was a placeholder.
2. **The #137 contract break, stated plainly.** The selector-free current JSON document is the
   sole supported output. The root `version` field is removed. The version-selection surface
   (`--output-version` and its `=` form) is removed and is rejected as an invalid invocation with
   exit code `2`. There is no compatibility selector, no v1 fallback, and no second contract.
   Consumers that relied on the root `version` field must stop reading it.
3. **Installation migration.** Installation no longer needs Python or an editable checkout.
   Users with a prior `pip install -e .` must `pip uninstall yasb-limitora` to avoid two
   `yasb-limitora` entry points competing on PATH; PATH order would otherwise decide which one
   runs. YASB integration is unaffected because it uses the resolved full invocation path, not
   PATH.
4. **State migration.** `%LOCALAPPDATA%\yasb-limitora` config and cache carry over unchanged.
   Nothing is auto-created, auto-migrated, or auto-mutated by installing.
5. **PATH.** The User PATH task is optional and unchecked. Enabling it affects direct CLI
   convenience only and requires newly started processes; YASB integration does not require it.
6. **Unsigned release.** SmartScreen behavior and hash verification, as in §7.3.
7. **YASB.** YASB is never managed by this product. If YASB is running during a lifecycle
   operation, the user closes it manually.

### 8.5 Rollback

| Level | Mechanism | Boundary preserved |
| --- | --- | --- |
| Release candidate | `rc-acceptance.json` records every blocking pre-publication gate; any `fail` or `unrun` quarantines the separately retained candidate | No unvalidated publication; immutable manifest remains identity-only |
| Publication | Publish verifies candidate bytes against the manifest and ledger binding, then promotes only exact retained bytes; any mismatch aborts | Byte identity and acceptance custody remain distinct |
| Post-publication closeout | A failed clean-machine check leaves R11 open and triggers incident/rollback decision-making with preserved evidence | Publication is not retroactively blocked and approval/artifact identity are never rewritten |
| Installed program | Staged swap with an executable reverse-swap and quarantine; registry bookkeeping captured before mutation and restored on rollback; a staging failure leaves the prior install untouched | Prior install usable |
| Mutable state | Never deleted on any failure path; deletion only via the explicit default-negative uninstall choice | Default retention |
| `config.json` | Runtime-valid documents: timestamped backup plus restore-on-failure; `create` recovery deletes a newly created file. Invalid documents: reject-and-preserve — never backed up, merged, written, normalized, or reserialized by the assist | No malformed active config; an invalid user document is never touched |
| `.env` | Backup in the state root plus restore-on-failure; temp never promoted | YASB file intact |
| PATH | The exact appended element is recorded and removed precisely on uninstall | No residual or corrupted PATH |
| Source | Revert to the prior repository revision if release work is rejected | Must not introduce a portable ZIP, a dual JSON contract, automatic YASB lifecycle, or a broad config-edit fallback |

## 9. File-and-test map and capability boundaries

### 9.1 File map

| Path | Change | Why |
| --- | --- | --- |
| `src/yasb_limitora/__init__.py` | `__version__ = "0.2.0"` | Single version source |
| `pyproject.toml` | `dynamic = ["version"]` + attr mapping; scripts unchanged | Removes the duplicate version literal |
| `src/yasb_limitora/setup_assist.py` | New private module: sentinel dispatch, independently derived temp request/result transport, PATH, `.env`, `config.json` two-gate transaction, cleanup | All mutation logic in testable Python; destructive cleanup can report after deleting state |
| `src/yasb_limitora/discovery.py` | New read-only YASB discovery and process probe, including safe `YASB_CONFIG_HOME`/`%USERPROFILE%\.config\yasb` resolution | Three outcomes; absent `.env` is creatable after consent; install-independent |
| `src/yasb_limitora/cli.py` | Add the assist sentinel dispatch after `freeze_support()`, before `_config_path` | Mirrors the existing helper sentinel; keeps argv closed |
| `src/yasb_limitora/config.py` | No validation change; expose the whole-document validator and the owned-path and credential-pattern constants for assist reuse | The runtime contract is the assist's sole merge gate (§4.3) |
| `packaging/pyinstaller/yasb-limitora.spec` | New onedir spec | Frozen bundle |
| `packaging/pyinstaller/version_info.txt.in` | New version resource template | File properties match `0.2.0` |
| `packaging/inno/yasb-limitora.iss` | New per-user script: identity, tasks, staged swap, assist invocation | Sole public artifact |
| `scripts/build_frozen_bundle.py` | New | Build + `build-info.json` |
| `scripts/build_setup.py` | New | ISCC with `/D` defines from `__version__` |
| `scripts/make_release_manifest.py` | New | Immutable build identity/integrity manifest, hashes, SBOM binding; no acceptance status |
| `scripts/make_release_acceptance.py` | New | Strict separately custodied `rc-acceptance.json` bound to build run, manifest digest, artifact hashes, and pre-publication evidence |
| `scripts/smoke_frozen.py` | New | Frozen smoke driver |
| `scripts/spacepath_spike.ps1` | New | Spike harness and evidence capture |
| `.github/workflows/release-build.yml` | New | Immutable candidate build, manifest, hashes, SBOM, automated evidence |
| `.github/workflows/release-acceptance.yml` | New | Post-candidate acceptance ledger in separate custody; never repacks candidate |
| `.github/workflows/release-publish.yml` | New | Manifest/ledger/attestation verification, all-pass pre-publication enforcement, hash-equal promotion |
| `.github/workflows/windows-proof.yml` | Extend scan coverage to release evidence when present | Keeps the existing safe-log discipline |
| `docs/release/0.2.0/RELEASE_NOTES.md` | New | First-public + #137 + unsigned |
| `docs/release/0.2.0/MIGRATION.md` | New | Migration guidance |
| `docs/release/0.2.0/SMOKE-0.2.0.md` | New | Pre-publication matrix plus a distinctly labeled post-publication closeout section |
| `docs/release/0.2.0/evidence/` | New | Redacted evidence with separate pre-publication and post-publication closeout paths |
| `docs/roadmap.md` | R11 status and evidence pointers, respecting the Limitora-version guards | Roadmap accuracy |
| `README.md` | Point to `setup.exe` installation; keep the editable-checkout section clearly labeled as development-only | No active path implies a placeholder version |
| `examples/customwidget/*` | Untouched in S04a; eligible only in bounded S04c after G2a passes and selects a mechanism, with its test updated deliberately if adoption requires it | Pinned example cannot encode an expected, unproved mechanism; G2b later confirms the installed candidate |
| `tests/test_windows_only_documentation_contract.py` | Updated only if a guarded document must mention the product version | Deliberate, recorded change |
| `build/lib/yasb_limitora/__init__.py` | Removed from the working tree; not edited as source | Stale setuptools output still reporting placeholder `0.1.0`; must never be a build input |

### 9.2 Test map

| Test path | Proves |
| --- | --- |
| `tests/test_version_identity.py` (new) | `__version__ == "0.2.0"`; `pyproject` is dynamic and resolves to it; no active surface reports `0.1.0`; no `-rc` string in release metadata |
| `tests/test_setup_assist_protocol.py` (new) | Sentinel inert without nonce; exact nonce grammar; both sides independently derive the Local-AppData temp transport; exclusive creation; 64 KiB limits; strict request/result schemas; operations/choices only and no supplied path; malformed/unknown/duplicate fields refused; non-regular or reparse components refused; discovery creates no state root; `state-cleanup` result survives outside deleted state; installer removes only literal files and empty nonce dir; stdout carries no contract |
| `tests/test_setup_assist_path.py` (new) | Verbatim PATH append; no-op when already present; exact recorded-element removal; value type preserved; empty elements and `%VAR%` untouched; no System PATH access |
| `tests/test_setup_assist_env_block.py` (new) | Marker-delimited region only; every emitted line commented; idempotent on repeat; unrelated bytes preserved; BOM/newlines preserved; safe resolved home; absent `.env` created only after consent with create rollback; existing-file backup/restore; undecodable or reparse target refused; credential-like content refused; YAML/CSS untouched |
| `tests/test_setup_assist_config.py` (new) | Whole-document runtime-contract validation before any mutation; invalid existing config: reject-and-preserve with byte-identity of the original, no backup/temp/write/normalization/reserialization, bounded non-secret enumerated errors, and a nonfatal outcome code that lets the install continue; runtime-valid config: opt-in create, backup after the validation gate, ordered merge of explicit selections only, final whole-document validation before write, atomic replace, verify step, rollback on write and on validation failure; credential keys refused; no auto-create outside the wizard; single-writer lock |
| `tests/test_provider_enabled_state.py` (new) | Enabled state written only from explicit selection; discovery outcome, secret presence, and prerequisite presence never change it; missing requirement produces a warning; explicit selection commits despite a missing requirement |
| `tests/test_yasb_discovery.py` (new) | Safe non-empty `YASB_CONFIG_HOME` precedence; present empty/unsafe override is inconclusive with no fallback; absent override falls back to `%USERPROFILE%\.config\yasb`; `.env` never parsed for home discovery; present versus absent-creatable `.env`; unresolved/unsafe home remains distinct; `detected`/`absent`/`inconclusive`; read-only/bounded; no state, YAML, CSS, or lifecycle mutation |
| `tests/test_yasb_running_probe.py` (new) | Exact-name process matching; snapshot failure reports inconclusive rather than "closed"; no termination API is reachable |
| `tests/test_frozen_entry_order.py` (new) | Platform gate → `freeze_support()` → sentinel dispatch → argv validation; the assist and helper sentinels never reach `_config_path`; the public argv surface stays closed |
| `tests/test_packaging_spec.py` (new) | onedir; `console=True`; entry is `cli:main`; pinned PyInstaller range; UPX disabled; `limitora` submodule collection present; no repository docs/examples/fixtures in datas |
| `tests/test_inno_script.py` (new) | Textual invariants: `PrivilegesRequired=lowest`; stable identity/default path; PATH unchecked; no HKLM; lifecycle rollback; independently derived temp transport with no supplied target path; default-negative state cleanup followed by result read and exact transport removal; assist nonfatal post-commit; no YAML/CSS/termination call |
| `tests/test_release_manifest.py` (new) | Immutable manifest schema/order; version/source/tool identity; artifact size/hash and SBOM/build-info digest correctness; no gate/approval/evidence/custody/post-publication fields; no absolute build paths or secrets |
| `tests/test_release_acceptance.py` (new) | Ledger schema and exact gate IDs; build-run, manifest-digest, and artifact-hash binding; statuses limited to `pass`/`fail`/`unrun`; pass requires evidence refs/null reason while fail/unrun requires a reason; `yasb-spaced-path` pass requires candidate-bound G2b evidence plus its G2a trace and rejects G2a-only acceptance; post-publication closeout forbidden; publish refuses mismatch/fail/unrun without repacking candidate |
| `tests/test_windows_native_proof.py` (extend) | Job containment, deadlines, and no-orphan behavior against the frozen bundle where the environment supports it |
| `tests/test_customwidget_examples.py` (S04c only, after G2a) | If the G2a-selected mechanism requires a deliberate example change, it keeps a single literal path, `use_shell: false`, and no shell metacharacters; this test does not replace G2b candidate confirmation |

All new tests run under `python -m pytest -q --strict-markers`; native-executable cases carry the
existing `windows_native` marker.

### 9.3 Six capability boundaries (<=400 lines each)

These are capability boundaries for later task planning. They are not tasks, issue assignments,
or PR topology.

| # | Boundary | Primary files | Approximate size | Independence |
| --- | --- | --- | --- | --- |
| 1 | Release policy and version identity | `__init__.py`, `pyproject.toml`, `docs/release/0.2.0/RELEASE_NOTES.md`, `MIGRATION.md`, `README.md`, `docs/roadmap.md`, `tests/test_version_identity.py` | Small | Fully independent; unblocks 2, 3, 6 |
| 2 | Frozen build and provenance | `packaging/pyinstaller/*`, `scripts/build_frozen_bundle.py`, `scripts/make_release_manifest.py`, `tests/test_packaging_spec.py`, `tests/test_release_manifest.py` | Medium | Depends on 1 for the version; independent of 3-5 |
| 3 | Per-user installer lifecycle | `packaging/inno/yasb-limitora.iss`, `packaging/inno/SetupAssistant.isi`, `tests/test_inno_script.py` | Medium | Depends on 2 for the onedir input; the staged swap is testable as script invariants without 4 or 5; implementation is gated by the Inno staged-swap feasibility spike (§3.3, §10.2) |
| 4 | Discovery, two-checkpoint real-YASB gate, PATH, manual close | **S04a:** discovery, PATH/manual-close code/tests, and spike harness only. **G2a:** disposable/prototype real-target feasibility and selection evidence. **S04c:** bounded adoption of exactly the selection, including a paired example/test change only when required. **G2b:** installed-candidate confirmation evidence | Medium-large across five ordered units including candidate construction | S04a follows S02's frozen target; G2a depends on S02 + S04a; S04c depends on G2a pass and the static installer path/identity contract when needed; later installer/build slices produce the retained integrated candidate; G2b depends on that exact candidate and only its pass closes overall G2 |
| 5 | Configuration assistance | `src/yasb_limitora/setup_assist.py`, `cli.py` sentinel dispatch, `tests/test_setup_assist_protocol.py`, `_env_block.py`, `_config.py`, `test_provider_enabled_state.py`, `test_frozen_entry_order.py` | **Largest risk** | Depends on 1 only |
| 6 | Runtime and release acceptance | release build/acceptance/publish workflows, `make_release_acceptance.py`, `windows-proof.yml` extension, `SMOKE-0.2.0.md`, separately classified evidence, manifest/acceptance tests, native-proof extension | Medium | Depends on 2 and 3 for artifacts; consumes candidate-bound G2b evidence with its G2a selection trace plus boundary 5 evidence; post-publication closeout remains outside its pre-publication ledger |

Boundary 5 is the one most likely to exceed the budget. If it does, split it along the already
separate test files: **5a** protocol and `.env` block, **5b** `config.json` transaction and
enabled-state rules. That split follows a real seam (two different files, two different
transaction models) rather than an arbitrary line count.

## 10. Selected technical decisions and remaining gates

### 10.1 Selected decisions

| # | Decision | Rejected alternative | Key reason |
| --- | --- | --- | --- |
| D1 | Single version source: `__init__.__version__` with `pyproject` dynamic | Duplicate static version; tag-generated version; runtime `importlib.metadata` | The current duplicate is already a drift risk; frozen bundles lack reliable distribution metadata |
| D2 | No `--version` CLI flag; identity proven via metadata, version resource, registry, and `build-info.json` | Adding a version flag | The public argv surface is closed and locked by tests; adding a flag reopens a fixed contract |
| D3 | PyInstaller **onedir**, `console=True`, pinned `>=6,<7` | onefile; windowed build | The helper relaunches `sys.executable` and needs co-located dependencies; onefile failed the bounded frozen child path in recorded native evidence; YASB captures stdout |
| D4 | Reproducible-enough inputs plus promotion of retained bytes | Byte-reproducible rebuild requirement | Specs require validated bytes to be published, not rebuild equality; reproducibility tooling cannot be validated in this budget |
| D5 | Program root `%LOCALAPPDATA%\Programs\yasb-limitora`; state root `%LOCALAPPDATA%\yasb-limitora`; siblings, never nested | Program files inside the state root; machine-wide `Program Files` | Keeps the helper relaunch path out of mutable data and preserves the least-privilege per-user model |
| D6 | `PrivilegesRequired=lowest`, no elevation override | An optional elevated mode | An elevation path would change the per-user ownership model the proposal requires |
| D7 | **G1-proven:** pre-install evacuation moves the prior canonical directory to `.old` before Inno copies/registers against canonical, deletes `.old` only after success, and restores it on failure; the late failure hook uses the exact native new uninstaller as the smallest disposable harness correction before restoring `.old` and captured registry values/types | Post-install staged rename-swap; in-place overwrite; versioned side-by-side directories plus a pointer | The historical exact new `UninstallString` exited `0` but left the renamed canonical payload, disproving coherent Inno bookkeeping after the post-install rename; the fallback run proves native canonical bookkeeping and both uninstall paths |
| D8 | No separate Repair entry; same-version reinstall is the repair path (`NoRepair=1`) | A distinct Inno repair flow | The proposal left repair open; a third lifecycle state needs its own locked-file and rollback evidence the budget cannot support, and reinstall already achieves the outcome |
| D9 | Cleanup is an explicit default-negative `MB_YESNO`/`MB_DEFBUTTON2` confirmation at uninstall; only `YES` deletes | A custom checkbox page; an install-time pre-authorization | Inno has no uninstall checkbox page; pre-authorizing deletion of data that does not yet exist inverts the spec |
| D10 | A private setup-assist sentinel inside the same frozen exe, guarded by a per-run nonce env value that is correlation and accidental-invocation protection rather than authorization, owns all user-data and environment mutation; Inno Pascal owns only consent UI, the program-file transaction, and registry identity | Implementing `.env`, `config.json`, and PATH logic in Inno Pascal; a second frozen executable; treating the nonce as a security boundary | Pascal is untestable here and unsafe for UTF-8 JSON and PATH string surgery; one exe means one artifact to hash and one bundle to prove; the real security boundary is same-user OS ownership plus fail-closed checks |
| D11 | Assist transport is `%LOCALAPPDATA%\Temp\yasb-limitora-setup-assist\<nonce>\{request,result}.json`, independently derived from the Local AppData known folder plus fixed segments/validated nonce; requests contain operations/choices only; strict 64 KiB/schema/no-reparse rules apply; Inno removes it after reading | State-root transport; request-supplied target paths; argv; stdout; inherited-handle/pipe IPC | State-root transport self-destructs during cleanup and creates application state during discovery; the dedicated temp root survives state deletion while preserving the closed argv/stdout contracts and fail-closed path safety |
| D12 | Reject-and-preserve for an invalid existing config: only the optional configuration operation is abandoned, the original bytes stay untouched, bounded validation errors are enumerated, and install/upgrade continues | Deleting or repairing unknown fields; loosening `_fields`; preserving-and-committing with a warning; failing the install on the optional operation | The corrected spec forbids mutating or committing a document the runtime contract rejects, and forbids making the optional operation fatal to the program-file transaction |
| D13 | Whole-document runtime-contract validation is the single merge gate, applied to the existing document before any mutation and to the final merged document before the write | The former split design: an owned-projection gate with whole-document acceptance demoted to a warning | A split gate commits runtime-invalid documents successfully and gives the assist a second, weaker validator that can drift from `config.py` |
| D14 | `.env` assistance is a fully commented, marker-delimited, byte-preserving, idempotent region with backups stored in our state root | Writing active (uncommented) entries; backing up inside the YASB directory | Commented lines cannot change YASB behavior; backups in YASB's directory would add foreign files to a YASB-owned location |
| D15 | `enabled` comes only from explicit selection; readiness checks emit warnings and never change state | Deriving enabled state from discovery or prerequisite probing | Normative spec requirement: provider selection overrides prerequisite readiness warnings |
| D16 | Prerequisite checks test key-name presence only and never read a value | Reading secret values to validate them | Any value read is a potential leak path into logs, results, or evidence |
| D17 | Treat a present `YASB_CONFIG_HOME` as authoritative only when non-empty and safe; a present empty/unsafe value is inconclusive and never falls back. Only an absent variable selects `%USERPROFILE%\.config\yasb`; never parse `.env` for its home. A resolved home with absent `.env` is detected/creatable after consent | Assuming a Roaming-AppData config home; falling back after an explicit unsafe override; treating missing `.env` as inconclusive; using `.env` contents for discovery; failing install | Matches YASB's actual precedence while preventing assistance from writing to a directory YASB did not select |
| D18 | Manual-close prompt offers only Retry and Cancel, re-probes on every Retry, and has no process-control API | Auto-continue after a timeout; closing YASB for the user | Auto-continue proceeds into a locked-file failure; any termination violates the no-lifecycle-ownership invariant |
| D19 | Overall G2 has G2a feasibility/selection and G2b installed-candidate confirmation; only candidate-bound G2b pass closes the gate, and every counted M3/M6/M8 execution keeps PATH unchanged and `use_shell: false`; M7 is diagnostic only | One pre-adoption gate claiming installer guaranteeability; accepting `use_shell: true`; making PATH a prerequisite; per-user `SUBST`/DOS-device drive aliases (M9); App Paths (M10); reparse-point aliases (M11) | Separating selection from installed-candidate acceptance removes the S04↔G2 circularity while retaining the no-shell/no-PATH contract and the M9–M11 dispositions (§6) |
| D20 | If the profile path contains a space and no alias mechanism passes, fail closed and block publication; the installer still installs, skips integration, informs the user, and reports that machine class as unproven | Shipping an example that only works on space-free machines | Honesty about the gate is a release requirement; silent environment dependence is a defect |
| D21 | Boundary 4 is sequenced S02 + S04a → G2a selection → static installer path/identity contract when needed → S04c bounded adoption → later integrated candidate build → G2b candidate confirmation; only S04c may encode the selection or deliberately change the pinned example/test, and only G2b may accept it for publication | A single G2 pass before adoption; pre-G2a conditional adoption; silently switching mechanisms after G2b failure; letting the harness rewrite YAML | G2a can prove real-YASB feasibility without pretending the installer exists; G2b proves the actual retained candidate, and a different mechanism requires a new G2a/S04c/candidate identity cycle |
| D22 | RC is CI state only: immutable retained candidate bundle, separate bound acceptance ledger, and protected publish approval; no tag, no `-rc` version | A `-rc` git tag/version; mutable acceptance fields in the build manifest | Product identity stays final-version and immutable while external acceptance can be custodied separately |
| D23 | Promotion downloads candidate and acceptance artifacts by explicit run IDs, verifies manifest digest/artifact hash binding, and never builds or repacks | Rebuilding at publish time; trusting a mutable latest ledger; embedding acceptance into candidate bytes | Byte identity and acceptance custody are both mechanically verifiable without changing the validated candidate |
| D24 | `rc-manifest.json` is immutable release-manifest/v1 identity/integrity metadata; `rc-acceptance.json` is separate release-acceptance/v1 pre-publication status/evidence; SHA256SUMS, bound CycloneDX SBOM, attestation, and build-info complete the evidence set | One mutable manifest containing gates; an ad-hoc evidence mix | Separates what was built from whether external gates accepted it and prevents evidence updates from changing candidate identity |
| D25 | Fixed unsigned/SmartScreen disclosure wording in both release notes and the release body, with no implied assurance | Vague or omitted signing language | The spec requires disclosure without implying trust that is not present |
| D26 | Evidence is retained only after secret scanning and redaction; screenshots cropped; `.env` recorded by hash and managed-block region only | Committing raw logs and screenshots | Credentials must not reach the repository or release artifacts |
| D27 | Clean-machine execution of published bytes is a post-publication closeout check outside `rc-acceptance.json`; failure keeps R11 open and triggers incident/rollback decision-making without rewriting prior approval or identity | Calling it a publication gate or retroactively changing the acceptance ledger/manifest | Publication has already occurred; closeout must remain truthful without pretending it could have blocked the past event |

### 10.2 Remaining external and spike gates

These cannot be closed by design or by source-only work. Each is reported as `pass`, `fail`, or
`unrun (external)`; none may be recorded as a pass without its evidence.

| Gate | Type | Blocks |
| --- | --- | --- |
| **G2a — feasibility/selection:** after S02 + S04a, run M1-M8 against the real release-target YASB using disposable/prototype M3/M6/M8 arrangements as needed; retain full §6.2 evidence but make no candidate-acceptance or installer-guaranteeability claim | External manual, native | S04c adoption; fail/unrun also leaves publication blocked |
| **G2b — installed-candidate confirmation / overall G2 closure:** after later installer/build slices retain an exact setup candidate, install those bytes and repeat the real-YASB spaced-path/no-PATH proof against the S04c-adopted behavior with manifest/setup identity binding | External manual, native | Publication; only pass closes overall G2 and permits `yasb-spaced-path: pass` |
| Inno staged-swap feasibility spike: stage-to-`.new`, swap, induced step-6 failure, reverse-swap with quarantine, registry capture/restore, and a working uninstall after each — all under `PrivilegesRequired=lowest`, with the named pre-install-evacuation fallback if the post-install rename is disproven (§3.3) | Design-verification build spike, native | Boundary 3 implementation (§9.3) and publication while unresolved |
| Clean Windows machine with no Python: install, CLI contract, helper, multiprocessing, Job, deadlines, no-orphans | External manual, native | Publication |
| Installer lifecycle on a real machine: install, reinstall, upgrade, induced failure rollback, uninstall default and with cleanup | External manual, native | Publication |
| YASB absent / undetected / running messaging and manual-close behavior | External manual, native | Publication |
| No-YAML/CSS-edit proof by file hash on a real YASB installation | External manual, native | Publication |
| Representative live supported-provider flow with secret-safe evidence | External manual, network + credentials | Publication |
| Native Windows proof (`tests/test_windows_native_proof.py`) where the environment supports it | CI native | Publication where runnable; otherwise `unrun` |
| Post-publication clean-machine closeout check on the published bytes | External manual, native | R11 closeout only; not publication or pre-publication ledger |
| Availability of the required environments and their evidence retention locations | External planning | Recorded before execution begins |

Named-provider live proof becomes mandatory only if this release changes that provider; 0.2.0 is
a distribution change and does not change provider behavior, so a representative live flow plus
existing supported-provider coverage satisfies the policy.

## Checklist for the next phase

- [ ] Every mechanism in §10.1 traces to a fixed spec requirement or to a proposal open question.
- [ ] No product decision from §1.1 was reopened or restated as unresolved.
- [ ] `setup.exe` is described as the artifact and Inno Setup only as the technology.
- [ ] The setup-assist helper is private, nonce-guarded (correlation, not authorization), uses the
      independently derived per-user temp transport with strict size/schema/no-reparse cleanup and
      no second stdout contract, and can report after literal state-root deletion.
- [ ] An invalid existing `config.json` is rejected-and-preserved with bounded enumerated
  errors; no text claims an invalid document is merged or committed, with or without a warning.
- [ ] Rollback after the swap is an executable reverse-swap with quarantine ordering and
  registry capture/restore, and Inno feasibility is a named spike gate, not an assumption.
- [ ] Config-assist failure is nonfatal and never rolls back the committed program transaction.
- [ ] Every materially relevant no-PATH discovery mechanism — including `SUBST`/DOS-device
  aliases and App Paths — carries an explicit disposition in §6, and the fail-closed rule with
  no `use_shell: true` bypass is unchanged.
- [ ] Provider selection overriding prerequisite readiness warnings is preserved in §4.4 and D15.
- [ ] The spaced-path gate fails closed and never counts `use_shell: true`; after S02 + S04a,
      G2a selects from disposable/prototype real-target evidence without claiming final acceptance or
      installer guaranteeability; only then may S04c adopt exactly that mechanism.
- [ ] G2b installs the exact retained candidate and repeats the real-YASB spaced-path/no-PATH proof;
      only G2b pass closes overall G2, while fail/unrun blocks publication and any different mechanism
      requires a new G2a/S04c/candidate identity cycle.
- [ ] `rc-manifest.json` is immutable identity/integrity metadata; separately custodied
      `rc-acceptance.json` binds pre-publication statuses to its digest and artifact hashes.
- [ ] The post-publication clean-machine check is closeout-only and cannot rewrite publication
      approval, acceptance status, or artifact identity.
- [ ] Every new module and script has a named test in §9.2.
- [ ] Six capability boundaries are each plausibly <=400 lines, with boundary 5's split identified.
- [ ] External gates are listed as external, not assumed passed.

## Next step

Interactive mode stops after Design. Task planning consumes §9.3 as capability boundaries and
§10.2 as explicit prerequisites; it must order work strict-TDD style (failing tests first) and
must not treat any external gate as satisfied by design alone.
