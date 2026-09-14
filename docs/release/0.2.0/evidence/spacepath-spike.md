# G2a — No-PATH / spaced-path spike evidence (design §6)

**Change:** `release-and-smoke-test-0-2-0`
**Checkpoint:** G2a — real release-target YASB feasibility/selection
**Verdict:** `pass — feasibility/selection only (M6 selected)` — see §16 as completed by §17, which together supersede the §12/§15 verdicts for the current state. §1–§16 remain as the truthful historical record. This verdict claims **only** G2a feasibility/selection for S04c; it is not installer guaranteeability, S04c adoption, retained-candidate inclusion, ledger acceptance, or publication pass.
**Date (local):** 2026-09-06; updated 2026-09-07 (§12: manual run record + complementary direct runs; §15: monitor correction; §16: captured remediation session + selection; §17: bounded exact-M6 direct-run remediation of failed verification `sha256:8ad2c24f…`)
**Worker:** delegated apply executor (G2a external checkpoint only; `<user-home>` redacts the observed Windows profile root)
**Strict TDD:** N/A — external verification gate; no production/test/harness change was made.

> **What this record is.** A truthful G2a `unrun (external)` record. Read-only environment
> discovery and integrity baselining were performed. The design §6.2 mechanism executions
> (M1–M8) against the real release-target YASB **did not occur** because they require a manual
> native YASB widget run and UI observation that this delegated, non-controlling executor is
> prohibited from performing.
>
> **What this record is NOT.** It is **not** a pass. It does **not** select a mechanism, does
> **not** claim S04c adoption, installer guaranteeability, retained-candidate inclusion,
> acceptance-ledger pass, or publication pass. Per the fail-closed rule (design §6.3), G2a
> `unrun` blocks S04c and leaves publication blocked.

---

## 1. Environment discovery (read-only)

Discovery was produced with the S04a read-only module `src/yasb_limitora/discovery.py`
(`discover(os.environ)`) and read-only registry/version/path inspection. No PATH, environment
variable, YASB config, YAML, or CSS was modified, created, or deleted. No process was installed,
launched, terminated, suspended, restarted, or otherwise controlled.

| Field | Observed value |
| --- | --- |
| Discovery outcome | `detected` |
| Install evidence | `registry:HKLM:YASB Reborn@` (InstallLocation value empty), `directory:C:\Program Files\YASB` |
| YASB product | YASB ("YASB Reborn") |
| YASB version | `2.0.6` (`yasb.exe` FileVersion `2.0.6.0`, ProductVersion `2.0.6`) |
| YASB install path | `C:\Program Files\YASB` |
| YASB launcher binaries present | `yasb.exe`, `yasb_themes.exe`, `yasbc.exe` (read-only listing) |
| Config home state | `resolved` (safe) |
| Config home | `<user-home>\.config\yasb` (from `USERPROFILE`; `YASB_CONFIG_HOME` unset) |
| `.env` state | `present` |
| `config.yaml` | present (9033 bytes) |
| YASB process status | `clear` — **no `yasb.exe` / `yasb-limitora.exe` process running** |
| Discovery reasons | none (no probe failure) |
| OS / platform | Windows (`os.name == 'nt'`), process snapshot supported |

**Frozen candidate (S02b target) present:** `build/frozen/dist/yasb-limitora/yasb-limitora.exe`.

## 2. Integrity baseline (read-only, before any external run)

These digests bind the G2a inputs and prove that read-only discovery did not alter YASB
config bytes, `.env` bytes, or the persisted PATH. They are the `before` half of the §6.2
rule-8 PATH-preservation and config-preservation requirement; the `after` half must be
captured by the external manual run that surrounds the actual mechanism executions.

| Artifact | SHA-256 | Notes |
| --- | --- | --- |
| Frozen candidate exe (S02b target) | `93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0` | `build/frozen/dist/yasb-limitora/yasb-limitora.exe` (3543720 bytes) |
| Frozen `_internal/build-info.json` | `f783582af3a79b4a21598f8b45ac951f203099ae0c6787e6c4feee52bc22763a` | version `0.2.0`, PyInstaller `6.22.2`, Python `3.13.5`, limitora `0.3.1`, source_commit `528313c972e14ef72f784ada0284ac7fdf5a5d82`, source_date_epoch `1788269543` |
| S04a harness `scripts/spacepath_spike.ps1` (revision) | `3c24332abc75751ad63a38062acc666a491668df7033ec4c410d7f7a5fcef853` | unchanged by this run |
| YASB `yasb.exe` | `28b5fe3d53ce4a0f6d77e5ef749b25a4faf906cbceb9e0c0b25dad42660a629f` | release-target launcher |
| YASB `config.yaml` | `728af2dc87dd0557cc138d2241f511f96e874836f582067ce26bf5db25c00499` | **not** read as text; **not** modified |
| YASB `.env` | `3bdaf891e689e7271bcb226dac1a81f7dacd91769dcf723f082dc3cafd7c7c1e` | hashed only; contents not inspected (secret-bearing); **not** modified |

### Persisted PATH baseline (read-only)

| Component | Registry type | Length | Contains `yasb-limitora`? |
| --- | --- | --- | --- |
| Machine PATH (`HKLM\...\Session Manager\Environment`) | `REG_EXPAND_SZ` (2) | 957 chars | No |
| User PATH (`HKCU\Environment`) | `REG_EXPAND_SZ` (2) | 1960 chars | No |
| **Combined PATH SHA-256** | — | — | `29f76483d0601f0653cf6f06c25c68f19e25966430ab8b587a8ae0d4afca1a54` |

The frozen candidate's directory is **not** on PATH. This confirms the no-PATH requirement is
real on this machine (M2 control would be expected to fail; M1 would require the optional PATH
convenience task, which is not enabled here). No PATH change was made by this run; the combined
PATH digest above is the unchanged `before` baseline.

## 3. Harness readiness

- S04a harness `scripts/spacepath_spike.ps1` is present and unmodified (revision digest above).
- The harness is read-only/disposable by design: it never modifies PATH or persisted env, never
  edits/creates/deletes YASB YAML/CSS/config (fields needing a target-side test widget are
  recorded as `pending-manual`), never controls any process, and never selects/ranks a mechanism.
- The harness records, for every mechanism, `yaml_quote`, `screenshot`, `child_cmdline`, and
  `process_ancestry` as `pending-manual` — i.e. it **cannot** itself satisfy §6.2 evidence rules
  2, 3, 4, and 7. Those require an actual release-target YASB run with a loaded test widget and
  human UI observation, which is the external manual portion of G2a.
- The harness's `Invoke-LaunchProbe` emulates the YASB `use_shell:false` first-whitespace-token
  parse by directly spawning the frozen candidate; it is **not** a real YASB widget spawn and does
  **not** produce real child-argv/ancestry or widget-rendering evidence. Running it alone would
  not complete G2a and would risk being misread as partial completion, so it was **not** executed
  as a substitute for the required manual run.
- Disposable/prototype M3/M6/M8 arrangements (spaced dir, 8.3 short-path dir, space-free
  relocated launcher) must be constructed by the external run **outside the repository and outside
  the YASB config**; none were created here.

## 4. Mechanism executions M1–M8 (design §6.1) — NOT RUN

Every §6.2 field for every mechanism is `unrun`. No mechanism executed; no widget rendered; no
child argv/ancestry captured; no stdout/exit observed from a real YASB run. M7 is diagnostic-only
and never selectable regardless of outcome.

| ID | Mechanism | `run_cmd` (intended) | `use_shell` | YASB ver / path | Exact test-YAML `run_cmd`/`use_shell` quote | Widget result / screenshot | Child argv (`argv[0]`, no extra tokens) | Process ancestry (no cmd/powershell/conhost) | stdout selector-free JSON (no root `version`) | Exit code | PATH before/after unchanged | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | Bare name, PATH task enabled | `yasb-limitora` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (control; cannot be integration path) |
| M2 | Bare name, PATH unchanged | `yasb-limitora` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (control; expected fail — candidate not on PATH) |
| M3 | Full path, no space | `<progdir>\yasb-limitora.exe` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (primary candidate; needs disposable prototype) |
| M4 | Quoted full path with space | `"<spaced>\yasb-limitora.exe"` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (expected fail under `split(" ")`) |
| M5 | Unquoted full path with space | `<spaced>\yasb-limitora.exe` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (expected fail) |
| M6 | 8.3 short-path alias (space-free) | `<shortpath>\yasb-limitora.exe` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (rescue; needs short-name generation + disposable prototype) |
| M7 | Shell-enabled spaced path (diagnostic) | spaced form | `true` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (diagnostic only; never selectable, never a pass) |
| M8 | Launcher in space-free dir, no elevation | `<space-free>\yasb-limitora.exe` | `false` | unrun | unrun | unrun | unrun | unrun | unrun | unrun | unrun | **unrun** (rescue; needs disposable prototype) |

