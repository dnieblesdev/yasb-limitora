# Research Decisions

This record contains the evidence that fixes the 0.2 product boundary. It is
not an open investigation into native YASB extensibility: that path is
explicitly rejected.

## Verified decisions

| Evidence | Decision |
|----------|----------|
| YASB CustomWidget v2.0.5 source | Use `CustomWidget` with JSON return data, `label`, `label_alt`, tooltip text, static CSS, periodic refresh, and manual/callback refresh. |
| YASB CustomWidget worker | `stop()` stops result publication but does not terminate the running `Popen`; process cleanup belongs to the CLI boundary and must be bounded. |
| Limitora public API 0.2.0 Bearer contract | Preserve `available`, `partial`, `unavailable`, `unauthorized`, `rate_limited`, `transient_error`, and `invalid_data` exactly. |
| Limitora domain model | Preserve variable quota windows, availability, source metadata, plan identifiers, reset timestamps, and Decimal `limit`/`used`/`remaining` quantities. |
| Limitora comparability | Window identity is `(kind, scope, period)`; compatibility additionally requires `plan_id` and `unit`, plus a sanitized non-null source match for planless commercial quota. |
| OpenCode 0.2 window contract | `available` and `partial` snapshots use one fixed commercial slot for each `five_hour`, `monthly`, and `weekly` period; `rate_limited` carries technical windows only and no per-window commercial provenance. |
| Limitora #55 / yasb-limitora #133 | Limitora's v0.3.0 per-window rate-limit signal is upstream context only; this consumer remains on the 0.2 contract and does not consume it until #133. |
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

## Verification status and remaining gates

R9 artifact validation is complete for the repository evidence and documented
data boundary. The abandoned external YASB harness is historical context, not a
current requirement, and must not be recreated.

R10 is complete at two separate boundaries:

1. Automated native Windows proof covers the `yasb-limitora` CLI and JSON v2
   contract.
2. The maintainer accepted the real YASB CustomWidget manually on YASB v2.0.6.

OpenCode supported-API validation remains an R11 gate under migration #130. It
requires a separate maintainer manual acceptance in a real YASB installation
after that migration; it is not an R10 or automated-YASB-rendering claim.

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
