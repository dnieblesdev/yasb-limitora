# Release and smoke-test the first public 0.2.0 product

## Intent

Prepare the first public Windows release of `yasb-limitora` as version 0.2.0 and prove that a real user can install, run, upgrade, and remove it safely. R11 turns the completed Windows CLI, frozen-runtime seams, current JSON contract, and YASB CustomWidget integration into a releaseable product without changing provider ownership or silently editing a user's YASB configuration.

0.2.0 is the first public product release. There will be no retroactive 0.1.0 release, tag, or compatibility promise.

Research admission is explicitly deselected for this change. The blocked `research.md` audit is historical context, not a dependency or source of approval. This proposal uses the exploration, current repository documentation, and the confirmed product decisions supplied for R11. External and native claims still require the acceptance evidence described below.

## Desired product outcome

A Windows 10/11 user without Python can download the one supported public product artifact, a per-user `setup.exe`, install `yasb-limitora`, and use the existing YASB CustomWidget integration and current JSON contract. The installer must keep packaged program files separate from mutable per-user state, work without modifying PATH, and leave YASB lifecycle and provider credentials under their existing owners.

The release process must produce final-version 0.2.0 candidate artifacts in CI, validate their exact hashes and release evidence, and publish those exact validated artifacts. `RC` is an internal workflow state only; it is not a public `-rc` tag or version.

## Scope

### In scope

- Set and report the product version as 0.2.0 consistently in the approved package, runtime, installer, and release materials. Describe it as the first public release; do not publish 0.1.0 retroactively.
- Build the evidence-backed internal frozen runtime candidate with PyInstaller onedir. The supported public artifact is an Inno Setup per-user `setup.exe`; it is not a portable ZIP. The onedir bundle is a packaging input and verification subject, not a second supported public distribution form.
- Install under a per-user program location distinct from mutable `%LOCALAPPDATA%\\yasb-limitora` configuration, cache, and state. Exact directory constants and installed layout remain design details.
- Provide install, reinstall, upgrade, and failure/rollback handling; any repair behavior remains a design question. Uninstall preserves config/cache/state by default.
- Offer an optional User PATH installer task, unchecked by default, only as a convenience for direct CLI use. YASB integration must work without PATH.
- Resolve and prove YASB integration in a real release-target environment, including a release-blocking path-with-spaces spike. Do not select `use_shell: true` merely to bypass command parsing.
- Detect YASB when possible. If YASB is absent or its configuration cannot be detected, still install successfully, skip YASB-specific integration, and inform the user.
- If YASB is running during install, upgrade, or uninstall, ask the user to close it manually before continuing. `yasb-limitora` must never stop, restart, install, uninstall, or otherwise manage YASB lifecycle.
- With explicit user consent, optionally manage a commented, idempotent `yasb-limitora` block in YASB `.env`. The managed behavior must never write secrets, edit YASB YAML/CSS, or enable providers by default.
- Provide an opt-in provider wizard that can atomically create or update the `yasb-limitora` `config.json`, with backup, safe merge, validation, and rollback for runtime-valid documents, preserving fields the wizard does not own within the accepted contract. If an existing `config.json` fails the current runtime contract, including because of unknown fields, the wizard abandons only the optional configuration operation, preserves the original file byte-for-byte, enumerates detected validation errors, and allows install/upgrade to continue. This optional configuration failure is nonfatal to the program-file installation transaction. It never repairs, normalizes, drops fields, loosens runtime validation, or reserializes the invalid document. A provider is enabled only by explicit user selection. Missing secrets or external prerequisites must never change enabled state automatically; the installer warns that a selected provider may not function until its requirements are met.
- Preserve config/cache/state on uninstall by default. An explicit cleanup option, unchecked by default, may delete those data files when the user chooses it.
- Produce release evidence and materials for an unsigned release: SmartScreen disclosure, SHA-256 values, a manifest, SBOM, and provenance/attestation. Signing is not required for 0.2.0, but custody and future-signing design must not be implied by this release.
- Execute the smoke and acceptance matrix covering clean Windows with no Python, frozen runtime and helper behavior, multiprocessing bootstrap, Job containment, deadlines, sanitized streams, no-orphan cleanup, optional PATH, installer lifecycle, YASB boundaries, and at least one representative live supported-provider flow. A specific provider is mandatory only when that release changes the provider.
- Publish release notes and migration guidance that explain the first public 0.2.0 release and the #137 contract break: the current selector-free JSON document is the sole supported output and consumers must not rely on the removed version-selection surface or root version field.

### Out of scope