## 5. Selected mechanism

**None.** No mechanism is selected. Exactly-one-mechanism selection requires complete §6.2
execution evidence proving feasibility against the real release target with PATH unchanged and
`use_shell:false` (M7 never counts). That evidence does not exist because the executions did not
occur. Selecting a mechanism on the basis of discovery or emulation alone would violate the
fail-closed rule.

## 6. Bounded machine-class behavior

Not established. The release-target profile path is `<user-home>\.config\yasb` (user name
redacted; profile path had no space) and the install path is `C:\Program Files\YASB` (**contains a space**). The
program directory that a real install would resolve for `run_cmd` therefore may contain a space
(`C:\Program Files\...`), which is exactly the spaced-path machine class G2a must prove. No
mechanism was executed, so no machine-class coverage (space-free vs spaced) can be claimed. A
space-free-only M3 result would cover only the space-free class and could not be selected as
coverage for the spaced-path class (design §6.3).

## 7. Secret-scan / redaction

- No mechanism executed, so no runtime stdout/stderr was captured. The YASB `.env` (secret-bearing)
  was **hashed only**, never read as text or copied into evidence.
- This document contains no secret bytes: only path strings, versions, and SHA-256 digests.
- The harness applies its own secret-pattern redaction before retention when run externally.

## 8. Cleanup / process evidence

- No disposable/prototype arrangement was created; nothing to clean up.
- No process was spawned, launched, terminated, suspended, restarted, or controlled.
- YASB process probe after discovery: `clear` (no `yasb.exe` / `yasb-limitora.exe` running) —
  unchanged from before discovery.
- PATH: combined digest `29f76483...` unchanged; no Machine/User/process PATH or persisted env
  modification occurred.
- YASB `config.yaml` (`728af2dc...`) and `.env` (`3bdaf891...`) bytes unmodified.

## 9. Fail-closed status

Per design §6.3: G2a `unrun` → **S04c never starts**, **no mechanism is adopted**, and
**publication remains blocked**. This record establishes feasibility inputs and integrity
baselines only; it makes no candidate-acceptance or installer-guaranteeability claim.

## 10. Interaction required — smallest exact user action

G2a is an external manual native gate. A human operator with native GUI access to this Windows
machine must perform the real release-target YASB run. The smallest exact action:

1. **Confirm the target is unchanged:** YASB `2.0.6` at `C:\Program Files\YASB`; persisted PATH
   combined digest still `29f76483d0601f0653cf6f06c25c68f19e25966430ab8b587a8ae0d4afca1a54`;
   `config.yaml` `728af2dc…`, `.env` `3bdaf891…`; frozen candidate
   `build/frozen/dist/yasb-limitora/yasb-limitora.exe` `93db5fbd…`; harness revision `3c24332a…`.
2. **Build disposable/prototype M3/M6/M8 arrangements OUTSIDE the repository and OUTSIDE the
   YASB config** (e.g. under `%TEMP%`), each pointing at the frozen candidate exe: a no-space
   full-path dir (M3), an 8.3 short-path/space-free alias dir if short-name generation is enabled
   on the volume (M6), and a space-free relocated launcher dir (M8). Also prepare a spaced dir
   (M4/M5) and the diagnostic shell-enabled form (M7).
3. **Load a disposable test widget** that invokes the frozen candidate for M1–M8 with the exact
   `run_cmd`/`use_shell` per design §6.1 (`use_shell:false` for M1–M6 and M8; M7 `true`,
   diagnostic only) — using a **disposable YASB config** (e.g. a separate `YASB_CONFIG_HOME`),
   never editing the shipped `<user-home>\.config\yasb\config.yaml`/CSS.
4. **Manually open YASB and observe**, capturing for each mechanism every §6.2 field: exact
   test-YAML `run_cmd`/`use_shell` quote; widget rendering the expected label (cropped, redacted
   screenshot); spawned child command line with `argv[0]` equal to the intended executable path and
   no extra positional tokens; process ancestry showing **no** `cmd.exe`/`powershell.exe`/`conhost`
   intermediary for any passing mechanism; stdout parsing as the current selector-free JSON contract
   with no root `version` field; exit code matching the contract; and PATH unchanged before/after.
   Capture the S02b target digest, S04a harness revision, and each prototype arrangement.
5. **Select exactly one feasible M3/M6/M8 mechanism** with its bounded machine-class behavior **only
   if complete evidence proves it**; otherwise record `fail` (no permitted arrangement feasible /
   incomplete selection evidence) or keep `unrun` truthfully. M7 is never selectable and never a pass.
6. **Redact secrets, retain evidence, and clean up** every disposable arrangement; leave PATH,
   YASB config/`.env`, shipped examples, production code, and tests unmodified; close YASB manually.

Until that external run is completed and its evidence recorded here, G2a remains `unrun (external)`,
S04c remains blocked, and publication remains blocked.

## 12. Manual run record, complementary direct runs, and G2a verdict (2026-09-07)

The human operator performed the manual native YASB run against the disposable environment of §11.
This executor did **not** launch/stop/restart/control YASB at any point; a YASB instance that was
already open (session 2, pid 6708) was only observed read-only. This section records what the
external run produced, the authorized complementary direct runs, the §6.2 completeness assessment,
and the verdict.

### 12.1 Sessions, captures, and the screenshot

| Item | Value |
| --- | --- |
| YASB session 1 | launched 03:00:44 with `YASB_CONFIG_HOME=<root>\config-home` (disposable config SHA-256 `e105cd7d…`), exited from tray 03:16:40 (`config-home\yasb.log`) |
| Session-1 captures | `capture\live-g2a-cim-poll.txt` (03:08:27→), `capture\live-g2a-existing-helper-poll.txt`, `capture\post-poll-state-and-hashes.txt` (03:13) — read-only CIM process/ancestry polling only |
| YASB session 2 | launched 16:49:05 (`yasb.log`), still running at record time (pid 6708; observed only, never controlled) |
| Screenshot | user-supplied `<user-home>\OneDrive\Documentos\ShareX\Screenshots\2026-09\explorer_nrak6Lxj9b.png`, mtime 16:50 → belongs to **session 2**, during which **no process capture was running**; copied verbatim to `docs/release/0.2.0/evidence/spacepath-spike-widget.png` |
| Screenshot SHA-256 (source and copy identical) | `9aeb22b54a49996819f01039efcf92ace5aa1890c5004cfc415bab0fc05a5e3a` (116441 bytes) |
| Exact visual interpretation (directly observed, left→right, one bar) | `M1-BARE-PATHTASK Quota not run` · `M2-BARE-NOPATH Quota not run` · `M3-FULLPATH-NOSPACE Quota not run` · `Loading...` (M4 slot: bare default text, **no** `M4-QUOTED-SPACED` prefix rendered) · `M5-UNQUOTED-SPACED Quota 89% remaining: state=available; freshness=fresh` · `M6-SHORTPATH Quota not run` · `M7-SHELL-DIAGNOSTIC {data[providers][0][compact_text]}` (literal placeholder, prefix rendered) · `M8-LAUNCHER-NOSPACE Quota not run` |

**Cross-session caveat (recorded, not glossed):** widget renders come from session 2 (screenshot),
child argv/ancestry from session 1 (captures). Same disposable config hash (`e105cd7d…`), same YASB
version/path, same arrangement bytes, same widget set — but render and spawn are **not simultaneous**.
This weakens the rule-3/rule-4 binding for every mechanism and is one reason the verdict is not pass.

### 12.2 Exact test-YAML `run_cmd`/`use_shell` quotes (disposable config `e105cd7d…`)

| ID | `run_cmd` (verbatim) | `use_shell` |
| --- | --- | --- |
| M1 | `'yasb-limitora'` | `false` |
| M2 | `'yasb-limitora'` | `false` |
| M3 | `'<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14\arrangements\m3-spacefree\bundle\yasb-limitora.exe'` | `false` |
| M4 | `'"<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14\arrangements\m4 m5 m6 spaced bundle\bundle\yasb-limitora.exe"'` | `false` |
| M5 | `'<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14\arrangements\m4 m5 m6 spaced bundle\bundle\yasb-limitora.exe'` | `false` |
| M6 | `'<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~1\M4M5M6~1\bundle\YASB-L~1.EXE'` | `false` |
| M7 | `'"<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14\arrangements\m4 m5 m6 spaced bundle\bundle\yasb-limitora.exe"'` | `true` |
| M8 | `'<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14\arrangements\m8-launcher-spacefree\bundle\yasb-limitora.exe'` | `false` |

