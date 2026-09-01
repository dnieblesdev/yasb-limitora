# JSON Output Specification

## Purpose

Define the pre-stable JSON and command-line boundary for `yasb-limitora` after the current contract becomes the only supported output. The change intentionally removes the legacy v1 contract and public version selection while preserving current runtime behavior and externally meaningful identities.

## Requirements

### Requirement: The current JSON contract is the sole supported output

`yasb-limitora` MUST produce the current JSON contract for every supported invocation. The document MUST retain the current contract's fields, values, provider mappings, redaction behavior, and failure-safe semantics, except that it MUST NOT contain a public top-level `version` field. The command MUST NOT emit a legacy v1 document or expose the current contract as one selectable version among several.

#### Scenario: Successful selector-free invocation

- GIVEN a valid supported configuration
- WHEN `yasb-limitora` is invoked without an output-version selector
- THEN it produces the current JSON contract
- AND the JSON document has no top-level `version` field

#### Scenario: Configuration precedence does not change the contract

- GIVEN an explicit configuration, an equivalent `YASB_LIMITORA_CONFIG` configuration, or the per-user default configuration
- WHEN the command is invoked without an output-version selector
- THEN the established configuration precedence selects the run
- AND each supported configuration path produces the same current contract shape

#### Scenario: Unavailable, not-run, and safe-error outcomes

- GIVEN a provider is unavailable, not run, or produces a handled error
- WHEN the command emits its result
- THEN the existing `execution_state`, provider outcome, and `public_state` mappings remain applicable
- AND the result remains sanitized and contains no top-level `version`

#### Scenario: Invalid provider data is handled safely

- GIVEN provider data is malformed or invalid
- WHEN the command processes the data
- THEN it follows the existing safe, fail-closed output behavior
- AND it MUST NOT fall back to v1 or expose unsanitized provider data

### Requirement: Output-version selection is removed from the supported CLI surface

The CLI MUST NOT expose `--output-version`, `_output_version`, or any equivalent selector for choosing a JSON contract. Supported invocations MUST NOT route through a v1 coordinator, serializer, or fallback path. An invocation that requests the removed selector MUST NOT receive a v1 response or a compatibility alias.

#### Scenario: Removed selector cannot select v1

- GIVEN a caller supplies the former output-version selector
- WHEN the CLI parses the invocation
- THEN the selector is not accepted as a supported way to request output
- AND the command does not produce a v1 document

#### Scenario: No implicit legacy fallback

- GIVEN a supported invocation encounters a configuration, provider, or serialization problem
- WHEN the command reports the result
- THEN it uses the current contract's established error behavior
- AND it does not retry or fall back to the legacy v1 contract

### Requirement: The compatibility boundary is explicit and one-way

The supported boundary MUST document this as a deliberate pre-stable wire and schema break. Consumers of the former top-level `version` field or v1 selector MUST update to the current contract. The project MUST NOT promise a dual-output mode, compatibility alias, or v1 fallback, and documentation MUST NOT claim that private consumers do not exist.

#### Scenario: Legacy consumer migration boundary

- GIVEN a consumer expects the former top-level `version` field or requests v1
- WHEN it is evaluated against the changed command
- THEN it is identified as outside the supported contract
- AND the documented migration target is the current JSON contract without that field

### Requirement: Cache entries cross an explicit invalidation boundary

The cache schema identifier MUST be incremented for this contract change. Cache entries written under the previous schema MUST be treated as stale and refreshed cold; they MUST NOT be migrated or accepted as current solely because their payload otherwise appears valid. Current cache validation and serialization MUST NOT depend on a public top-level `version` field.

#### Scenario: Previous-schema cache is refreshed cold

- GIVEN a cache entry was written with the previous `CACHE_SCHEMA`
- WHEN the command reads the cache
- THEN it treats the entry as stale
- AND it obtains fresh data rather than migrating or serving the old entry as current

#### Scenario: Current cache has no public version coupling

- GIVEN data is written to the current cache
- WHEN the cache data is validated or serialized
- THEN validity is determined by the current cache contract and schema boundary
- AND the public JSON payload does not require a top-level `version` field

### Requirement: Persisted and external identities remain unchanged

