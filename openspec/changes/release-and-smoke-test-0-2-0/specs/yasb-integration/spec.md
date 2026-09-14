# YASB Integration Specification

## Purpose

Define the no-PATH YASB integration boundary, discovery outcomes, manual-close behavior, optional PATH convenience, and narrow consented environment assistance.

## Requirements

### Requirement: YASB integration works without PATH changes

YASB integration MUST work when the installer leaves PATH unchanged. The optional User PATH task MUST be visibly optional and unchecked by default, and enabling it MUST affect direct CLI convenience only; it MUST NOT be an integration prerequisite.

#### Scenario: YASB works with PATH unchanged

- GIVEN a real release-target YASB installation and an installed `yasb-limitora`
- WHEN the User PATH task is disabled and PATH is unchanged
- THEN the YASB integration works through its supported invocation path
- AND the direct CLI remains usable without requiring PATH

#### Scenario: User PATH task is opt-in

- GIVEN a user views installer tasks
- WHEN no PATH choice has been made
- THEN the User PATH task is unchecked
- AND enabling it is not required for YASB integration

### Requirement: The release-target spaced-path proof is release-blocking

The release MUST prove the no-PATH integration against a real release-target YASB installation whose relevant command path contains spaces. The proof MUST exercise the target YASB command parsing behavior and MUST NOT count a shell-enabled parsing bypass as a passing result.

#### Scenario: Spaced executable path succeeds

- GIVEN the release-target YASB executable or command path contains spaces
- WHEN the installed product invokes the integration with PATH unchanged
- THEN the real YASB integration succeeds with the expected observable result
- AND the result does not depend on enabling a shell parsing bypass

#### Scenario: Spaced-path failure blocks release

- GIVEN the release-blocking spaced-path proof fails or is not run
- WHEN release readiness is evaluated
- THEN the release is not approved for publication
- AND the failure or missing external evidence is recorded

### Requirement: YASB discovery does not make installation dependent on YASB

The installer MUST distinguish successful YASB detection, absent YASB, and undetected YASB configuration as user-facing outcomes where possible. An absent or undetected YASB installation MUST NOT prevent successful installation; YASB-specific integration MUST be skipped and the user MUST be informed.

#### Scenario: YASB is absent

- GIVEN YASB is not installed
- WHEN the user installs the product
- THEN installation succeeds
- AND YASB-specific integration is skipped
- AND the user is informed that YASB was not found

#### Scenario: YASB configuration cannot be detected

- GIVEN YASB may be present but its configuration cannot be detected
- WHEN installation completes
- THEN installation succeeds
- AND YASB-specific integration is skipped or deferred
- AND the user is informed that detection was inconclusive

### Requirement: The product never owns YASB lifecycle

The product MUST NOT stop, restart, install, uninstall, or otherwise manage the YASB process lifecycle. If YASB is running during install, upgrade, or uninstall, the user MUST be asked to close it manually before the operation continues or is cancelled.

#### Scenario: YASB is running during a lifecycle operation

- GIVEN YASB is running during install, upgrade, or uninstall
- WHEN the installer detects that the operation may conflict with YASB
- THEN it asks the user to close YASB manually
- AND it does not stop, restart, or otherwise control YASB

#### Scenario: User does not close YASB

- GIVEN the user is asked to close a running YASB
- WHEN the user does not close it or cancels the prompt
- THEN the operation follows its reported cancellation or safe failure outcome
- AND the product does not forcibly manage YASB to continue

### Requirement: Environment assistance is narrow, consented, and safe

The product MAY manage only the approved `yasb-limitora` block in YASB `.env`, and only after explicit user consent. Any such block MUST be commented and idempotent. The product MUST NOT write secrets or credentials and MUST NOT edit YASB YAML or CSS.

#### Scenario: Consent creates the managed block

- GIVEN the user explicitly consents to the approved `.env` assistance
- WHEN the block is absent
- THEN the product adds only the commented `yasb-limitora` block
- AND it does not write secrets or edit YASB YAML or CSS

#### Scenario: Repeated consent is idempotent

- GIVEN the approved commented block already exists
- WHEN the user repeats the consented operation
- THEN the block is not duplicated
- AND unrelated `.env` content remains unchanged

#### Scenario: No consent prevents the mutation

- GIVEN the user has not explicitly consented to `.env` assistance
- WHEN installation or integration setup runs
- THEN the product does not modify the `.env` file
- AND it does not substitute an edit to YAML, CSS, credentials, or secrets
