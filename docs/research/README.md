# Research Decisions

This record contains the evidence that fixes the 0.2 product boundary. It is
not an open investigation into native YASB extensibility: that path is
explicitly rejected.

## Verified decisions

| Evidence | Decision |
|----------|----------|
| YASB CustomWidget v2.0.5 source | Use `CustomWidget` with JSON return data, `label`, `label_alt`, tooltip text, static CSS, periodic refresh, and manual/callback refresh. |
| YASB CustomWidget worker | `stop()` stops result publication but does not terminate the running `Popen`; process cleanup belongs to the CLI boundary and must be bounded. |
| Limitora public API 0.1.0 | Preserve `available`, `partial`, `unavailable`, `unauthorized`, `rate_limited`, `transient_error`, and `invalid_data` exactly. |
| Limitora domain model | Preserve variable quota windows, availability, source metadata, plan identifiers, reset timestamps, and Decimal `limit`/`used`/`remaining` quantities. |
| Limitora comparability | Window identity is `(kind, scope, period)`; compatibility additionally requires `plan_id` and `unit`, plus a sanitized non-null source match for planless commercial quota. |
| Existing YASB-side runtime | v1 is a fixed `codex`, then `opencode_go` envelope and must remain byte-for-byte stable. |
| Existing Codex IPC | Control payloads are bounded at 16 KiB and response payloads at 64 KiB; v2 must not silently enlarge those limits. |

## Product implications

- A stale snapshot is not unavailable. Freshness is an independent field.
- An undetected provider is not unavailable. It has no public provider state or
  freshness because no usable source was detected.
- A provider that was not called is not unavailable. It carries an explicit
  safe reason such as disabled, configuration failure, document abort, or
  deadline exhaustion.
- Missing numeric evidence is never zero. Nullable quantities remain `null`.
- Percentages are derived presentation data only; canonical windows retain all
  safe quota quantities and their context.
- A mutex serializes execution but does not coalesce requests or promise
  instantaneous process death when YASB closes.

## Verification still required

R9 will validate the seam against pinned YASB v2.0.5 in two separate layers:

1. Deterministic integration with the real CustomWidget and a fixture
   executable covering complete, partial, stale, window disappearance and
   reappearance, invalid JSON, and overlapping invocations.
2. A separate live-provider smoke for current Codex and OpenCode Go evidence.

Both layers must record the exact YASB version/commit, environment, commands,
stdout/stderr, exit code, and bounded eventual process termination. Compatibility
claims are limited to the pinned evidence; they are not indefinite support.

## Rejected research paths

- Native YASB widget implementation, upstream contribution, and maintainer
  approval.
- Official extension/plugin API research as a product dependency.
- Native popover, tabs, interactive progress, dynamic severity CSS, and a
  synthetic cross-provider minimum.
- Claude, Gemini, costs, tokens, history, predictions, usage, and reset credits
  for 0.2.

Provider-specific implementation research belongs in the Limitora repository.
This repository records only the public API evidence needed at the boundary.

## Sanitized evidence rules

- Never commit cookies, tokens, sessions, credentials, private payloads, or raw
  provider diagnostics.
- Redacted samples use `*.redacted.json` or `*.redacted.txt`.
- Source identifiers are allowlisted and normalized by the R2 contract; raw
  source references never reach output.
