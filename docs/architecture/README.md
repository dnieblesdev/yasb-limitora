# Product Boundary

The official 0.2 architecture is deliberately narrow:

```text
YASB CustomWidget -> yasb-limitora CLI / JSON v2 -> Limitora public API
```

`yasb-limitora` does not become a native YASB widget, a YASB upstream extension,
or a provider client. The CLI is the process boundary between CustomWidget and
Limitora. Provider internals and credentials do not cross it.

## Runtime platform boundary

`yasb-limitora` is Windows-only across its complete public runtime surface. The
installed `yasb-limitora` route and `python -m yasb_limitora` converge on one
early gate. On non-Windows runtimes the gate returns `2`, writes exactly
`yasb-limitora: unsupported_platform\n` to stderr, writes no stdout, and runs
before argument, configuration, provider, native-process, or clock activity.
Linux, macOS, and WSL are not compatibility targets. Test-only predicate
injection keeps supported-path tests hermetic without claiming Windows proof.

R1-R10 are evidenced product work. R10's automated proof covers the native
Windows CLI/JSON v2 boundary; the real YASB CustomWidget behavior was accepted
manually by the maintainer on YASB v2.0.6. The abandoned automation harness is
historical context only, and this boundary does not claim automated YASB E2E or
automated YASB rendering.

## Ownership

| Component | Owns | Does not own |
|-----------|------|--------------|
| YASB CustomWidget | Host lifecycle, compact/alternate labels, tooltip, static CSS, periodic/manual refresh | Provider calls, credentials, JSON interpretation, cancellation of a running helper |
| `yasb-limitora` | Version selection, config resolution, bounded execution, safe projection, JSON serialization | Provider implementation or private Limitora APIs |
| Limitora 0.2.0 Bearer public API | Provider detection, authentication, transport, status state, freshness, quota windows, Decimal quantities | YASB imports, widget layout, popover behavior |

## Product contract

R2 defines a quota-focused v2 document that keeps these distinctions explicit:

- document execution state;
- provider outcome (`snapshot`, `undetected`, `not_run`, or `execution_error`);
- exact public Limitora provider state;
- independent freshness;
- every quota window and its availability/source context; and
- sanitized execution errors.

The consumed OpenCode 0.2 contract is explicit: `available` and `partial`
snapshots use one fixed commercial slot for each `five_hour`, `monthly`, and
`weekly` period. A `rate_limited` snapshot carries technical windows only and
does not carry per-window commercial provenance. Limitora #55's per-window
rate-limit signal is released upstream in v0.3.0, but it is upstream context
only here and is not consumed until yasb-limitora #133.

`usage` and `rate_limit_reset_credits` are excluded from 0.2. This is an
intentional quota scope, not a claim that it is the complete Limitora snapshot.
JSON v1 remains byte-for-byte frozen for its existing consumer.

## Execution boundary

Codex continues to use a disposable native Windows helper with Job Object
containment and bounded IPC. Future v2 work must use one absolute wall-clock
deadline for guard wait, provider calls, IPC, and cleanup. Each phase receives
only its remaining budget, with cleanup budget reserved. A cleanup guarantee
means bounded eventual termination within that deadline; it does not claim that
YASB's CustomWidget can instantly kill a subprocess when the widget closes.

The shared refresh coordinator uses a Windows cross-process mutex only for short
cache-key state transitions and publication authority. It is not held across a
Codex/OpenCode call or provider cleanup. Each cache key has one bounded marker
containing only a generation, owner PID, non-reusable process-creation token, and
start time. A live owner is waited on with bounded cache/marker retries; a dead
or mismatched owner is reclaimed by incrementing the generation. An unknown
owner or unreadable marker fails closed and is never reclaimed. Publication is
allowed only when the producer still owns the exact generation, so a stale
producer cannot overwrite a newer result. Coordination failures never start an
uncoordinated producer or rewrite a valid provider result.

The v2 runtime also uses a shared quota cache below the default local Limitora
directory. It stores only a schema-2 envelope containing `cached_at`, a
digest-only effective account/config/path fingerprint, and the already
projected public JSON v2 document. Cache reads and writes are atomic, size- and
deadline-bounded, canonical, and fail closed. A fresh cache hit is returned
without a provider call. On a miss, one producer runs with fresh provider
resources while live waiters retry the cache and marker; waiters never launch a
duplicate Codex refresh. Provider cleanup, release, and close finish before
publication, and no cache coordination lease is retained across a provider
call. Cache I/O, mutex, ACL, path, and cleanup failures cannot change a valid
provider result. Provider errors, timeouts, cleanup failures, and all-disabled
runs are never published. Unknown Windows account identity fails closed rather
than permitting cross-account cache reuse.

## CustomWidget limits

The supported UI intentionally stops at the capabilities verified in pinned
YASB CustomWidget v2.0.5:

| Available | Not available as a contract |
|-----------|----------------------------|
| `label`, `label_alt`, and `{data}` formatting | Dynamic CSS based on provider state |
| JSON output and multiline tooltip text | Native popover, tabs, or interactive progress |
| Static CSS and `run_interval` | A public `refreshing` state |
| Manual callback refresh | Reliable termination of the worker's `Popen` from `stop()` |

No v2 field may promise a UI capability in the second column. Presentation
fields are bounded text only; they do not create a severity protocol.

## Non-goals and immutable references

- No native YASB widget or YASB upstream contribution.
- No official extension research or maintainer approval as roadmap work.
- No native popover, generic fixed provider-window assumptions, synthetic
  windows, or absent-as-zero interpretation. The explicit OpenCode 0.2 fixed
  commercial slots are defined by the consumed contract above.
- No Claude, Gemini, costs, tokens, history, predictions, usage, or reset
  credits in 0.2.
- Open Design exports remain immutable. Their README may explain their status,
  but the exports are never edited or used as runtime code.

See [`docs/roadmap.md`](../roadmap.md) for the ordered R1-R11 product plan and
[`docs/specifications/json-v2.md`](../specifications/json-v2.md) for the
normative boundary.
