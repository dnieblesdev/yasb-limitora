# Installer Lifecycle Specification

## Purpose

Define safe no-Python per-user installation and lifecycle behavior while keeping packaged program files separate from mutable user state.

## Requirements

### Requirement: A clean per-user installation runs without Python

The supported `setup.exe` MUST install the product for a normal Windows 10/11 user without requiring Python or an editable checkout. Installed program files MUST remain separate from mutable configuration, cache, and state under `%LOCALAPPDATA%\\yasb-limitora`.

#### Scenario: Clean machine has no Python

- GIVEN a clean supported Windows machine with no Python installation
- WHEN a normal user runs the supported `setup.exe`
- THEN installation succeeds without requiring Python or an editable checkout
- AND the installed product can start its normal CLI

#### Scenario: Program and mutable state are separate

- GIVEN the product has been installed and has created configuration, cache, or state
- WHEN the installed layout is inspected
- THEN program files and `%LOCALAPPDATA%\\yasb-limitora` mutable data are distinct
- AND lifecycle operations can address program files without treating mutable data as program files

### Requirement: Install, reinstall, and upgrade preserve a usable installation

The installer MUST support install, reinstall, and upgrade for the supported per-user product. A successful lifecycle operation MUST leave the installed program usable and MUST NOT silently delete or corrupt existing mutable configuration, cache, or state.

#### Scenario: Reinstall retains user data

- GIVEN an existing installation with valid mutable configuration, cache, and state
- WHEN the user performs a reinstall
- THEN the product remains usable
- AND the existing mutable data is retained unless the user explicitly selected cleanup

#### Scenario: Upgrade retains user data

- GIVEN an existing earlier installation and mutable user data
- WHEN the user performs a supported upgrade
- THEN the new program version is installed successfully
- AND the mutable data remains available without silent deletion or corruption

### Requirement: Failed installation or upgrade rolls back safely

A failed or cancelled install or upgrade MUST restore the prior usable program installation according to the approved transaction behavior and MUST NOT remove mutable user data by default.

#### Scenario: Upgrade failure restores the prior product

- GIVEN a usable installed product and an upgrade that cannot complete
- WHEN the failure is reported
- THEN the prior program installation remains usable or is restored
- AND existing configuration, cache, and state remain intact

### Requirement: Uninstall retains state unless cleanup is explicitly selected

Uninstall MUST preserve `%LOCALAPPDATA%\\yasb-limitora` configuration, cache, and state by default. Any cleanup option MUST be visibly opt-in and unchecked by default, and MUST delete those data files only when the user explicitly selects it.

#### Scenario: Default uninstall preserves mutable data

- GIVEN an installed product with configuration, cache, and state
- WHEN the user uninstalls without selecting cleanup
- THEN installed program files are removed as defined for uninstall
- AND the mutable configuration, cache, and state remain

#### Scenario: Explicit cleanup removes mutable data

- GIVEN an installed product with mutable data
- WHEN the user explicitly selects the cleanup option before uninstall
- THEN the selected cleanup is performed
- AND the cleanup option was not selected implicitly or by default

### Requirement: User PATH changes are consented and ownership-bounded

The optional `addtopath` install choice MUST remain unchecked by default. If the exact current
installation directory is already a PATH element, install assistance MUST complete successfully
without adding a duplicate or adopting PATH ownership. Replacing a related old route MUST require
a separate, unchecked `correctownedpath` choice as well as `addtopath`; `addtopath` alone MUST NOT
authorize correction. The effective correction consent MUST be false for silent installs, even if
task names are supplied. Correction also requires a valid product ownership record proving the exact
live PATH value/type and identifying the related route as its final element; absent, malformed, or
stale proof MUST fail closed without mutation.

Uninstall MUST present a `removePATH` checkbox checked by default (silent uninstall keeps this
default without displaying UI). Unchecking it MUST preserve PATH. Checking it MUST remove only a
still-owned recorded route; an absent route is a successful no-op, and the checkbox MUST NOT
authorize deletion of a foreign or unowned element. Separately consented state cleanup MUST require
the exact recorded live PATH value/type and unchanged ownership record before deleting state. Any
PATH snapshot mismatch, including an already-absent recorded route, MUST preserve both state and
bookkeeping; PATH removal remains an independent no-op when the route is absent.

