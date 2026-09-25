# Configuration Assistance Specification

## Purpose

Define the opt-in provider configuration wizard and preserve ownership, consent, validation, atomicity, and safe state semantics.

## Requirements

### Requirement: Provider configuration changes are opt-in and atomic

The provider wizard MUST run only after explicit user opt-in. When it creates or updates `yasb-limitora` `config.json`, it MUST use an atomic write with a recoverable backup or equivalent pre-change recovery point. If the write or final validation fails for a runtime-valid configuration, the prior configuration MUST be restored or remain authoritative.

#### Scenario: Opt-in creates a configuration

- GIVEN no `yasb-limitora` `config.json` exists
- WHEN the user explicitly starts and completes the provider wizard
- THEN the wizard creates the configuration atomically
- AND a recoverable backup or equivalent pre-change recovery point is available

#### Scenario: Failed update rolls back

- GIVEN an existing runtime-valid configuration and an opt-in wizard update
- WHEN the write or final validation fails
- THEN the prior configuration is restored or remains authoritative
- AND a partial or malformed replacement is not left as the active configuration

### Requirement: Existing configurations are validated before wizard updates

Before any wizard update, the wizard MUST validate the complete existing `config.json` against the current runtime contract. If the document is invalid for any reason, including unknown fields, the wizard MUST abandon only the optional configuration operation, preserve the original file byte-for-byte, enumerate the detected validation errors using bounded non-secret diagnostics, and MUST NOT repair, normalize, drop, merge, reserialize, or loosen validation for that document.

#### Scenario: Invalid configuration is not mutated

- GIVEN an existing `config.json` fails the current runtime contract, including because it contains an unknown field
- AND the user explicitly starts a provider wizard update
- WHEN the wizard validates the existing document
- THEN the optional configuration operation is abandoned before any write
- AND the original file remains byte-for-byte identical
- AND the selected provider fields are not applied
- AND the detected validation errors are enumerated with bounded, non-secret diagnostics
- AND the invalid document is not repaired, normalized, partially rewritten, or reserialized

#### Scenario: Invalid configuration does not fail installation or upgrade

- GIVEN an install or upgrade includes an explicitly opted-in provider wizard update
- AND the existing `config.json` fails the current runtime contract for any reason
- WHEN the wizard abandons the optional configuration operation
- THEN installation or upgrade continues successfully
- AND the program-file installation transaction does not fail because of that optional configuration outcome
- UNLESS a separate program-file failure occurs
- AND the original configuration remains byte-for-byte identical

### Requirement: Wizard merges runtime-valid configurations safely

For an existing configuration that passes the current runtime contract, the wizard MUST safely merge only explicitly selected changes to fields it owns. It MUST preserve all other contract-valid fields it does not own, back up the prior document, write atomically, validate the final document against the current runtime contract, and roll back on failure.

#### Scenario: Runtime-valid configuration receives a safe merge

- GIVEN an existing configuration passes the current runtime contract
- AND it contains contract-valid fields not owned by the wizard
- WHEN the user explicitly updates a provider through the wizard
- THEN only the explicitly selected owned fields are changed
- AND all other contract-valid fields remain unchanged
- AND a recoverable backup is made before the write
- AND the resulting document is written atomically and passes final validation

### Requirement: Provider enabled state requires explicit selection

A provider MUST become enabled or disabled only as a result of an explicit user selection in the approved configuration flow. Missing secrets or external prerequisites MUST produce a warning and MUST NOT automatically change enabled state.

#### Scenario: No explicit selection leaves enabled state unchanged

- GIVEN the provider has no explicit enabled-state selection in the current configuration flow
- AND discovery has any outcome
- AND the required secret and external prerequisite may each be present or absent
- WHEN the wizard or installer evaluates provider readiness
- THEN discovery, secret presence or absence, and prerequisite presence or absence do not change the provider enabled state
- AND when a required secret or external prerequisite is missing, the user receives a warning about that missing requirement

#### Scenario: Explicit selection commits despite a missing requirement

- GIVEN the user explicitly selects a provider state in the wizard
- AND a required secret or external prerequisite is missing
- WHEN the configuration is committed successfully
- THEN the provider enabled state reflects that explicit selection
- AND the wizard warns that the provider may not work until the missing requirement is satisfied

#### Scenario: Installer tri-state controls default to unchanged

- GIVEN the user checks the `configassist` consent gate in the installer
- AND the provider configuration page appears with tri-state controls (unchanged, enabled, disabled) for each provider
- WHEN the user leaves both provider controls at the default unchanged
- THEN no `config-apply` operation is emitted
- AND the existing discover fallback is used instead

#### Scenario: Installer Codex enable requires absolute runner path

- GIVEN the user selects enabled for Codex in the installer provider page
- WHEN the runner path is empty or not absolute
- THEN the installer rejects the page advance
- AND no `config-apply` operation is emitted for that selection

### Requirement: Provider ownership and credential boundaries remain intact

The provider wizard MUST NOT implement or duplicate provider authentication, transport, selection logic, or interpretation outside the established Limitora ownership boundary. Credentials and secrets MUST remain in the existing YASB startup-loaded environment or effective environment and MUST NOT be copied into `config.json`, installer arguments, logs, output, fixtures, reports, or release artifacts.

#### Scenario: Configuration assistance handles no secret material

- GIVEN a user configures a provider with credentials available through the existing environment
- WHEN the wizard creates or merges `config.json`
- THEN the configuration contains no copied secret
- AND installer arguments, logs, output, and release evidence contain no secret
- AND provider authentication and transport remain owned by Limitora
