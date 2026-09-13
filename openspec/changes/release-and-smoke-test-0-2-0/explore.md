# R11 release and smoke-test exploration

## Outcome

R11 can plan the first public Windows 0.2.0 release, but it must first approve the artifact, installation, discovery, lifecycle, security, and acceptance policies. This exploration makes no packaging or installer decision.

## Evidence

- **Scope and tracker state:** `openspec/config.yaml`, `docs/roadmap.md`, README, and research docs identify R11/#62 as the next, unapproved release-and-smoke-test gate. R1–R10 are complete. #130 is complete and integrated through PR #159 (`bdcd29f6`); real OpenCode acceptance in an existing YASB installation remains a separate manual R11 gate. #137 superseded versioned output: the current selector-free, three-root JSON document is sole supported output.
- **First release/versioning:** `pyproject.toml` and `src/yasb_limitora/__init__.py` both say `0.1.0`; repository documentation says the package is not published to PyPI and presently documents editable checkout installation. Per session context, 0.2.0 is the first public release and there must be no retroactive 0.1.0 release.
- **No existing release pipeline:** `pyproject.toml` has no PyInstaller/build tooling; searched workflows contain native source/editable-test proof only, not package build, installer, signing, release, or artifact publication.
- **Frozen seams:** `cli.main()` performs the Windows gate before `multiprocessing.freeze_support()`. `codex_helper` detects `sys.frozen`/`_MEIPASS` and relaunches the frozen executable with a private helper sentinel; tests cover that route. `path.py` explicitly propagates selected PyInstaller child environment keys. These are strong frozen-runtime constraints, but not an actual bundled-binary proof.
- **Windows containment:** Codex uses disposable helper processes, bounded IPC, Job Object containment, deadlines, and cleanup. R11 packaging must preserve helper relaunch, Job assignment/cleanup, no-orphan behavior, and sanitized streams.
- **Mutable state:** default configuration is `%LOCALAPPDATA%\yasb-limitora\config.json`; it is selected only and never auto-created, migrated, or mutated. Cache state also lives below `%LOCALAPPDATA%\yasb-limitora`, under a fingerprinted `quota-v2-cache-*.json` name. Packaged binaries must remain distinct from both.
- **YASB discovery:** examples use bare `run_cmd: "yasb-limitora"` with `use_shell: false`; documentation says this requires inherited user PATH and YASB restart after PATH changes. Archived pinned-YASB evidence records `run_cmd.split(" ")`, making a quoted full path with spaces unsafe without a native spike. The repository’s real generic YASB acceptance used v2.0.6; the split evidence is historical pinned-v2.0.5 evidence and needs revalidation against the release target.
- **Secrets/security:** OpenCode credentials remain only in YASB’s startup-loaded `.env`/effective environment. Existing rules prohibit credentials in Limitora JSON, YAML, argv, output, logs, fixtures, and reports. YAML/CSS/credential auto-editing is forbidden.
- **Current automated proof:** `windows-proof.yml` uses Windows 3.13, a published binary Limitora dependency, editable project install, selected native proof, full suite, safe-log scanning, and checkpoint-9 clean-tree evidence. It does not prove a clean no-Python end-user installation or frozen artifact lifecycle.

## Hypotheses to evaluate, not decisions

- PyInstaller **onedir** is a credible initial candidate because the helper relaunches the same frozen executable and dependencies remain co-located; the session request refers to prior successful onedir history. Engram history was not available to this executor, so that history is not independently verified here.
- A onefile topology needs a separate proof. The code handles frozen execution generally, but repository evidence does not establish onefile correctness, extraction behavior, or Job/helper cleanup. Session-referenced onefile failures should be recovered from Engram before proposal.
- Candidate release materials may include a Windows bundle, installer, checksums/manifest, SBOM/provenance, source archive, and release notes. Their required set and portable-artifact policy are unapproved.
- Reproducibility will require an approved toolchain/version lock, deterministic build inputs, artifact manifest/hash verification, and a clean-machine rebuild comparison; none exists today.

## Product questions required before proposal

1. Which distribution forms are supported: installer, portable onedir archive, both, or neither? Which artifact is canonical?
2. Which installer technology, per-user location, elevation policy, and uninstall registration are approved?
3. Is PATH modified at all? If so, how are existing processes/YASB restart, rollback, and non-PATH discovery handled?
4. What exact installed layout is promised, and which files are immutable package files versus `%LOCALAPPDATA%` user state?
5. What do clean install, reinstall, upgrade, repair, failed install/rollback, and uninstall do to config, cache, logs, and any future state? What state deletion requires explicit consent?
6. What must happen when YASB is absent, installed but stopped, or running? No option may automatically modify YASB YAML, CSS, or `.env`.
7. Which native YASB spike resolves bare PATH, quoted paths with spaces, `run_cmd.split(" ")`, and `use_shell` behavior? `use_shell: true` must not be selected merely to bypass parsing.
8. Are code signing, SmartScreen handling, checksum/signature publication, SBOM/provenance, and signing-key custody release blockers or documented limitations?
9. What precise RC and release thresholds apply: clean Windows/no Python smoke, frozen helper/Job cleanup, source regression, installer lifecycle, real-YASB/OpenCode manual acceptance, and post-release smoke?
10. How will the 0.1.0 placeholder be updated atomically in package metadata/runtime/version reporting, and how will notes truthfully state “first public 0.2.0 release” and the #137 wire break?

## Candidate smoke matrix

| Area | Required evidence to approve |
|---|---|
| Build | Clean Windows build, pinned inputs, recorded tool versions, manifest and integrity verification |
| Clean install | Native Windows user with no Python; command discovery and JSON/stream/exit contract |
| Frozen runtime | Normal CLI, frozen internal helper, multiprocessing bootstrap, Job containment, timeout cleanup, no descendant processes |
| State | Existing config/cache preserved or changed only under approved policy; no config creation/migration by accident |
| Lifecycle | Reinstall, upgrade, repair, uninstall, failed-operation rollback; YASB absent/running cases |
| Discovery spike | Current real YASB path parsing and inherited PATH behavior, including a path-with-spaces case |
| Security | No YAML/CSS/`.env` edits; secret scan of logs/evidence/artifacts; approved signing/integrity policy |
| Release gates | CI source/native proof; RC manual real-YASB OpenCode acceptance; post-release clean-machine smoke |

## Review shape

Natural capability boundaries are: policy decisions; frozen build/artifact proof; installation and lifecycle; discovery spike; CI/release provenance; and manual RC/post-release evidence. An all-in-one implementation would likely exceed the 400-line review budget. These are capability groupings only, not tasks or PR topology.

## Parent-recovered evidence and remaining gaps

The parent session verified GitHub #37/#62 and current upstream YASB/PyInstaller evidence before this phase. Issue #62 remains an unapproved planning anchor. Current upstream YASB still splits `run_cmd` with `.split(" ")`, and upstream issue #815 remains open. PyInstaller documents onefile extraction to a temporary `_MEI...` directory and slower startup than onedir.

Engram observations 2201, 2114, 2226, 2234, and 2266 record repeated successful native PyInstaller onedir bundles with frozen helper, Windows Job, stream, redaction, and no-orphan evidence. Observation 2150 records that onefile could not complete the bounded frozen child path while onedir passed it. Therefore onedir is the evidence-backed frontrunner, but proposal approval is still required before it becomes the R11 distribution decision.

The remaining gaps are product choices, a current real-YASB path-with-spaces spike, installer lifecycle evidence, clean no-Python installation proof, signing policy, and release acceptance thresholds.
