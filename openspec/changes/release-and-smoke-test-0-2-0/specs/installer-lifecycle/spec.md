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