- Any public 0.1.0 release, retroactive tag, or compatibility layer for the placeholder version.
- A portable ZIP or any second supported public distribution form.
- Native YASB widget code, an upstream YASB contribution, or changes to YASB's lifecycle behavior.
- Automatic YASB stop/restart/install/uninstall or process management by `yasb-limitora`.
- Automatic edits to YASB YAML, CSS, credentials, secrets, argv, logs, output, fixtures, or reports. The only permitted YASB configuration assistance is the explicitly consented, commented, idempotent `.env` block described above.
- Automatic provider enabling, provider logic, authentication, transport, or duplicated provider behavior. Limitora remains the owner of provider selection, authentication, transport, and interpretation.
- New providers or provider-contract changes that are not part of the release; live proof for a particular provider is required only when that release changes it.
- A public `-rc` tag/version, a dual release channel, or publication of unvalidated candidate artifacts.
- Changes to the current JSON contract beyond the already-confirmed #137 migration, or expansion beyond the Windows-only product boundary.
- Editing GitHub issue #62 as part of this proposal phase.

## Compatibility impact

This is a product-distribution change and a deliberate pre-stable compatibility boundary:

- The first public version is 0.2.0. Existing repository metadata that says 0.1.0 is a placeholder and must not become a public release.
- The current selector-free JSON document remains the sole supported output. Release notes and migration guidance must plainly call out the #137 contract break, including removal of the root `version` field and version-selection surface. No compatibility selector or v1 fallback is introduced.
- The Windows-only runtime, sanitized output, streams, exit codes, bounded execution, helper relaunch, Job containment, deadlines, cleanup, and Limitora ownership invariants remain compatibility requirements for the packaged runtime.
- Installation no longer depends on Python or an editable checkout. The public installation is per-user and separates immutable program files from `%LOCALAPPDATA%\\yasb-limitora` mutable state.
- PATH is an optional direct-CLI convenience and is not an integration prerequisite. YASB integration must continue to work when PATH is unchanged.
- Reinstall, upgrade, and uninstall must not silently delete existing config/cache/state. Uninstall cleanup is opt-in.
- Existing `config.json` handling is reject-and-preserve: a document that fails the current runtime contract, including one with unknown fields, is preserved byte-for-byte, its detected validation errors are enumerated, and only the optional configuration operation is abandoned while install/upgrade continues. This optional configuration failure is nonfatal to the program-file installation transaction. Runtime validation is not loosened, and the invalid document is never repaired, normalized, partially rewritten, or reserialized. Runtime-valid documents continue through atomic backup/safe merge/validation/rollback while preserving fields the wizard does not own within the accepted contract.
- No YASB YAML/CSS/credential compatibility behavior is added. Any consented `.env` block is commented, idempotent, and limited to the approved integration purpose.

## Affected areas

| Area | Required outcome | Preservation boundary |
| --- | --- | --- |
| Version and release metadata | Consistent first-public 0.2.0 identity and release notes/migration material. | No public 0.1.0 and no `-rc` public identity. |
| Frozen build and artifact pipeline | Reproducible-enough PyInstaller onedir evidence packaged by Inno Setup as the per-user `setup.exe`. | No portable ZIP as a supported artifact; preserve frozen helper and dependency behavior. |
| Installer and mutable state | Per-user installation, lifecycle operations, default state retention, explicit cleanup choice, and user-facing diagnostics. | Program files stay separate from `%LOCALAPPDATA%\\yasb-limitora`; no silent state loss. |
| CLI and process boundary | No-Python execution with the existing current JSON contract, helper, Job, deadline, stream, sanitization, and cleanup guarantees. | Preserve Windows-only behavior and no-orphan invariants. |
| PATH and YASB discovery | Optional unchecked User PATH task and a real-YASB, spaced-path proof of integration without PATH. | Never manage YASB lifecycle; never use PATH as an implicit YASB requirement. |
| YASB configuration boundary | Absent/undetected YASB remains installable; consented `.env` block and opt-in provider wizard obey narrow mutation rules. Invalid existing `config.json` abandons only the optional operation, and the failure is nonfatal to the program-file installation transaction during install/upgrade. | Never write secrets or edit YAML/CSS; reject-and-preserve invalid config byte-for-byte, enumerate validation errors, never repair or reserialize it, and use atomic backup/safe merge/validation/rollback only for runtime-valid config while preserving fields not owned within the accepted contract. |
| CI and acceptance | Final-version candidate artifacts, exact-hash validation, SBOM/provenance, smoke matrix, and promotion of the exact validated artifacts. | RC is internal; no unvalidated artifact publication. |

## Security and ownership boundaries

