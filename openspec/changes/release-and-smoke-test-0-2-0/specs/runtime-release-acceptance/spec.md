# Runtime and Release Acceptance Specification

## Purpose

Define the runtime invariants and evidence required to accept the packaged Windows product and close the 0.2.0 smoke-test release.

## Requirements

### Requirement: The packaged runtime preserves the current Windows execution contract

The packaged product MUST preserve the Windows-only runtime boundary and the current selector-free JSON, stream, exit-code, sanitized-output, and fail-closed behavior. Packaging MUST NOT introduce a second output contract or expose secrets through output, logs, or diagnostics.

#### Scenario: Clean no-Python run uses the current contract

- GIVEN the packaged product runs on a supported Windows machine without Python
- WHEN the normal CLI completes successfully or with a handled unavailable/error outcome
- THEN it produces the current selector-free JSON contract and established streams and exit code
- AND output is sanitized and contains no top-level `version` field or secret

#### Scenario: Unsupported platform remains gated

- GIVEN the packaged runtime is started outside its supported Windows boundary
- WHEN execution begins
- THEN the established early platform gate applies
- AND packaging does not bypass the Windows-only boundary

### Requirement: Frozen process and execution safeguards remain bounded

The packaged runtime MUST preserve frozen helper relaunch, multiprocessing bootstrap, Windows Job containment, shared deadlines, stream handling, redaction, cleanup, and no-descendant/no-orphan behavior. A deadline, failure, or normal completion MUST NOT leave unmanaged helper work or descendants beyond the established bounds.

#### Scenario: Frozen helper completes within the run boundary

- GIVEN the packaged CLI requires its internal helper and multiprocessing support
- WHEN the helper is relaunched and the run reaches success, failure, or its deadline
- THEN multiprocessing bootstrap and helper execution work in the frozen runtime
- AND deadlines, streams, redaction, Job containment, and cleanup remain effective
- AND no orphaned descendant remains after completion or timeout

### Requirement: The smoke matrix covers release-critical environments and behavior

Release acceptance MUST execute and record a smoke matrix covering clean Windows with no Python, frozen helper behavior, multiprocessing bootstrap, Job containment, deadlines, sanitized streams, no-orphan cleanup, optional PATH enabled and disabled, installer install/reinstall/upgrade/failure rollback/uninstall, YASB present/absent/undetected/running boundaries, consented environment assistance, provider wizard safety, artifact integrity, and applicable native Windows proof.

#### Scenario: Required smoke evidence is reviewable

- GIVEN the candidate is evaluated for 0.2.0 release readiness
- WHEN the smoke matrix is run
- THEN each applicable matrix case has a recorded pass or an explicitly reported unrun external gate
- AND no unrun case is represented as a pass

### Requirement: Live-provider evidence follows the release-change policy

Acceptance MUST include at least one representative live flow for a supported provider using secret-safe evidence. Named-provider live proof MUST be included when that release changes the provider; otherwise existing supported-provider coverage plus a representative live flow is sufficient.

#### Scenario: Provider scope determines live proof

- GIVEN the release changes a particular provider
- WHEN release acceptance is reviewed
- THEN live evidence for that named provider is present
- AND the evidence is redacted and contains no credentials

#### Scenario: Release does not change provider behavior

- GIVEN the release does not change a provider
- WHEN release acceptance is reviewed
- THEN a representative live supported-provider flow and existing supported-provider coverage are recorded
- AND no provider-specific implementation is duplicated by the release packaging

### Requirement: Post-release smoke is required before closeout

After publication, release acceptance MUST record a clean-machine smoke of the published bytes. The post-release smoke MUST verify installation and normal packaged execution under the same no-Python and user-state safety boundaries.

#### Scenario: Published artifact passes post-release smoke

- GIVEN the exact validated artifact has been published
- WHEN a clean supported Windows machine runs the post-release smoke
- THEN the published artifact installs and runs without Python
- AND the result is recorded before R11 closeout
