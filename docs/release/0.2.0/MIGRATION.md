# Migrating to yasb-limitora 0.2.0

0.2.0 is the **first public release** of yasb-limitora. This guide is for
consumers of the current JSON document and for anyone who installed a
development checkout before the release existed.

## From an editable checkout to setup.exe

1. Remove any editable development install: `py -m pip uninstall yasb-limitora`.
2. Run the per-user `yasb-limitora-0.2.0-setup.exe`. It needs no Python and
   no elevation, and installs program files under
   `%LOCALAPPDATA%\Programs\yasb-limitora`.
3. The editable-checkout route (`py -m pip install -e .`) remains
   **development-only**; it is not a supported end-user installation.

## JSON contract: the #137 break

- The current selector-free JSON document is the sole supported output.
- The root `version` field no longer exists. Consumers that read it must
  stop; there is no replacement field, no compatibility selector, and no v1
  fallback.
- The removed version-selection surface is invalid and fails closed with
  `invocation_invalid` and exit code `2`.
- Migrate by consuming the current document exactly as documented in
  [`docs/windows-json.md`](../../windows-json.md).

## PATH is optional

The installer offers an optional User PATH task, **unchecked by default**,
for direct CLI convenience only. YASB CustomWidget integration does not
require PATH: it uses the installer-provisioned no-PATH invocation mechanism
validated for the published candidate. A PATH change takes effect only in newly started processes, so restart YASB
yourself if you enable the task. yasb-limitora **never manages the YASB
lifecycle**: starting, stopping, and restarting YASB stay manual, owned by
you.

## Your state is retained

Configuration, cache, and backups under `%LOCALAPPDATA%\yasb-limitora` are
separate from installed program files and are **preserved by default**
across install, reinstall, upgrade, and uninstall. State deletion happens
only when you explicitly answer the default-negative cleanup confirmation
during uninstall.

## Unsigned artifact

The 0.2.0 `setup.exe` is unsigned. Expect the Windows SmartScreen disclosure
described in [`RELEASE_NOTES.md`](RELEASE_NOTES.md), and verify the published
SHA-256 of your download before running the installer.