The change MUST preserve these identities exactly: the guard prefix `Global\yasb-limitora-v2-guard-*`, the cache filename `quota-v2-cache.json`, and all existing public provider source IDs. Normalizing active implementation names MUST NOT rename or alias any of these identities.

#### Scenario: Existing operational identities remain addressable

- GIVEN a deployment or test observes a guard name, cache filename, or provider source ID
- WHEN the single-contract change is applied
- THEN each observed identity remains byte-for-byte unchanged
- AND the command continues to use the same identity for the same operational purpose

### Requirement: Current runtime and safety invariants are preserved

The command MUST preserve the current execution and safety behavior, including `execution_state` semantics, provider outcome and `public_state` mappings, output streams, exit codes, shared deadlines, early non-Windows gating, redaction, guard/job/process/cleanup behavior, cache single-flight and public-only bounds, and YASB provider paths. Removing version selection MUST NOT alter these invariants.

#### Scenario: Platform boundary is enforced before normal execution

- GIVEN the command runs on a non-Windows platform
- WHEN execution begins
- THEN the existing early non-Windows gate applies
- AND no version-specific output path bypasses that gate

#### Scenario: Streams and exit behavior remain current

- GIVEN a successful run or a handled unavailable/error outcome
- WHEN the command completes
- THEN its established stdout/stderr behavior and exit code remain unchanged apart from the intentional JSON contract break
- AND the emitted JSON, when applicable, is the current contract without a top-level `version`

#### Scenario: Deadline and lifecycle safeguards remain bounded

- GIVEN providers, guards, jobs, or processes are active during a run
- WHEN the shared deadline is reached or execution completes
- THEN existing deadline, cleanup, guard, job, and process invariants apply
- AND removing the legacy coordinator does not leave work, guards, or processes running beyond the established bounds

#### Scenario: Cache and provider safeguards remain bounded

- GIVEN concurrent callers use the cache or a YASB provider path
- WHEN data is read or refreshed
- THEN cache single-flight and public-only bounds remain enforced
- AND provider selection, authentication, transport, and provider-specific interpretation remain delegated to the existing Limitora boundary

### Requirement: Active repository examples and names describe one contract

Active implementation, symbol, test, fixture, example, and specification names MUST identify the supported contract without presenting it as v2 alongside a supported v1. V1-only serializers, fixtures, tests, examples, and documentation MUST be removed from active supported paths. Historical v1 references in `docs/roadmap.md` MUST remain and MUST include a superseding note that the current contract is now the sole supported output.

#### Scenario: Examples and fixtures match the supported document

- GIVEN a maintained example or fixture is used to demonstrate or validate output
- WHEN it is compared with the supported contract
- THEN it represents the current contract only
- AND it contains no public top-level `version` field or v1-only shape

#### Scenario: Historical roadmap context is retained

- GIVEN a reader consults `docs/roadmap.md`
- WHEN the historical v1 reference is read
- THEN the historical context remains available
- AND a superseding note makes clear that the current contract is now the sole supported output

### Requirement: Documentation and verification make acceptance reviewable

Documentation MUST describe the intentional pre-stable wire/schema break, the current-only output, the removed selector, the cache invalidation boundary, and the identities that remain unchanged. Acceptance verification MUST demonstrate the contract, CLI removal, stale-cache refresh, preserved runtime invariants, and documentation/example updates through focused tests and the full configured pytest suite. Native Windows proof MUST be run when available; otherwise its absence MUST be reported as external verification still required.

#### Scenario: Focused and full verification provide evidence

- GIVEN the change is ready for acceptance
- WHEN focused tests and the full configured pytest suite are run
- THEN they verify the current contract without `version`, absence of v1 selection/fallback, cold refresh of previous-schema caches, and preserved runtime/lifecycle invariants
- AND the verification record identifies the results

#### Scenario: Native Windows verification is available

- GIVEN a native Windows environment is available
- WHEN the Windows proof is run
- THEN the Windows-only gate and lifecycle/safety behavior are verified there

#### Scenario: Native Windows verification is unavailable

- GIVEN a native Windows environment is unavailable
- WHEN verification is reported
- THEN native Windows proof is explicitly reported as unrun external verification rather than implied to have passed
