# Make the current JSON contract the sole supported output

## Intent

Implement GitHub issue #137 by making the current JSON contract the default and only supported output of `yasb-limitora`. The command must no longer expose or route through the legacy v1 contract. This is a deliberate pre-stable wire and schema break: the repository will document the change without asserting that private consumers do not exist.

The result keeps the existing current-contract behavior and operational safeguards intact while removing obsolete version-selection and v1-only surface area.

## Scope

### In scope

- Make selector-free CLI calls use the current JSON contract through the existing configuration precedence:
  1. explicit configuration,
  2. `YASB_LIMITORA_CONFIG`,
  3. the per-user default.
- Remove the public top-level `version` field from the supported output contract.
- Remove `--output-version`, `_output_version` branching, v1 routing, and obsolete v1 coordinator/serializer paths.
- Treat `projection_v2.py` and other active versioned implementation names as the current implementation boundary, then normalize active runtime modules, symbols, tests, and spec names so the sole supported contract is not presented as one version among several.
- Remove v1-only serializers, fixtures, tests, examples, and documentation. Preserve historical v1 references in `docs/roadmap.md` and add a superseding note explaining that the current contract is now the sole supported output.
- Remove `version` coupling from the producer, schema, canonical ordering, cache validation/serialization, fixtures, examples, and tests.
- Increment `CACHE_SCHEMA`; old cache entries must be treated as stale and refreshed cold rather than migrated.
- Preserve persisted and external identities exactly, including:
  - `Global\\yasb-limitora-v2-guard-*`
  - `quota-v2-cache.json`
  - existing public provider source IDs.
- Preserve the current execution and safety behavior: `execution_state`, provider outcome and `public_state` mappings, streams, exit codes, deadlines, the early non-Windows gate, redaction, the shared deadline, guard/job/process/cleanup behavior, cache single-flight and public-only bounds, and YASB provider paths.

### Out of scope

- Unrelated wire or schema redesign.
- Guard identity renaming.
- Release publication or release-process changes.
- Provider ownership, credentials, transport, or YASB-native changes.
- Removing historical roadmap context.
- Compatibility aliases or a second output mode for private consumers.

## Affected areas

| Area | Required change | Preservation requirement |
| --- | --- | --- |
| CLI/configuration | Remove output-version selection and route all supported calls to the current contract using the established configuration precedence. | Existing invocation, configuration, stream, and exit behavior remains valid apart from the intentional contract break. |
| Projection and schema | Retire the legacy projection/coordinator path; normalize the active producer and remove the root `version` field and its canonical-order/schema dependencies. | Current JSON values, provider mappings, redaction, and failure-safe behavior remain unchanged. |
| Cache and guard | Update cache validation/serialization for the contract without the public version field; increment `CACHE_SCHEMA` and cold-refresh stale data. | Keep cache filename, guard names, public source IDs, single-flight behavior, bounds, and cleanup semantics unchanged. |
| Tests, fixtures, examples, and specs | Delete v1-only coverage and update active names and expectations to the sole contract. Add coverage for removed selector/version behavior and cache invalidation. | Retain coverage for platform gating, streams, exit codes, deadlines, providers, sanitization, and lifecycle invariants. |
| Documentation | Describe the pre-stable wire/schema break and current-only output. Add the superseding roadmap note while retaining historical v1 references. | Do not imply that private consumers are absent. |

## Compatibility impact

This change intentionally breaks the pre-existing public JSON shape and CLI version-selection surface before the contract is stable. Consumers that read the top-level `version` field or request v1 must update to the current contract and must not rely on v1 fallback behavior. The documentation should state this plainly, while making no claim about the existence or absence of private consumers.

The cache schema increment is an explicit invalidation boundary. Existing cache data is not migrated; it is ignored as stale and refreshed. Persisted and externally observed identities listed above are not part of the wire-contract rename and must remain exact.

## Risks and mitigations

- **Hidden v1 coupling:** dynamic imports, monkeypatch targets, and path-based tests may continue to reference old names. Search and update active references, then run focused and full test suites.
- **Accidental contract drift:** removing `version` may affect canonical ordering, schemas, cache serialization, fixtures, or examples beyond the intended field removal. Keep the current contract as the source of truth and assert exact output in tests.
- **Lifecycle regression during routing cleanup:** coordinator removal can disturb guard, process, job, deadline, or cleanup behavior. Preserve and exercise the existing lifecycle and Windows-boundary tests.
- **Cache behavior regression:** a renamed internal module or changed validation path could bypass single-flight or public-only constraints. Test stale-cache refresh and concurrent/cache-bound behavior explicitly.
- **Consumer surprise:** the wire break may affect private integrations. Document the deliberate pre-stable break and migration expectation rather than retaining an undocumented compatibility path.

## Rollback

Rollback is a source/release revert to the last supported implementation, including restoration of the prior routing and contract behavior if that is operationally required. No cache migration is introduced. If a rollback must reuse cache data under the old implementation, restore the previous `CACHE_SCHEMA` handling with the reverted code; otherwise allow the new cache entries to be discarded and refreshed after rollback. Do not create a permanent dual-output mode as a rollback mechanism.

## Success criteria

- [ ] Selector-free invocations consistently produce the current JSON contract through explicit configuration, `YASB_LIMITORA_CONFIG`, or the per-user default, with no v1 fallback.
- [ ] `--output-version`, `_output_version`, v1 routing, v1 serializers, and v1-only fixtures/tests/docs are absent from active supported paths.
- [ ] The supported JSON document has no public top-level `version`, and producer, schema, canonical ordering, cache, fixture, example, and test expectations agree.
- [ ] Active versioned implementation, symbol, test, and spec names are normalized without changing persisted/external identities.
- [ ] `CACHE_SCHEMA` is incremented and stale caches receive a cold refresh; `quota-v2-cache.json`, guard identities, and public source IDs remain exact.
- [ ] Existing execution-state, provider mapping, stream/exit, deadline, redaction, platform-gate, lifecycle, cleanup, and cache-bound invariants remain covered and pass.
- [ ] Documentation records the deliberate pre-stable wire/schema break, preserves historical v1 roadmap references with a superseding note, and does not claim private consumers do not exist.
- [ ] Focused pytest coverage and the full configured pytest suite pass; native Windows proof is run when available or reported as an external verification when unavailable.
