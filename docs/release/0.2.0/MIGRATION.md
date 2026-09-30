# Migrating to yasb-limitora 0.2.0

0.2.0 is the planned first public release of yasb-limitora. As of this
document revision, no 0.2.0 installer or release has been published. This
migration material describes the intended transition from a development
checkout; it is not evidence that a published installer is available or has
passed release acceptance.

## Intended transition from checkout to setup.exe

When a 0.2.0 installer is published and release acceptance is complete:

1. Remove any editable development install: `py -m pip uninstall yasb-limitora`.
2. Run the per-user `yasb-limitora-0.2.0-setup.exe`. The intended installer
   requires no Python or elevation and installs program files under
   `%LOCALAPPDATA%\Programs\yasb-limitora`.
3. The editable-checkout route (`py -m pip install -e .`) remains
   **development-only**; it is not an end-user installation.

No installer is currently published; do not interpret these planned steps as
release availability or verification evidence.

## JSON contract: the #137 break

- The current selector-free JSON document is the sole supported output.
- The root `version` field no longer exists. Consumers that read it must
  stop; there is no replacement field, no compatibility selector, and no v1
  fallback.
- The removed version-selection surface is invalid and fails closed with
  `invocation_invalid` and exit code `2`.
- Migrate by consuming the current document exactly as documented in
  [`docs/windows-json.md`](../../windows-json.md).

## PATH and YASB invocation status

The installer design includes an optional User PATH task, **unchecked by
default**, for direct CLI convenience. This does not by itself establish that
YASB CustomWidget works without PATH. G2a selected M6 as a feasibility result,
but explicitly did not close installer guaranteeability or release acceptance;
G2b must confirm the behavior against the exact retained installed candidate
and remains pending. Therefore this guide makes no verified no-PATH integration
claim. The checkout example's bare command requires YASB to inherit a PATH that
contains its editable-install console script. A PATH change affects newly
started processes, so restart YASB yourself if you enable the task.
yasb-limitora **never manages the YASB lifecycle**: starting, stopping, and
restarting YASB stay manual, owned by you.

## Your state is retained

Configuration, cache, and backups under `%LOCALAPPDATA%\yasb-limitora` are
separate from installed program files and are **preserved by default**
across install, reinstall, upgrade, and uninstall. State deletion happens
only when you explicitly answer the default-negative cleanup confirmation
during uninstall.

## Unsigned artifact (planned)

The planned 0.2.0 `setup.exe` is unsigned. If it is published, expect the
Windows SmartScreen disclosure described in [`RELEASE_NOTES.md`](RELEASE_NOTES.md),
and verify the published SHA-256 of your download before running the installer.
No setup executable is currently published.