- **Limitora owns** provider selection, authentication, transport, and provider interpretation. Credentials remain in YASB startup-loaded `.env`/effective environment and are never copied into `config.json`, installer arguments, logs, output, fixtures, reports, or release artifacts.
- **yasb-limitora owns** configuration resolution, bounded execution, sanitized projection, and the CLI/process boundary. The packaged runtime must preserve fail-closed diagnostics, redaction, deadlines, Job containment, and cleanup.
- **YASB owns** CustomWidget lifecycle and display. `yasb-limitora` may ask the user to close YASB and may, only with explicit consent, maintain the approved commented `.env` block; it never controls YASB lifecycle or edits YAML/CSS.
- Installer actions must be least-privilege per-user operations. They must not require an elevation path that changes the per-user ownership model unless the design explicitly proves why it is necessary.
- The provider wizard must validate an existing `config.json` against the current runtime contract before any optional configuration write. If validation fails, including for unknown fields, it must abandon only that optional operation, preserve the original file byte-for-byte, enumerate detected validation errors, and allow install/upgrade to continue as a nonfatal outcome for the program-file installation transaction; it must never repair, normalize, drop fields, loosen runtime validation, or reserialize the invalid document. For a runtime-valid config, it must use atomic writes, backup, safe merge, validation, and rollback while preserving fields it does not own within the accepted contract. It must not infer consent or enabled state from missing secrets or prerequisites.
- Release evidence must include secret scanning and integrity/provenance records. An unsigned 0.2.0 must disclose that limitation and SmartScreen behavior rather than implying trust that is not present.

## Acceptance evidence

R11 is release-ready only when the following evidence is reviewable. Evidence may be automated, native, or manual as identified; a skipped external gate is not a pass.

### Build and artifact

- A clean Windows build records the pinned source/tool versions and inputs.
- The PyInstaller onedir candidate starts the normal CLI and its frozen internal helper, with dependencies co-located as required.
- Inno Setup produces the unique supported public artifact, a per-user `setup.exe`; no portable ZIP is presented as supported.
- Candidate and final artifacts have a manifest and exact SHA-256 values. CI validates the candidate hashes, and final publication uses those exact validated bytes.
- SBOM and provenance/attestation are retained. Release notes disclose that 0.2.0 may be unsigned and explain SmartScreen implications.

### Clean installation and runtime

- On a clean Windows machine with no Python, install succeeds for a normal per-user user and the installed CLI produces the current JSON/stream/exit contract.
- Normal CLI execution, frozen helper relaunch, multiprocessing bootstrap, bounded deadlines, Windows Job containment, sanitized output, and no-descendant/no-orphan cleanup are proven.
- Repeated install/reinstall/upgrade and approved failed-operation rollback paths are exercised without corrupting the program installation or mutable state.
- `%LOCALAPPDATA%\\yasb-limitora` config/cache/state is distinct from installed program files and is retained by default across lifecycle operations.
- The User PATH task is visibly optional and unchecked by default; direct CLI use is proven with it enabled and disabled. YASB integration is proven with PATH unchanged.

### YASB and configuration boundaries

- A current real-YASB installation proves the no-PATH integration path, including a release-blocking `run_cmd` path-with-spaces spike against the release target. The result must not depend on `use_shell: true` as a parsing bypass.
- Install behavior is proven for YASB absent and YASB configuration undetected: installation succeeds, YASB-specific integration is skipped, and the user is informed.
- When YASB is running during install, upgrade, or uninstall, the user receives a manual-close request; the product performs no automatic YASB stop, restart, install, uninstall, or lifecycle management.
- With explicit consent, the `.env` operation is commented and idempotent; tests/evidence prove no secret write and no YAML/CSS edit.
- The opt-in provider wizard proves that runtime-valid config receives atomic create/update, backup, safe merge, validation, and rollback while preserving fields it does not own within the accepted contract. It also proves that an existing config failing the current runtime contract, including with unknown fields, causes only the optional configuration operation to be abandoned: the original file remains byte-for-byte identical, detected validation errors are enumerated, install/upgrade continues as a nonfatal outcome for the program-file installation transaction, and no repair, normalization, field dropping, validation loosening, or reserialization occurs. Provider enabled state changes only from explicit selection, while missing requirements produce a warning without automatic state changes.
- Uninstall preserves config/cache/state by default. The default-unchecked cleanup option deletes them only when explicitly selected.

### Release and migration