All widgets: `type: yasb.custom.CustomWidget`, `return_format: json`, `run_interval: 120000`,
`run_once: false`, `hide_empty: false`; labels prefixed `M1-…`–`M8-…` with
`{data[providers][0][compact_text]}` templates.

### 12.3 Session-1 child argv / ancestry observations

Direct `yasb.exe` (pid 29900) → child spawns, **no `cmd.exe`/`powershell.exe`/`conhost` between YASB
and the child** (two full widget cycles each):

| Observed child command line | Cycles (pids) | Attribution |
| --- | --- | --- |
| `…\arrangements\m3-spacefree\bundle\yasb-limitora.exe` (unquoted, single token, no extra args) | 38028, 12452 | **M3** — unambiguous |
| `…\arrangements\m8-launcher-spacefree\bundle\yasb-limitora.exe` (unquoted, single token) | 37848, 41008 | **M8** — unambiguous |
| `"…\arrangements\m4 m5 m6 spaced bundle\bundle\yasb-limitora.exe"` (quoted spaced) | 29392, 42668 | **ambiguous among M4/M5/M7** (see below) |
| `yasb-limitora` → `<user-home>\.pyenv\pyenv-win\versions\3.10.5\Scripts\yasb-limitora.exe` | 23040, 2448, 25056, 42576 | **M1/M2 controls** — bare name resolved to an unrelated pyenv-installed `yasb-limitora`, **not** the frozen candidate |

- Each spawned bundle child produced normal PyInstaller onedir `--multiprocessing-fork` grandchildren
  (e.g. 44852, 26328, 6044, 11292, 9844…) parented to the bundle child, not to YASB — ordinary
  candidate behavior, not shell intermediation.
- Ancestry above YASB in session 1: `yasb.exe ← pwsh.exe ← WindowsTerminal.exe` — the operator's
  launch environment for YASB itself, **not** an intermediary in the YASB→child spawn link. The
  helper's coarse `shell_intermediary_present=True` flag reflects those above-YASB ancestors; §6.2
  rule 7 is evaluated on the YASB→child link, which is direct for M3/M8 and for the quoted-spaced pair.