#### Scenario: Existing correct PATH entry is accepted without adoption

- GIVEN the exact current installation directory is already in the user's PATH
- WHEN the user opts into `addtopath`
- THEN setup assistance succeeds without changing PATH
- AND it does not create or replace the ownership record for that pre-existing element

#### Scenario: A recorded incorrect route is disclosed and corrected only with separate interactive consent

- GIVEN the product has a valid ownership record matching the exact live PATH value/type and final
  element for a previous installation directory
- AND the current installation directory is not already in PATH
- WHEN the interactive user selects both `addtopath` and `correctownedpath` and affirms the route
  confirmation
- THEN before mutation the installer displays the exact recorded old route and current destination
  in a default-No confirmation
- AND the installer requires a read-only live User PATH registry type query to return `REG_SZ` or
  `REG_EXPAND_SZ` matching the recorded type before disclosing the route
- AND only an affirmative answer plus the helper's live full-PATH/type ownership revalidation may
  replace that proven-owned final element
- AND the updated ownership record describes the resulting PATH

#### Scenario: Unsafe route preview does not disclose or grant correction consent

- GIVEN a correction preview is requested for a recorded old route and current destination
- WHEN the live PATH type query fails, returns an unsupported type, or differs from the recorded
  type
- OR either raw display route contains a Unicode `Bidi_Control` character
- THEN no correction confirmation is shown and correction consent remains false
- AND the installer does not sanitize or rewrite either route for display
- AND the PATH and ownership record are not changed by the refused correction request

#### Scenario: Declining correction does not fall back to appending a new route

- GIVEN a valid ownership record matches the exact live PATH value/type and its old route is final
- AND the current installation directory is not already in PATH
- WHEN the interactive user selects `addtopath` but declines correction or leaves `correctownedpath`
  unchecked
- THEN the `path-add` operation returns the bounded refusal `path-correction-consent-required`
- AND the full PATH value and ownership record remain exactly unchanged
- AND the new installation directory is not appended

#### Scenario: Silent addtopath cannot replace a recorded route

- GIVEN a valid ownership record matches the exact live PATH value/type and its old route is final
- AND the current installation directory is not already in PATH
- WHEN setup runs silent with `addtopath` selected, even if `correctownedpath` is also supplied
- THEN correction consent remains false
- AND the `path-add` operation returns the bounded refusal `path-correction-consent-required`
- AND the full PATH value and ownership record remain exactly unchanged without appending the new
  installation directory

#### Scenario: Uninstall preserves PATH when unchecked

- GIVEN the product has a still-owned PATH entry
- WHEN the user unchecks `removePATH` during uninstall
- THEN the PATH entry remains unchanged
- AND if state cleanup is separately confirmed, the state-cleanup operation runs without removing
  PATH and clears the record only after successful deletion

#### Scenario: State cleanup refuses when the live PATH snapshot differs

- GIVEN a valid product ownership record exists but the live PATH value or registry type differs
  from the recorded snapshot, including when its recorded route is already absent
- WHEN the user explicitly selects state cleanup, with `removePATH` either checked or unchecked
- THEN state and the ownership record remain unchanged and state cleanup is refused
- AND PATH is not modified by state cleanup
- BUT a separate `removePATH` request for the already-absent route may still succeed as a no-op

#### Scenario: Uninstall never removes an unowned PATH entry

- GIVEN a matching PATH element exists without a valid product ownership record
- WHEN `removePATH` is checked during uninstall
- THEN the helper succeeds without changing that element or adopting ownership

#### Scenario: Missing PATH route is a successful uninstall no-op

- GIVEN the recorded route is already absent from PATH, or no valid ownership record exists
- WHEN `removePATH` is checked during uninstall
- THEN PATH removal succeeds silently without modifying unrelated PATH elements