- CI source/native proof and the applicable full test suite pass under repository policy; native Windows proof is required where the environment supports it.
- An internal RC workflow validates final-version 0.2.0 candidate artifacts without creating a public `-rc` tag/version.
- Final publication is traceable to and byte-identical with the exact validated candidate artifacts.
- Release notes and migration guidance state that 0.2.0 is the first public release and explain the #137 current-JSON contract break.
- At least one representative live supported-provider flow is proven. A named provider is mandatory only when the release changes that provider; otherwise existing supported-provider coverage and a representative live flow suffice.
- Post-release clean-machine smoke is recorded before R11 closeout.

## Unresolved technical design questions

These are implementation and evidence questions, not invitations to reopen the confirmed product decisions:

1. What exact per-user program directory, installed file layout, uninstall registration, repair behavior, and Inno Setup metadata satisfy the separate-program/state boundary?
2. Which PyInstaller version, hidden imports/data rules, build environment, and deterministic-input controls are required to make the onedir candidate reproducible and to prove frozen helper behavior?
3. How will install/upgrade/uninstall detect a running YASB instance, present the manual-close gate, and handle cancellation, stale detection, or a failed continuation without managing YASB lifecycle?
4. What release-target YASB discovery and invocation path works without PATH, including a command path containing spaces and the target version's actual `run_cmd` parsing? What exact spike result blocks release?
5. How are absent YASB and undetected configuration distinguished for user messaging without making installation dependent on discovery?
6. What exact commented block format, ownership marker, atomicity, idempotence rules, and failure recovery apply to the explicitly consented `.env` operation?
7. What exact validation and user-facing error-enumeration rules identify an existing `config.json` that fails the current runtime contract, including unknown fields, while preserving it byte-for-byte and continuing install/upgrade after abandoning only the optional configuration operation? For a runtime-valid config, what schema and merge rules provide backup, atomic safe merge, validation, rollback, and preservation of fields the wizard does not own within the accepted contract, while never handling secrets?
8. What installer error, cancellation, rollback, and cleanup semantics apply when files are locked or state is malformed, while preserving state by default?
9. Which manifest, SHA-256, SBOM, provenance/attestation formats, SmartScreen disclosure text, and artifact-retention locations are required for the unsigned release?
10. How will CI represent internal RC status, retain final-version 0.2.0 candidates, compare exact hashes, and promote the same bytes at final release?
11. Which repository version-reporting, documentation, and migration surfaces must change together so no active path reports placeholder 0.1.0?
12. Which clean-machine, real-YASB, and live-provider environments are available, and how will their logs and screenshots be retained after secret scanning and redaction?

## Expected capability slices

These are natural capability boundaries for later design and implementation; they are not tasks, issue assignments, or PR topology:

1. **Release policy and version identity** — 0.2.0 first-public semantics, #137 migration material, artifact policy, unsigned disclosure, and release gates.
2. **Frozen build and provenance** — PyInstaller onedir proof, Inno Setup input/output, manifests, exact hashes, SBOM, provenance, and candidate promotion.
3. **Per-user installer lifecycle** — install/reinstall/upgrade/rollback/uninstall, program/state separation, default retention, and explicit cleanup.
4. **Discovery and real-YASB spike** — no-PATH invocation, spaced-path proof, optional direct-CLI PATH task, YASB detection/messaging, and manual-close behavior.
5. **Configuration-assistance boundaries** — consented commented `.env` block and opt-in provider wizard with runtime-contract validation, reject-and-preserve handling for invalid config, and safe atomic merge, backup, validation, and rollback for runtime-valid config.
6. **Runtime and release acceptance** — clean no-Python smoke, frozen helper/Job/no-orphan proof, security scans, representative live-provider proof, RC evidence, and post-release smoke.

Delivery is intended to use the auto-chain strategy with a 400-line review budget. The later design phase must keep these capability boundaries independently reviewable without prescribing task or PR topology here.

## Risks and mitigations

