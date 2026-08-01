# Product Boundary

The official 0.2 architecture is deliberately narrow:

```text
YASB CustomWidget -> yasb-limitora CLI / JSON v2 -> Limitora public API
```

`yasb-limitora` does not become a native YASB widget, a YASB upstream extension,
or a provider client. The CLI is the process boundary between CustomWidget and
Limitora. Provider internals and credentials do not cross it.

## Ownership

| Component | Owns | Does not own |
|-----------|------|--------------|
| YASB CustomWidget | Host lifecycle, compact/alternate labels, tooltip, static CSS, periodic/manual refresh | Provider calls, credentials, JSON interpretation, cancellation of a running helper |
| `yasb-limitora` | Version selection, config resolution, bounded execution, safe projection, JSON serialization | Provider implementation or private Limitora APIs |
| Limitora 0.1.0 public API | Provider detection, authentication, transport, status state, freshness, quota windows, Decimal quantities | YASB imports, widget layout, popover behavior |

## Product contract

R2 defines a quota-focused v2 document that keeps these distinctions explicit:

- document execution state;
- provider outcome (`snapshot`, `undetected`, `not_run`, or `execution_error`);
- exact public Limitora provider state;
- independent freshness;
- every quota window and its availability/source context; and
- sanitized execution errors.

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

The cross-process execution guard is a bounded mutex guard, not `single-flight`
and not request coalescing. Its scope is the Windows user plus the canonical
effective configuration path. Abandoned acquisition is safe ownership; wait,
creation, release, and deadline failures are sanitized document/provider
outcomes as defined by R2.

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
- No native popover, fixed provider-window assumptions, synthetic windows, or
  absent-as-zero interpretation.
- No Claude, Gemini, costs, tokens, history, predictions, usage, or reset
  credits in 0.2.
- Open Design exports remain immutable. Their README may explain their status,
  but the exports are never edited or used as runtime code.

See [`docs/roadmap.md`](../roadmap.md) for the ordered R1-R11 product plan and
[`docs/specifications/json-v2.md`](../specifications/json-v2.md) for the
normative boundary.
