# yasb-limitora 0.2.0 release notes

yasb-limitora 0.2.0 is the **planned first public release**. As of this
document revision, no tag, installer artifact, or release has been published.
There is no retroactive 0.1.0 release, tag, or compatibility promise; earlier
`0.1.0` repository metadata was a development placeholder that was never
published. This file describes intended release material; it is not a release
announcement or evidence of publication.

## Intended artifact (not yet published)

- The planned public product artifact is the per-user
  `yasb-limitora-0.2.0-setup.exe` installer for Windows 10/11 x64, requiring no
elevation or Python. It is not currently available as a published release.
- The PyInstaller onedir bundle is intended as an internal packaging input and
  verification subject, not a second public distribution form.
- No portable ZIP is planned as a supported distribution form.

## Contract break: issue #137

- The selector-free current JSON document is the **sole supported output**.
- The root `version` field was removed from the JSON document; no replacement
  field exists.
- The removed version-selection surface is invalid: such invocations fail
  closed with `invocation_invalid` and exit code `2`.
- No compatibility selector, v1 fallback, or second JSON contract is
  introduced. Consumer guidance is in `MIGRATION.md`.

## Planned unsigned-release and SmartScreen disclosure

Intended disclosure wording for a future release body:

- The 0.2.0 `setup.exe` is **not Authenticode-signed**.
- Windows SmartScreen may show "Windows protected your PC"; the user chooses
  **More info → Run anyway**.
- Once published, the SHA-256 lets a user verify the download with
  `Get-FileHash -Algorithm SHA256`.
- No code-signing assurance, publisher identity, or trust is implied. Signing
  is not required for 0.2.0, and nothing in this release establishes
  signing-key custody for a future release.

The planned release process requires an artifact manifest, exact SHA-256
values, an SBOM, and provenance/attestation records. No artifact is currently
published.

## Intended 0.2.0 boundaries

- Windows-only runtime: non-Windows invocations exit `2` with
  `yasb-limitora: unsupported_platform` and no stdout bytes.
- Limitora owns provider selection, authentication, transport, and
  interpretation. YASB owns CustomWidget lifecycle and display;
  yasb-limitora never stops, restarts, installs, or uninstalls YASB.
- Configuration, cache, and backups under `%LOCALAPPDATA%\yasb-limitora` are
  separate from program files and retained by default across install,
  upgrade, and uninstall; deletion is an explicit opt-in choice.
- The optional User PATH task is designed as an unchecked direct-CLI
  convenience. G2a selected M6 for feasibility, but installed-candidate G2b
  confirmation remains pending; these notes do not claim verified YASB
  no-PATH integration.

## Status of this document

This file is intended release identity and user material for the approved R11
change. It is not a publication record: no tag, installer artifact, or release
has been published, and publication remains gated by the R11 evidence matrix.
