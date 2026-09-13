# yasb-limitora 0.2.0 release notes

yasb-limitora 0.2.0 is the **first public release**. There is no retroactive
0.1.0 release, tag, or compatibility promise; earlier `0.1.0` repository
metadata was a development placeholder that was never published.

## Supported artifact

- The sole supported public product artifact is the per-user
  `yasb-limitora-0.2.0-setup.exe` installer: Windows 10/11 x64, no elevation,
  no Python required.
- The PyInstaller onedir bundle is an internal packaging input and
  verification subject, not a second supported public distribution form.
- No portable ZIP is published or supported.

## Contract break: issue #137

- The selector-free current JSON document is the **sole supported output**.
- The root `version` field was removed from the JSON document; no replacement
  field exists.
- The removed version-selection surface is invalid: such invocations fail
  closed with `invocation_invalid` and exit code `2`.
- No compatibility selector, v1 fallback, or second JSON contract is
  introduced. Consumer guidance is in `MIGRATION.md`.

## Unsigned release and SmartScreen disclosure

Fixed disclosure wording (repeated verbatim in the release body):

- The 0.2.0 `setup.exe` is **not Authenticode-signed**.
- Windows SmartScreen may show "Windows protected your PC"; the user chooses
  **More info → Run anyway**.
- The published SHA-256 lets a user verify the download with
  `Get-FileHash -Algorithm SHA256`.
- No code-signing assurance, publisher identity, or trust is implied. Signing
  is not required for 0.2.0, and nothing in this release establishes
  signing-key custody for a future release.

The unsigned artifact ships with a release manifest, exact SHA-256 values,
an SBOM, and provenance/attestation records.

## Boundaries preserved in 0.2.0

- Windows-only runtime: non-Windows invocations exit `2` with
  `yasb-limitora: unsupported_platform` and no stdout bytes.
- Limitora owns provider selection, authentication, transport, and
  interpretation. YASB owns CustomWidget lifecycle and display;
  yasb-limitora never stops, restarts, installs, or uninstalls YASB.
- Configuration, cache, and backups under `%LOCALAPPDATA%\yasb-limitora` are
  separate from program files and retained by default across install,
  upgrade, and uninstall; deletion is an explicit opt-in choice.
- The optional User PATH task is an unchecked direct-CLI convenience; YASB
  integration works with PATH unchanged.

## Status of this document

This file is release identity and user material for the approved R11 change.
It is not a publication record: no tag, installer artifact, or release has
been published yet, and publication remains gated by the R11 evidence matrix.