- **Frozen packaging changes process behavior.** PyInstaller may expose helper, multiprocessing, dependency, or Job-cleanup faults not visible from source tests. Mitigate with a clean no-Python frozen proof, helper relaunch checks, process-tree inspection, deadlines, and no-orphan evidence.
- **YASB command parsing is path-sensitive.** A spaced executable path may fail in the release-target YASB parser. Treat the real-YASB spaced-path spike as release-blocking; do not hide the failure with `use_shell: true` or make PATH a hidden prerequisite.
- **Installer lifecycle can damage user state.** Locked files, partial upgrades, or uninstall defaults could delete or corrupt data. Keep program files separate, preserve state by default, use backup/atomicity/rollback, and test interrupted and failed paths.
- **Configuration assistance can cross ownership boundaries or destroy an invalid user document.** Broad edits could expose secrets, alter YASB behavior unexpectedly, or overwrite a config that the current runtime contract rejects. Restrict edits to the explicitly consented commented `.env` block and the opt-in provider operation; for any invalid existing `config.json`, including one with unknown fields, abandon only the optional configuration operation, preserve the original byte-for-byte, enumerate detected validation errors, continue install/upgrade without failing the program-file installation transaction, and never repair, normalize, drop fields, loosen validation, or reserialize it. For runtime-valid config, use backup, atomic safe merge, validation, rollback, and preservation of fields not owned within the accepted contract; never write secrets/YAML/CSS, and keep provider enabled state tied only to explicit selection.
- **Undetected YASB could block installation.** Discovery is environment-dependent. Make installation succeed independently, skip only YASB-specific integration, and provide clear information.
- **Unsigned distribution may trigger SmartScreen or user distrust.** Disclose the unsigned status and SmartScreen behavior, publish exact SHA-256, manifest, SBOM, and provenance/attestation, and avoid implying code-signing assurance.
- **Candidate drift could invalidate release evidence.** A rebuilt final artifact may differ from the tested RC. Store and hash final-version candidates, validate exact bytes, and publish only those exact artifacts.
- **The #137 contract break may surprise existing consumers.** Make the first-public 0.2.0 status and migration path explicit; do not create an undocumented compatibility mode.
- **Live-provider evidence may be unsafe or unavailable.** Use a representative supported-provider flow with secret-safe evidence; require named-provider proof when that provider changes and report any remaining external gate honestly.

## Rollback

Rollback is a release and installer rollback, not a second public artifact contract. Before publication, reject or quarantine any candidate that fails exact-hash, native, lifecycle, YASB, security, or provider gates; do not publish it under an RC or final tag. Final publication must be able to point back to the exact validated candidate bytes.

For an installed user, failed install/upgrade must restore the prior program installation according to the approved installer transaction design and must not remove mutable state by default. Uninstall keeps `%LOCALAPPDATA%\\yasb-limitora` unless the user explicitly selects the default-unchecked cleanup option. A source rollback to the prior repository revision is allowed if release work is rejected; it must not introduce a permanent portable ZIP, dual JSON contract, automatic YASB lifecycle, or broad configuration-edit fallback.

## Success criteria

- [ ] 0.2.0 is consistently identified as the first public release, with no retroactive 0.1.0 release and no public `-rc` tag/version.
- [ ] The only supported public product artifact is the per-user Inno Setup `setup.exe`; PyInstaller onedir is proven as the internal runtime candidate and no portable ZIP is supported.
- [ ] Program files are installed per-user separately from `%LOCALAPPDATA%\\yasb-limitora` mutable state, which is preserved by default through lifecycle operations.
- [ ] Install, reinstall, upgrade, approved rollback, and uninstall evidence passes, including the manual-close prompt when YASB is running and the explicit default-unchecked cleanup option.
- [ ] The optional User PATH task is unchecked by default and is proven to affect only direct CLI convenience; YASB integration works without PATH.
- [ ] The real release-target YASB spaced-path spike passes as a release-blocking gate, and absent/undetected YASB produces an informative non-blocking outcome.
- [ ] No YASB lifecycle is managed, no YASB YAML/CSS or secrets are written, and the only permitted `.env` mutation is the explicitly consented commented, idempotent block.
- [ ] The opt-in provider wizard proves atomic backup/safe merge/validation/rollback for runtime-valid config while preserving fields it does not own within the accepted contract. It proves reject-and-preserve behavior for invalid existing config, including unknown fields: only the optional configuration operation is abandoned, the original file remains byte-for-byte identical, detected validation errors are enumerated, install/upgrade continues without failing the program-file installation transaction, and the invalid document is never repaired, normalized, partially rewritten, validation-loosened, or reserialized. Enabled state changes only by explicit provider selection.
- [ ] Frozen CLI/helper/multiprocessing/Job/deadline/stream/sanitization/no-orphan behavior remains proven on clean Windows with no Python.
- [ ] Unsigned-release disclosure, SHA-256, manifest, SBOM, provenance/attestation, secret scans, and exact candidate-to-final artifact identity are reviewable.
- [ ] Release notes and migration guidance explain first public 0.2.0 and the #137 contract break.
- [ ] A representative live supported-provider flow and required post-release clean-machine smoke are recorded; named-provider proof is required when that provider changes.
- [ ] Focused and full repository tests pass under `openspec/config.yaml`, applicable native Windows proof is run, and any unavailable external evidence is explicitly reported rather than treated as passed.