- **Never observed in session 1:** any unquoted-spaced child (M5 form), any 8.3 short-path child
  (M6 form), any `cmd.exe`-parented child (which M7's `use_shell: true` would be expected to produce).
- **Attribution ambiguity:** M4 and M7 carry identical `run_cmd` strings (differing only in
  `use_shell`), and a YASB spawner that re-quotes a parsed spaced token would make M5's unquoted form
  produce the same quoted command line. The two quoted-spaced spawns therefore cannot be uniquely
  bound to M4, M5, or M7. Combined with M4's unrendered `Loading...` slot and M7's literal
  placeholder, the M4/M5/M7 records are incomplete or contradictory.
- **M5 anomaly:** the M5 widget rendered a quota snapshot (session 2) although no unquoted-spaced
  child was ever captured and session 2 had no capture running. Something rendered M5; the evidence
  cannot say what spawned it. Recorded truthfully; not usable as rule-4 evidence.

### 12.4 Complementary direct runs (authorized; explicitly NOT YASB spawns)

Harness `capture\direct-run-m3m6m8.py` (SHA-256 `57e0324be9ad3241ca0c76693d174460fe6f8f425e1a0acaf6f525a95773ac91`,
Python 3.10.5): each of the exact M3, M6, M8 `run_cmd` strings executed **once**, `argv=[exe]` only,
`shell=False` (direct CreateProcess from the harness process; ancestry
`exe ← python.exe ← harness shell`, recorded honestly), `cwd=capture dir`, bounded 30 s timeout.
Outputs retained only under `capture\` (`direct-run-m3m6m8.json`, per-run redacted stdout/stderr).
These runs prove executable-byte contract conformance and exit codes; they do **not** substitute for
the missing YASB ancestry/render simultaneity.

| Field | M3 | M6 (8.3 short path) | M8 |
| --- | --- | --- | --- |
| exe SHA-256 before run | `93db5fbd…` | `93db5fbd…` (short path resolves to same bundle bytes) | `93db5fbd…` |
| exit code | 0 | 0 | 0 |
| duration | 0.43 s | 0.43 s | 0.42 s |
| stdout raw SHA-256 / len | `0ed3a41c…` / 2117 B | identical | identical |
| stderr | empty (`e3b0c442…`) | empty | empty |
| JSON parse / root keys | ok / `execution_error, execution_state, providers` | same | same |
| root `version` present | **no** (selector-free contract) | no | no |
| `providers[0]` | `outcome=snapshot`, `compact_text="Quota 89% remaining; state=available; freshness=fresh"`, full presentation field set | same | same |
| `execution_state` | `partial` (one provider snapshot, one not-run — contract-valid) | same | same |
| secret-scan redaction hits | 0 | 0 | 0 |
| processes before/after | none / none (no residue) | none / none | none / none |

Note: the direct runs returned a snapshot document, while the session-2 widgets for M3/M6/M8 rendered
`Quota not run` (a contract-valid `not_run` presentation, `projection.py` maps `not_run → "Quota not
run"`). Both documents satisfy the selector-free contract; the widget renders additionally prove YASB
parsed candidate JSON. The environment difference (YASB process env vs harness env) is recorded as an
observation, not explained away.

### 12.5 §6.2 completeness table (rules 1–9 per mechanism)

Legend: ✓ present · ✗ absent/fail · ~ ambiguous or cross-session-bound · n/a not applicable.

| Rule | M1 | M2 | M3 | M4 | M5 | M6 | M7 (diag) | M8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 YASB ver/path | ✓ 2.0.6 / `C:\Program Files\YASB` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 exact YAML quote | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 widget render (real run) | ✓ (sess.2) | ✓ (sess.2) | ~ (sess.2 render, sess.1 spawn) | ✗ bare `Loading...` | ~ rendered but unbound | ~ rendered but unbound | ✗ literal placeholder | ~ (sess.2 render, sess.1 spawn) |
| 4 child argv (`argv[0]`, no extra tokens) | ✓ wrong exe (pyenv) | ✓ wrong exe (pyenv) | ✓ | ~ unattributable | ✗ missing | ✗ missing | ~ unattributable | ✓ |
| 5 stdout selector-free JSON, no root `version` | widget-parse only | widget-parse only | ✓ complementary direct run + widget parse | ✗ | ✗ no capture | ✓ complementary direct run only (no YASB binding) | ✗ | ✓ complementary direct run + widget parse |
| 6 exit code | ✗ not captured | ✗ | ✓ direct run (0) | ✗ |  | ✓ direct run (0) | ✗ | ✓ direct run (0) |
| 7 no shell intermediary, `use_shell:false` | n/a control | n/a control | ✓ direct YASB→child | ~ | ✗ | ✗ no spawn observed | n/a (shell true; no cmd.exe seen — inconclusive) | ✓ direct YASB→child |
| 8 PATH unchanged | ✓ `3736ac1a…` before 03:08 / after 03:13 / before 22:01 / after 22:01, `contains_yasb_limitora=False` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 9 secret-scan/redaction | ✓ 0 hits; `.env` hashed only, never read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Status** | control fail (wrong binary; never integration path) | control fail (wrong-binary resolution; never integration path) | strong but incomplete | fail (expected-fail control; render absent) | fail (missing rule 4; anomalous render) | fail (missing rule 4) | diagnostic inconclusive; never selectable | strong but incomplete |

### 12.6 Selection determination — none; verdict `fail (selection evidence incomplete)`

1. **Incomplete exercise.** §6.1 requires M4/M5 to be run *and recorded* and the G2a task requires
   M1–M8 exercised with child argv/ancestry. M5 and M6 lack rule-4 evidence entirely; M4/M7 spawn
   attribution is ambiguous; M4/M7 renders are absent. Per §6.2, missing required evidence fails the
   affected runs, and "selection evidence incomplete" makes G2a `fail`.
2. **Machine class.** This machine's profile path (`<user-home>`) contains no space, so M3/M8
   evidence covers only the **space-free** class. The **spaced** class — the class the
   `yasb-spaced-path` gate exists for — was exercised only through the M4/M5/M6 prototypes, whose
   records are incomplete/contradictory (M5 rendered a snapshot with no captured spawn). §6.3 forbids
   selecting an M3-only arrangement as coverage for the spaced class. M8's arrangement is itself
   space-free and proves nothing about spaced-install behavior; the standing rule "prefer M8 only if
   evidence proves its space-free relocated-launcher behavior against this spaced-install machine
   class" is **not** met, so M8 is not selected by preference either. M6, the spaced-class rescue,
   has no YASB spawn evidence at all.
3. **Simultaneity.** Render (session 2) and spawn (session 1) evidence are not bound to one session.

Therefore: **selected mechanism: none. Verdict: `fail — selection evidence incomplete (external
manual rerun required)`.** Not `unrun`: executions did occur. Per §6.3 fail-closed: **S04c never
starts, no mechanism is adopted, publication remains blocked.** The `tasks.md` G2a checkbox remains
**unchecked**. This record claims no installer guaranteeability, no S04c adoption, no
retained-candidate inclusion, no ledger acceptance, and no publication pass.

### 12.7 Single smallest manual rerun (the one action that unblocks)

One captured session, no config/arrangement changes needed (hashes recorded above):

1. Start both read-only capture helpers (`capture\capture-child.ps1`, CIM poll) writing into `capture\`.
2. Launch YASB 2.0.6 exactly as session 1 (`YASB_CONFIG_HOME=<root>\config-home`, same disposable
   config `e105cd7d…`).
3. Keep the `g2a-bar` visible and wait **≥2 widget cycles (~5 min)** so every M1–M8 widget executes
   at least twice *while capture is running*.
4. Take the screenshot **inside the capture window** (same session), showing all eight slots.
5. Exit YASB from the tray; stop the captures; hand over the files.

That single rerun yields: distinct M5 unquoted-spaced child argv/ancestry (or proof-of-absence bound
to the widget state), distinct M6 short-path child (or absence), M4-vs-M7 disambiguation (presence or
absence of a `cmd.exe`-parented child for M7), and a screenshot simultaneous with the spawn captures —
the exact fields missing in §12.5.

### 12.8 Integrity / process / cleanup evidence for this turn

- PATH canonical combined SHA-256 `3736ac1a909fc1ef41679c9d9b445b082093865712a7ad886eaf8d63ad522a44`
  identical pre-direct-run (22:01:03Z) and post-direct-run (22:01:41Z); `contains_yasb_limitora=False`.
- Real YASB `config.yaml` `728af2dc…` and `.env` `3bdaf891…` unchanged; disposable config `e105cd7d…`
  and `styles.css` `a15c8375…` unchanged; frozen candidate `93db5fbd…` unchanged; S04a harness
  `scripts/spacepath_spike.ps1` `3c24332a…` unchanged.
- No `yasb-limitora` process residue after the direct runs; session-2 YASB (pid 6708) pre-existed this
  turn and was only observed — never launched, stopped, restarted, or controlled.
- New external files confined to `capture\`: `direct-run-m3m6m8.py`, `direct-run-m3m6m8.json`,
  `direct-run-console.txt`, `direct-run-{m3,m6,m8}.stdout.redacted.bin`,
  `direct-run-{m3,m6,m8}.stderr.redacted.txt`, `pre-direct-run-baseline.txt`,
  `post-direct-run-state.txt`.
- Repo changes this turn: `docs/release/0.2.0/evidence/spacepath-spike-widget.png` (new binary copy),
  `docs/release/0.2.0/evidence/spacepath-spike.md` (§12 + header verdict),
  `openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`. `tasks.md` untouched (checkbox
  unchecked). No production code, tests, examples, installer, PATH, or YASB config change.
- Secret-scan: 0 redaction hits in all captured stdout/stderr; the secret-bearing `.env` was hashed
  only, never read as text.

## 11. Disposable manual-test preparation (2026-09-07, user chose `Preparar prueba manual`)

The user authorized preparing the disposable/prototype environment so the human action becomes small.
A uniquely named disposable root was created under `%TEMP%` only — outside the repository and outside
the real YASB config home. No YASB process was launched/terminated/restarted/controlled. The real
`config.yaml`, `.env`, CSS, PATH, shipped examples, production code, tests, and installer were **not**
read or modified. Only frozen-executable bytes were copied and read-only capture helpers created.

**Verdict remains `unrun (external)`; the tasks.md checkbox remains UNCHECKED.** One element could not
be prepared safely (see §11.5).

### 11.1 Disposable temp root

- Root: `<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14`
- Layout: `arrangements\`, `capture\`, `config-home\` (disposable `YASB_CONFIG_HOME` target), `evidence\`.
- Root marker: `%TEMP%\yasb-g2a-20260907-020324-0e776d14.path`.

### 11.2 M3–M8 arrangements (frozen-candidate byte copies; full onedir, 70 files each)

The frozen candidate is a PyInstaller **onedir** build, so each arrangement copies the whole bundle
(`yasb-limitora.exe` + `_internal\`) — the exe alone cannot run without its `_internal` sibling.

| Mechanism | Disposable arrangement (long path) | exe SHA-256 |
| --- | --- | --- |
| M3 (full path, no space) | `<root>\arrangements\m3-spacefree\bundle\yasb-limitora.exe` | `93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0` |
| M4/M5/M6 (spaced path) | `<root>\arrangements\m4 m5 m6 spaced bundle\bundle\yasb-limitora.exe` | `93db5fbd…` (identical) |
| M8 (space-free relocated launcher) | `<root>\arrangements\m8-launcher-spacefree\bundle\yasb-limitora.exe` | `93db5fbd…` (identical) |

Byte-preservation confirmed: all three copied executables hash identically to the source frozen
candidate (`93db5fbd…`). M1 (bare name, PATH task) and M2 (bare name, PATH unchanged) need no
arrangement — they invoke the bare name `yasb-limitora`; the candidate is **not** on PATH, so M2 is
expected to fail and M1 would require the optional PATH task (not enabled here). M7 reuses the spaced
arrangement with `use_shell: true` (diagnostic only).

### 11.3 M6 8.3 short-path availability — FINDING

Short-name generation **is enabled** on the `%TEMP%` volume (C:). The spaced bundle resolves to a
space-free 8.3 alias, so **M6 is prototypeable on this machine** (whether the real YASB spawns it
successfully still must be re-observed — not assumed):

- Spaced dir (long): `<root>\arrangements\m4 m5 m6 spaced bundle`
- Spaced dir (short): `<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~1\M4M5M6~1`
- Spaced exe (short): `...\YASB-G~1\ARRANG~1\M4M5M6~1\bundle\YASB-L~1.EXE` — `spaced_short_has_space = false`
- Recorded in `<root>\evidence\shortpath-and-path.json`.

### 11.4 Read-only capture helpers and PATH baseline

- `<root>\capture\capture-path.ps1` (SHA-256 `f73183e2…`) — records Machine+User PATH lengths and a
  combined SHA-256 (canonical method: `[Environment]::GetEnvironmentVariable` expansion + UTF-16),
  appending labeled `before`/`after` lines. Functionally validated.
- `<root>\capture\capture-child.ps1` (SHA-256 `180d63d2…`) — read-only `Get-CimInstance Win32_Process`
  capture of the spawned `yasb-limitora.exe` child: `CommandLine` (argv), `ExecutablePath`, full parent
  ancestry chain, and `shell_intermediary_present` (cmd/powershell/pwsh/conhost). Never controls any
  process. Dry-run validated: correctly reported `NO_TARGET_RUNNING` with no candidate running.
- `<root>\capture\probe-shortpath-and-path.ps1` (SHA-256 `ef3de4a5…`) — short-path + PATH probe used
  for §11.3.
- **PATH baseline (unchanged):** combined SHA-256 `3736ac1a909fc1ef41679c9d9b445b082093865712a7ad886eaf8d63ad522a44`,
  Machine len 971, User len 1961, `contains_yasb_limitora = false`; identical `before-prep-complete`
  and `after-prep` (`<root>\evidence\path-before-after.txt`). (This canonical expanded/UTF-16 digest
  differs from the §2 raw-registry UTF-8 digest `29f76483…`; both describe the same unchanged PATH —
  the manual run must compare like-for-like using `capture-path.ps1`.)
- Post-prep process state: YASB `clear`; `yasb-limitora` process count `0`. Prep spawned no YASB and no
  candidate process.

### 11.5 Remaining blocker — disposable `config.yaml` schema (truthful stop)

The disposable `config-home\` is intentionally **empty**; no `config.yaml` was fabricated. A valid
YASB **2.0.6** custom-widget `config.yaml` cannot be produced from allowed sources alone:

- The real user `config.yaml`, the shipped repo example `examples/customwidget/customwidget.yaml`, and
  `tests/test_customwidget_examples.py` are protected from reading this turn.
- YASB's install ships no loose config/schema (compiled into `lib\library.zip`, pydantic-validated).
- The design/spec grant only the fragment fields `run_cmd` / `use_shell`, not the full top-level config
  and custom-widget registration structure.

Fabricating the schema from memory would risk a config YASB 2.0.6 rejects (spoiling the manual run and
producing an error bar rather than valid evidence) and would violate the design §6.1 principle that the
release target's behavior — including whether it honors a process-local `YASB_CONFIG_HOME` — **must be
re-observed, not assumed**. Per the instruction to stop truthfully when a safe disposable config cannot
be prepared without protected reads, this element is left unprepared.

**Smallest unblock (choose one):**

1. Grant read-only access to the project's own shipped example `examples/customwidget/customwidget.yaml`
   (and, if needed, `tests/test_customwidget_examples.py` for the asserted shape) as the authoritative
   custom-widget schema. This is a project example file, not the user's real YASB config/`.env`/CSS/PATH.
   With it, the executor can write the disposable `config.yaml` (M1–M8 widgets), the exact one-command
   launch line, and the expected widget labels, then re-validate statically.
2. Or the human drops a valid disposable `config.yaml` (with the M1–M8 custom-widget entries) into
   `<root>\config-home\` and reports the exact `run_cmd`/`use_shell` used, so the evidence can quote it.

Until the config schema is unblocked and the real YASB run is observed, G2a stays `unrun (external)`,
S04c remains blocked, and publication remains blocked.

### 11.6 Cleanup boundary

The entire disposable environment is confined to
`<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14` and its marker
`%TEMP%\yasb-g2a-20260907-020324-0e776d14.path`. Rollback/cleanup = delete that root directory and the
marker file only. Nothing was written under the repository, the real YASB config home, PATH, or any
protected surface; no YASB or candidate process was started.

## 13. Authorized remediation preparation — BLOCKED by running YASB session (2026-09-07)

A remediation preparation for ONE new manual session was authorized, to remedy the parent-supplied
evidence identity `sha256:0e4af39a58c510dd073b40a4a4dbf9462647633e825efc7b7bfcf7c96e3a7cc1`
(the §12 render/spawn simultaneity gap: screenshot from session 2 with no capture running; child
argv/ancestry from session 1). The authorization included a hard read-only gate: prepare only if no
YASB / `yasb-limitora` process remains; otherwise stop and ask the human to close it manually.

Read-only CIM inspection at 2026-09-07T22:15:46Z found the §12.1 **session-2 instance still running**:

| PID | Parent PID | Executable | CommandLine | StartTime |
| --- | --- | --- | --- | --- |
| 6708 | 23008 | `C:\Program Files\YASB\yasb.exe` | `"C:\Program Files\YASB\yasb.exe"` | 2026-09-07 16:49:05 |

No `yasb-limitora.exe` process was found (other pattern matches were the inspection toolchain itself).

**Actions taken: none to the disposable configuration.** No prototype directories, onedir copies,
disposable `config.yaml`/CSS, capture monitor, or integrity helpers were created or modified. The
only artifact written was the read-only inspection script
`<root>\prep-r3\proccheck.ps1` inside the disposable temp exception root. No real config/`.env`/CSS/PATH
was read or mutated; no YASB or candidate was launched, stopped, restarted, or controlled.

**Verdict unchanged: `fail — selection evidence incomplete (external manual rerun required)` (§12.6).**
G2a remains not passed; S04c never starts; no mechanism adopted; publication remains blocked; the
`tasks.md` G2a checkbox remains unchecked. No screenshot, ancestry, or capture output is claimed.

**Unblock:** the human manually closes YASB (PID 6708, e.g., tray → exit), confirms no YASB process
remains, then re-authorizes this preparation. Only then will the distinct M1–M8 prototype arrangements,
disposable config, capture monitor, and before/after integrity helpers be built for one new
capture-bound manual session.

## 14. Remediation preparation round 3 — COMPLETE, awaiting one manual session (2026-09-07)

The user manually closed YASB (PID 6708 gone; strict read-only recheck at ~22:20Z:
`NO_YASB_PROCESSES`, zero `yasb.exe`/`yasb-limitora*`). The authorized preparation was then completed
inside the existing disposable root. **No YASB or candidate was launched, stopped, restarted, or
controlled; the verdict remains `fail — selection evidence incomplete` and G2a remains unchecked
until the manual rerun below occurs.** No screenshot, ancestry, or capture output is claimed.

### 14.1 Distinct per-mechanism arrangements (`<root>\arrangements-r3\`, six separate onedir copies)

Every path-sensitive mechanism now has its **own** directory and full 70-file onedir copy; every
executable basename is `yasb-limitora.exe`; every exe SHA-256 equals the frozen candidate
`93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0`; each copy's full tree hash
matches the source bundle byte-for-byte (verified statically, `evidence\r3-static-validation.json`).

| ID | Directory (under `arrangements-r3\`) | `run_cmd` form | `use_shell` | Distinctness verified |
| --- | --- | --- | --- | --- |
| M1 | — (bare control) | `'yasb-limitora'` | `false` | identical to M2 by design; resolves to **unrelated pyenv** shim `<user-home>\.pyenv\pyenv-win\shims\yasb-limitora.bat` → `versions\3.10.5\Scripts\yasb-limitora.exe` (`76fb2532…`); labels `M1-BARE-PYENV-NEVERSELECT`; never selectable |
| M2 | — (bare control) | `'yasb-limitora'` | `false` | label `M2-BARE-PYENV-NEVERSELECT-B`; never selectable |
| M3 | `m3-spacefree\bundle\` | unquoted full path, space-free | `false` | ≠ M8 path; no space; no quotes |
| M4 | `m4 quoted spaced\bundle\` | quoted full path, spaced | `false` | command AND path ≠ M7 (round-2 ambiguity fixed); quoted; spaced |
| M5 | `m5 unquoted spaced\bundle\` | unquoted full path, **own** spaced dir | `false` | path ≠ M4/M7; unquoted; spaced (round-2 sharing fixed) |
| M6 | `m6 shortpath spaced\bundle\` | verified unique 8.3 short path `<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe` | `false` | short path space-free; unique (6/6 short paths distinct); round-trip hash matches long path; collides with no other mechanism |
| M7 | `m7 shell spaced\bundle\` | quoted full path, **own** spaced dir | `true` (only M7) | command AND path ≠ M4; diagnostic only, never selectable |
| M8 | `m8-launcher-spacefree\bundle\` | unquoted full path, space-free | `false` | ≠ M3 path; no space; no quotes |

### 14.2 Disposable config/CSS (`<root>\config-home-r3\`; round-2 `config-home\` untouched)

- `config.yaml` SHA-256 `bc43b5a97b65a1de6f76d05e26f3463299d011da508d41e6b7545a72880fb69a` (5796 B):
  one bar `g2a-r3-bar`, eight widgets `g2a_r3_m1..m8` (`yasb.custom.CustomWidget`, `return_format:
  json`, `hide_empty: false`, **`run_once: true`** so the monitor started first sees every initial
  spawn), distinct labels/class names per mechanism, exact §14.1 `run_cmd`/`use_shell` semantics.
  Validated with `yaml.safe_load` + semantic assertions (0 fails).
- `styles.css` SHA-256 `c829271b17387f081aaa59eccc292f9fef80ba59933443961a77119407f9cf89` (395 B):
  legible 11px labels, bounded widths (`min-width:110px; max-width:210px`) and spacing per widget
  class so all eight labels fit one screen capture. Brace-balanced; all eight selectors present.
- Real config/.env/CSS/PATH were **not** read as text and **not** mutated (hashes only, §14.4).

### 14.3 Capture monitor and integrity helpers (`<root>\capture\`; read-only; human-run)

- `r3-monitor.ps1` SHA-256 `d3c89989916f361e3217e3fbb1025d6c236a206cd75f0c6432c634630000a2b6`
  (**SUPERSEDED — this event-subscription revision failed at arm time; see §15 for the corrected
  polling-only revision `b4124958…`, which is the ONLY monitor to run**):
  registers CIM `Win32_ProcessStartTrace`/`Win32_ProcessStopTrace` indication events (stop trace
  carries `ExitStatus`) **plus** a 300 ms WQL-filtered polling backstop; per relevant start it
  records UTC timestamp, PID, command line, executable path, direct parent, full ancestry snapshot
  (child→ancestor, 24-level guard), and a shell-intermediary flag (`cmd/powershell/pwsh/conhost`
  in ancestry); per stop it records exit status. Runs integrity-before at arm time, integrity-after
  (with screenshot binding) at horizon end, **auto-exits after 10 minutes**, prints
  `MONITOR_ARMED`/`MONITOR_COMPLETE`, and never signals or controls any process.
- `r3-integrity.ps1` SHA-256 `2ff2721dfbc114cd48ca0b5cf9b93b675c284a4bde054d82ea106ab5965e5537`:
  phase `before|after`; records persisted PATH canonical UTF-16 digest + `contains_yasb_limitora`,
  real `config.yaml`/`.env` SHA-256 and length (**hashes only, contents never read/stored**),
  disposable config/CSS hashes, all six frozen-target exe hashes + bundle file counts + M6 short-path
  round-trip, bare-control resolution, screenshot SHA-256/mtime vs monitor window binding, and
  process residue. Dry-run verified (`capture\r3\integrity-before.txt`, 22:35Z): PATH `3736ac1a…`
  unchanged, real config `728af2dc…`, `.env` `3bdaf891…`, residue count 0.
- Both scripts pass `System.Management.Automation.Language.Parser::ParseFile` with 0 errors
  (static parse; neither was executed as a monitor, no YASB/candidate launched).

### 14.4 Exact manual steps for the ONE remediation session (human only)

> **Superseded by §15.4** for step 1's expected armed line, step 5, and the expected-output list
> (no event `.jsonl` files exist in the corrected polling-only monitor). Steps 2–4 are unchanged.

All paths under `<root>` = `<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14`.

1. **PowerShell window A — start the monitor FIRST:**
   `powershell -NoProfile -ExecutionPolicy Bypass -File "<root>\capture\r3-monitor.ps1"`
   → expect `MONITOR_ARMED horizon_minutes=10 poll_ms=300 out_dir=<root>\capture\r3`.
2. **PowerShell window B — launch YASB with the disposable config home:**
   `powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:YASB_CONFIG_HOME='<root>\config-home-r3'; & 'C:\Program Files\YASB\yasb.exe'"`
3. **When the bar settles** (~15–30 s, eight `M1-…M8-` labels visible), take a screenshot, save it
   exactly to `<root>\capture\r3\screenshot-r3.png`, and record that path. (If saved elsewhere, e.g.
   ShareX, copy it to that exact path or note the real path for later `-ScreenshotPath` binding.)
4. **Manually close YASB** (tray → exit). The monitor is never used to stop anything.
5. **Wait for the monitor to auto-exit** (≤10 min) → expect `MONITOR_COMPLETE` with event counts and
   `screenshot_present=True`.

Expected outputs (all under `<root>\capture\r3\`): `monitor-window.txt`,
`monitor-events-start.jsonl`, `monitor-events-stop.jsonl`, `monitor-poll.jsonl`,
`monitor-summary.txt`, `integrity-before.txt` (session block appended), `integrity-after.txt`,
`screenshot-r3.png`.

This session yields, in ONE simultaneous window: per-mechanism child argv (`argv[0]` exactness per
distinct command), parent/ancestry with shell-intermediary flags (M4-vs-M7 disambiguated by distinct
paths and by `cmd.exe` presence for M7 only), exit statuses, M5/M6 spawn-or-absence proof, PATH and
real-config immutability before/after, and a screenshot bound to the capture window. Recording and
verdict re-evaluation happen only after the human hands over these files; until then G2a stays
`fail (selection evidence incomplete)`, S04c never starts, and publication remains blocked.

### 14.5 Cleanup boundary (round 3)

New artifacts are confined to `<root>\arrangements-r3\`, `<root>\config-home-r3\`,
`<root>\capture\` (two scripts + `r3\` outputs), `<root>\evidence\r3-static-validation.json`, and
`<root>\prep-r3\`. Round-2 evidence (`config-home\`, `arrangements\`, prior `capture\` files) is
untouched. Rollback/cleanup remains: delete `<root>` and the marker
`%TEMP%\yasb-g2a-20260907-020324-0e776d14.path` only. Repository changes this turn:
`docs/release/0.2.0/evidence/spacepath-spike.md` (§13 blocked record + this §14) and
`openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`; `tasks.md` untouched.

## 15. Capture monitor defect and polling-only correction — PREPARED, awaiting one manual session (2026-09-07)

### 15.1 Defect (independent diagnosis, capture-side only)

The §14.3 monitor revision `d3c89989…` failed **before** `MONITOR_ARMED` during the first real-run
attempt (~22:38Z): `Register-CimIndicationEvent` for `Win32_ProcessStartTrace` returned
**WBEM_E_CALL_CANCELLED**, so no events were subscribed and the script terminated at setup. Partial
outputs of that failed attempt (`capture\r3\integrity-before.txt`, an unclosed
`monitor-window.txt`) were the only r3 artifacts produced. **No YASB or candidate was launched or
controlled in that attempt or in this correction.** All §14.1 arrangements, §14.2
`config-home-r3`, and `r3-integrity.ps1` (`2ff2721d…`) remain statically valid and unchanged.

### 15.2 Corrected monitor (`<root>\capture\r3-monitor.ps1`, polling-only)

- SHA-256 `b4124958b5dfb2719b454ef8aa3d4ad922f2053b469f54ab61542c59c885396e` (replaces `d3c89989…`).
- **No `Register-*Event`, no WMI indication subscription** (verified by scan; the only textual
  matches are correction-history comments). Pure bounded polling of the **full** `Win32_Process`
  table (`SELECT ProcessId,ParentProcessId,Name,CommandLine,ExecutablePath FROM Win32_Process`),
  default **200 ms** (`-PollMs` validated 100–300), horizon default 10 min (`-HorizonMinutes`
  validated 1–10), plus `-GraceSeconds` (default 15, validated 1–120).
- Per poll it detects YASB roots (name/command line/exe matches `yasb`, case-insensitive) and their
  descendants at any depth, excluding the monitor's own PID/ancestor chain. **First observation per
  PID is retained** and written once as `poll_new` with: UTC timestamp, PID/PPID/name, command line,
  executable path, direct parent name/command line, `is_yasb_root`, child→ancestor chain (24-level
  guard), and shell-intermediary flag (`cmd/powershell/pwsh/conhost` in ancestry).
- Disappearances are written as `poll_gone` with **`exit_status: null`** and explicit note
  **`exit_status_unavailable_from_polling`** (polling cannot observe exit codes; the event-based
  `ExitStatus` path is abandoned with the subscription mechanism).
- Early stop occurs **only** after a YASB root was observed, nothing related remains live, and the
  short grace period elapsed; otherwise it runs the full bounded horizon. Consecutive poll errors
  (≥25) escalate to the failure path instead of looping silently.
- **Outer `try/finally`**: the `finally` block ALWAYS closes the window (`monitor_end_utc`), runs
  `r3-integrity.ps1 -Phase after -ScreenshotPath <root>\capture\r3\screenshot-r3.png`, and writes
  `monitor-summary.txt` including `status=setup_failed|armed→completed|failed` and the failure text.
  `MONITOR_ARMED` is printed only after setup succeeds (output dir, integrity-before, window open,
  and one successful full-table probe query). It never signals, stops, starts, or controls any
  process.

### 15.3 Static + dry-run validation (no YASB, no candidate launched)

- `Parser::ParseFile` on the corrected script: **0 errors**; forbidden-construct scan: only comments.
- Read-only process gate before the dry run: `NO_YASB_PROCESSES` (0 `yasb.exe`/`yasb-limitora*`).
- Bounded dry run (`-HorizonMinutes 1`, no YASB): printed
  `MONITOR_ARMED horizon_minutes=1 poll_ms=200 grace_seconds=15 out_dir=<root>\capture\r3`, then ran
  the full horizon and printed `MONITOR_COMPLETE` with `status=completed`, `failure=none`, closed
  window `22:49:44Z→22:50:44Z`, `poll_records=0`, `yasb_root_observed=False`,
  `early_exit=none (full bounded horizon)`, `consecutive_poll_errors_at_end=0`,
  `integrity_after=written`, `screenshot_present=False`.
- All dry-run outputs **and** the failed attempt's partial r3 outputs were then cleared:
  `<root>\capture\r3\` is **empty**, so the real run writes a clean, uniquely identified capture set
  (the monitor re-runs integrity-before at arm time). Validation helper: `<root>\prep-r3\validate-r3b.ps1`.

### 15.4 Exact manual steps for the ONE remediation session (authoritative; supersedes §14.4 where noted)

All paths under `<root>` = `<user-home>\AppData\Local\Temp\yasb-g2a-20260907-020324-0e776d14`.

1. **PowerShell window A — start the monitor FIRST:**
   `powershell -NoProfile -ExecutionPolicy Bypass -File "<root>\capture\r3-monitor.ps1"`
   → expect exactly:
   `MONITOR_ARMED horizon_minutes=10 poll_ms=200 grace_seconds=15 out_dir=<root>\capture\r3`
2. **PowerShell window B — launch YASB with the disposable config home** (unchanged from §14.4):
   `powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:YASB_CONFIG_HOME='<root>\config-home-r3'; & 'C:\Program Files\YASB\yasb.exe'"`
3. **When the bar settles** (~15–30 s, eight `M1-…M8-` labels visible), save a screenshot exactly to
   `<root>\capture\r3\screenshot-r3.png` (or note the real path for later `-ScreenshotPath` binding).
4. **Manually close YASB** (tray → exit). The monitor never stops anything.
5. **Wait**: the monitor early-exits ~15 s after the last YASB-related process disappears, or at the
   10-minute horizon → expect `MONITOR_COMPLETE` with `status=completed`, `yasb_root_observed=True`,
   `poll_records>0`, and `screenshot_present=True`.

Expected outputs (all under `<root>\capture\r3\`): `monitor-window.txt`, `monitor-poll.jsonl`
(`poll_new`/`poll_gone` records), `monitor-summary.txt`, `integrity-before.txt`,
`integrity-after.txt`, `screenshot-r3.png`. **No `monitor-events-*.jsonl` files exist** in this
revision; per-process exit statuses are NOT claimed — `poll_gone` records carry
`exit_status:null` + `exit_status_unavailable_from_polling`, and exit-code evidence, if needed,
comes only from the separately authorized direct-run harness records (§12).

**Verdict at time of §15: `fail — selection evidence incomplete (external manual rerun required)`.**
Superseded by §16 after the human completed the one manual session.

## 16. Captured remediation session — G2a `pass (feasibility/selection only)`, M6 selected (2026-09-07)

The human ran the §15.4 procedure exactly once. Evidence revision candidate:
**`g2a-evidence-rev-r3-session-1`**, bound to: poll log SHA-256
`6705793c0e9c9072457122de71766e721ef61a4bad1f356e28e807f57e8be72c` (120 records), screenshot
SHA-256 `baa7e2f8a405353b052aefb1765a6efd5982cad19de8e53bbbb497b0155a2744` (96766 B; repo copy
`docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png`, byte-identical), monitor
`b4124958…`, disposable config `bc43b5a9…`, frozen target `93db5fbd…`, S04a harness `3c24332a…`.

### 16.1 Session window and monitor facts

- Monitor (`b4124958…`, polling-only §15): `MONITOR_ARMED` then `MONITOR_COMPLETE`,
  `status=completed`, `failure=none`, window `2026-09-07T22:58:39.9611646Z`–`23:01:26.0009352Z`,
  `poll_records=120` (60 `poll_new` + 60 `poll_gone`), `distinct_related_pids=56`,
  `yasb_root_observed=True`, `early_exit=early_exit_yasb_observed_then_gone_grace_15s`,
  `consecutive_poll_errors_at_end=0`, `integrity_after=written`. An earlier interrupted arming
  (22:54:21Z→22:55:16Z, no screenshot, residue 0) precedes the canonical session in the appended
  integrity blocks; it produced no capture claims.
- YASB root: PID 2480, `"C:\Program Files\YASB\yasb.exe"`, spawned 22:59:12Z, gone 23:01:10Z
  (`poll_gone`, `exit_status:null`). Its own ancestry: `yasb.exe ← pwsh.exe (7.6.5, Windows
  Terminal) ← WindowsTerminal.exe` — the human's window-B launcher, **above** the YASB root; it is
  session environment, not spawn intermediation, and is identical for every mechanism.
- Every `poll_gone` carries `exit_status:null` + `exit_status_unavailable_from_polling`; **no exit
  code is invented anywhere in this record**. In-session exit codes are unavailable by construction;
  rule-6 exit evidence uses only authorized complementary direct runs (for the selected M6, this is
  now §17's exact-command run; §12's direct runs used round-2 paths and are superseded for M6).
- Secret scan over the retained poll log: 0 hits. Real `config.yaml`/`.env` hashed only, never read.

### 16.2 §6.2 evidence table, all eight mechanisms (one simultaneous window)

Config binding: `<root>\config-home-r3\config.yaml` `bc43b5a9…` (5796 B); `run_cmd`/`use_shell`
quoted verbatim below. YASB `2.0.6` at `C:\Program Files\YASB` (§1). PATH digest `3736ac1a…`
identical before (22:58:39Z) and after (23:01:26Z), `contains_yasb_limitora=False`. All six
arrangement exes `93db5fbd…` before and after; M6 short-path round-trip True. Screenshot bound
inside the window (`inside_monitor_window=True`). Post-run residue 0.

| ID | `run_cmd` (verbatim) / `use_shell` | Widget render (screenshot) | Child argv[0] / tokens / ancestry | stdout contract | Exit code | §6.2 result |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | `yasb-limitora` / `false` | snapshot `Quota 79% remaining; state=ava…` | bare token → **unrelated pyenv** exe `76fb2532…` (33336/35044/24756/27204), single token, direct child of 2480, no shell segment | rendered (parsed) | in-session unavailable; control | control; **never selectable** |
| M2 | `yasb-limitora` / `false` | `Quota not run` (guard contention) | as M1 | rendered | in-session unavailable; control | control; **never selectable** |
| M3 | `C:\…\arrangements-r3\m3-spacefree\bundle\yasb-limitora.exe` / `false` | snapshot `Quota 79% remaining; state=availab…` | argv[0] = exact path, single token (21452, 36592), direct child of 2480, segment `yasb-limitora.exe ← yasb.exe` shell-free | rendered + §12 direct-run parse (`0ed3a41c…`, root keys `execution_error/execution_state/providers`, no root `version`) | §12 direct run exit 0; in-session unavailable | feasible, space-free class; **not selected** |
| M4 | `"C:\…\arrangements-r3\m4 quoted spaced\bundle\yasb-limitora.exe"` / `false` | `Loading…` (empty state) | **no spawn observed** (0 records) | none | n/a | **fail as expected**; run+recorded |
| M5 | `C:\…\arrangements-r3\m5 unquoted spaced\bundle\yasb-limitora.exe` / `false` | `Quota not run` (guard contention) | spawned with **quoted** full path, single token (15056, 33060), direct child of 2480, shell-free segment | rendered | in-session unavailable | recorded; **not selectable**; contradicts the naive upstream `.split(" ")` model (unquoted spaced spawned; quoted M4 did not) — mechanism inference only, no adoption consequence |
| M6 | `<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe` / `false` | `Quota not run` (guard contention; label rendered from live parsed JSON, not empty/error) | argv[0] = exact verified-unique 8.3 short path, single token (23596, 34176), exe = frozen `93db5fbd…`, direct child of 2480, segment shell-free | rendered + **§17 exact-command direct-run** full contract parse (`fe609c77…`, root keys `execution_error/execution_state/providers`, no root `version`, 0 selectors) | **§17 exact-command direct run exit 0**; in-session explicitly unavailable | **PASS — SELECTED** |
| M7 | `"C:\…\arrangements-r3\m7 shell spaced\bundle\yasb-limitora.exe"` / `true` | raw template literal (no data) | **no spawn; `cmd.exe` count 0 in the whole capture** | none | n/a | **fail**; diagnostic only, never counts |
| M8 | `C:\…\arrangements-r3\m8-launcher-spacefree\bundle\yasb-limitora.exe` / `false` | `Quota not run` (guard contention) | argv[0] = exact path, single token (13484, 25796), direct child of 2480, shell-free segment | rendered + §12 direct-run parse | §12 direct run exit 0; in-session unavailable | feasible; **not selected** |

`Quota not run` is the frozen candidate's contract-valid `not_run` presentation
(`src/yasb_limitora/projection.py`), produced here by its designed single-instance guard lease under
the 16-spawn simultaneous burst (`guard_wait_timeout`); it is neither an empty nor an error state,
and M1/M3 rendered live snapshots in the same window. Grandchildren with
`--multiprocessing-fork …` tokens are internal PyInstaller multiprocessing respawns of the frozen
bundle, not YASB-spawned commands; rule 4 is evaluated on the direct children of PID 2480, all of
which carry exactly one token.

### 16.3 Selection: exactly one mechanism — **M6**, with bounded machine-class behavior

- **Selected:** M6 — 8.3 short-path alias of the spaced resolved path, `use_shell:false`, no PATH.
- **Class SF (resolved install path space-free):** short alias is space-free (equals or aliases the
  literal path); behavior proven by M3 and M6 space-free spawns in this session.
- **Class SP-83 (spaced path, 8.3 generation enabled):** proven by the M6 prototype — real frozen
  bundle inside a spaced directory, invoked through its verified unique space-free short alias,
  spawned directly by the real release-target YASB with clean argv and shell-free ancestry.
- **Class SP-no83 (spaced path, 8.3 disabled):** M6 unavailable; the installer must follow design
  §6.3 (a)–(d): install successfully, skip writing any integration command, inform the user, and
  report the class **unproven, not passed**; such an unproven required class blocks G2b. Recorded
  honestly as M6's real limitation.
- **Why not M3:** §6.3 forbids selecting an M3-only arrangement as spaced-class coverage.
  **Why not M8:** needs a space-free, user-writable, non-elevated directory that Windows does not
  guarantee, plus a second launcher artifact with its own custody/cleanup; M6 keeps one install
  identity. M8 remains a recorded feasible fallback, not the selection.

### 16.4 Verdict and explicit non-claims

**G2a = `pass (feasibility/selection only)`; selected mechanism M6.** The §12 simultaneity gap
(evidence identity `sha256:0e4af39a58c510dd073b40a4a4dbf9462647633e825efc7b7bfcf7c96e3a7cc1`) is
**remediated**: screenshot, child argv, and ancestry now come from one simultaneous captured window
with integrity binding. This pass establishes feasibility and selection for S04c only. It does
**not** claim installer guaranteeability, S04c adoption, retained-candidate inclusion,
`yasb-spaced-path` ledger acceptance, or publication pass; overall G2 closes only via G2b against
the exact retained candidate. `tasks.md` G2a checkbox is checked with this record; S04c remains
sequenced after S10's static installer path/identity contract (selection depends on install-time
short-path computation).

## 17. Bounded exact-M6 evidence remediation — direct run of the EXACT r3 command (2026-09-07)

**Remediated failed verification:** `sha256:8ad2c24fdab0a9dc9fda638596ce556ada9c1a7b825eacdb1f7ebc261ddf796a`,
after a maintainer-authorized reset. Rejection cause: §16's M6 pass/selection cited the §12
complementary direct runs for rule-5/6 (stdout contract + exit code), but §12's M6 run executed the
**round-2** short path `<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~1\M4M5M6~1\bundle\YASB-L~1.EXE`
— a different command string than the exact r3 command the live session spawned
(`…\YASB-G~1\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe`, widget `g2a_r3_m6` of
`config-home-r3\config.yaml` `bc43b5a9…`). The retained r3 live evidence itself was not the
rejected element. This section is the bounded remediation; no S04c work occurred.

### 17.1 What was executed (once, bounded, no YASB)

- Precondition gate: read-only CIM check found **no `yasb.exe` / `yasb-limitora.exe` process** before
  the run (YASB already closed per §14; the executor never launched, stopped, or controlled YASB).
- The exact r3 M6 `run_cmd` was quoted from the disposable config `config-home-r3\config.yaml`
  (SHA-256 `bc43b5a9…`, unchanged) and executed **once** directly: `subprocess.run([exe],
  shell=False)` — argv list of exactly one executable token, bounded 30 s timeout, `cwd` = the
  capture directory, inherited environment **unmodified**; no env/PATH/config/YAML/CSS mutation
  anywhere. Ancestry: `yasb-limitora.exe ← python.exe (3.10.5) ← harness shell` — a direct harness
  execution, **not** a YASB spawn; no stdout interception from YASB is claimed.
- Runner `capture\exact-m6-r3\run-exact-m6.py` (SHA-256 `ce4b5ca868262de4d5039278001a6d6e93822177a5c5f5cb65f0482093bab267`);
  structured record `capture\exact-m6-r3\exact-m6-r3.json` (SHA-256 `e01fa6c2ab0b5dc8c35d49f519be070b356e094b44139c14b8a9a5825d83c81b`).

### 17.2 Captured fields

| Field | Value |
| --- | --- |
| Command (verbatim, `config-home-r3\config.yaml`) | `<user-home>\AppData\Local\Temp\YASB-G~1\ARRANG~2\M6SHOR~1\bundle\yasb-limitora.exe`, `use_shell: false` |
| Timestamps (UTC) | start `2026-09-07T23:27:11.694248Z` → end `2026-09-07T23:27:14.091050Z`; duration 2.407 s; no timeout |
| Exit code | **0** |
| stdout raw bytes | 2124 B; SHA-256 `fe609c77cc4ec86a149baa4b8583dc91a6e4b9f0852ee0df0b0b84f46bc8843c`; retained `exact-m6.stdout.raw.bin`; redacted copy byte-identical |
| stderr raw bytes | empty; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| JSON parse / root keys | ok; exactly `execution_error, execution_state, providers`; **no root `version`**; 0 selector placeholders |
| Contract content | `execution_state=partial` (contract-valid); `providers[0]` `outcome=snapshot`, `compact_text="Quota 66% remaining; state=available; freshness=fresh"`, full presentation field set |
| Command path long/short resolution | `GetLongPathNameW(short)` = `…\arrangements-r3\m6 shortpath spaced\bundle\yasb-limitora.exe` (the exact M6 bundle); the short command path contains no space |
| Executable identity | exe SHA-256 via short path AND long path both `93db5fbd58b92ea37e692ce738e508b50ffa1ccc69ea5bb7b5455b8f44a798b0` = frozen S02b candidate (recomputed at the source, matches) |
| Complete onedir binding | full bundle 70 files; `_internal\build-info.json` SHA-256 `f783582af3a79b4a21598f8b45ac951f203099ae0c6787e6c4feee52bc22763a` (0.2.0 provenance) |
| PATH before == after | canonical combined SHA-256 `3736ac1a909fc1ef41679c9d9b445b082093865712a7ad886eaf8d63ad522a44` identical; Machine len 971 / User len 1961; `contains_yasb_limitora=False` |
| Real YASB config/`.env` | `728af2dc…` / `3bdaf891…` — hash-checked unchanged; contents never read |
| Secret scan / redaction | 0 hits over stdout+stderr; redaction a verified no-op |
| Process cleanup | 0 `yasb-limitora` processes before and after; no residue; post-run CIM gate re-confirmed no `yasb.exe`/`yasb-limitora.exe` |

### 17.3 Why the acceptance evidence composes two separate executions

Under clarified design §6.2 rules 4–7, §16 alone supplies same-session exact YAML/use_shell,
rendering, argv, and direct YASB→child binding: no cmd/powershell/pwsh/conhost between them;
recorded ancestors above YASB do not fail. §17 supplies only stdout/exit, conditional on verbatim
run_cmd, shell=false, one-token argv, unchanged environment/PATH, and immutable same complete
PyInstaller onedir/exe/build-info identity. Missing/mismatched binding fails; equivalent paths,
alternate short spellings, and exe-hash-only matches do not qualify. This is not YASB stdout interception.

G2a pass/M6 selection now relies on exactly two retained records that are **separate executions by
separate processes**, deliberately composed and never conflated:

- **(a) Retained r3 live session (§16, `g2a-evidence-rev-r3-session-1`):** proves the real
  release-target YASB 2.0.6 spawned this exact M6 command as a shell-free direct child with
  single-token argv[0] (pids 23596/34176, parent PID 2480) inside one simultaneous captured window,
  and the widget rendered live-parsed candidate JSON (rules 1–4, 7, 8, 9).
- **(b) This §17 exact-command direct run:** proves the same exact command itself emits the
  selector-free JSON contract with no root `version` and exits 0 under `use_shell:false` argv
  semantics (rules 5–6), with executable/complete-onedir identity, long/short path resolution, and
  PATH/config immutability bound to the identical bytes.

(a)'s widget render proves YASB successfully parsed candidate JSON in the live session; (b)
independently proves the contract and exit code of the same exact command's own stdout. **No stdout
interception from YASB or from a YASB-spawned child is claimed anywhere**; in-session exit codes
remain unavailable by polling construction and are not invented.

### 17.4 Status after remediation

- M6 rule-5/6 evidence is now bound to the **exact** r3 command under clarified §6.2. §12's round-2
  direct runs remain historical and superseded for M6; their different M3/M8 paths do not qualify
  as r3 stdout/exit binding. Historical feasibility wording selects neither; exactly M6 remains selected.
- Selection remains exactly one mechanism — **M6** — with §16.3's bounded machine-class behavior
  unchanged: **SF + SP-83 proven; SP-no83 unproven** (installer must follow design §6.3(a)–(d)
  skip+inform; an unproven required class blocks G2b).
- **G2a = `pass (feasibility/selection only)`**, meeting design §6.2 for the selected mechanism;
  the `tasks.md` G2a checkbox remains **checked**.
- **Settlement evidence revision:** `sha256:08655ec0fe7d2ea139ba14272d98514752cfe414fee7cdd0c2dfcd283467f3e7`.
  Its canonical aggregate manifest and validation receipt bind §16/§17 and explicitly remediate failed lineage
  `sha256:aeb474c01a344ecc0ff661e65682afbe861e41febe10070378ce7f2ace54c8bd`, unchanged safe
  environment/PATH evidence, and the pre/live/post 70-file M6 tree digest
  `866cde150798165693e4e98098e70f072655152cd12ad5ea8f4577807c78d47a`.
- Non-claims unchanged: no installer guaranteeability, no S04c adoption (**S04c not started**), no
  retained-candidate inclusion, no ledger acceptance, no publication pass; overall G2 closes only
  via G2b against the exact retained candidate.
- New external files are confined to `capture\exact-m6-r3\` (runner, JSON record, raw/redacted
  stdout/stderr). Repository changes this turn: this §17 plus header/§16 pointer edits,
  `apply-progress.md`, and the `tasks.md` G2a status note. No code/tests/examples/installer/PATH/
  real-config change; cleanup boundary unchanged: delete `<root>` + marker only.
