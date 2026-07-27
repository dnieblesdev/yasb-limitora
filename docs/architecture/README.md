# yasb-limitora product boundary

The product boundary is deliberately one-way: [YASB](https://github.com/amnweb/yasb)
consumes `yasb-limitora`, and `yasb-limitora` consumes the public
[Limitora 0.1.0](https://github.com/dnieblesdev/limitora) API. The JSON document
is the machine-facing contract between the integration and its future YASB
consumer; provider internals do not cross that boundary.

```text
YASB host  ──loads──>  yasb-limitora  ──public API only──>  Limitora 0.1.0
   ▲                         │                                  │
   └──── versioned JSON ─────┴──── provider results ────────────┘
```

## Ownership

| Component | Owns | Does not own |
|-----------|------|--------------|
| YASB | Host lifecycle and eventual native presentation | Provider calls, credentials, or JSON internals |
| `yasb-limitora` | Configuration, coordination, safe projection, and JSON serialization | Provider implementation or private Limitora APIs |
| Limitora 0.1.0 | Public provider clients, transport, authentication, and provider-specific behavior | YASB imports or widget concerns |

Each provider has an independent public client, configuration, and state. A
Codex failure therefore cannot erase or reinterpret an OpenCode Go result. The
integration preserves the fixed states `loading`, `success`, `unavailable`, and
`safe_error` for each provider.

## Native Windows Codex isolation

Codex runs only in a disposable native Windows helper process owned by
`yasb-limitora`. Before the helper receives authorization to invoke Limitora,
the parent establishes a Windows Job Object containment boundary and completes
a `contained → ready → go` handshake. Setup, assignment, readiness, timeout,
or cleanup failure is a safe error: the integration never falls back to
uncontained execution. Terminal cleanup terminates the complete contained tree,
waits for it, and verifies that no descendant remains.

## Versioned JSON seam

The CLI emits one UTF-8 JSON document with integer `version: 1`, fixed provider
order (`codex`, then `opencode_go`), stable state spellings, and safe fields
only. Diagnostics are sanitized and go to stderr. A future YASB consumer needs
only this versioned document, not a provider SDK, process handle, or private
payload. Widget rendering and popover behavior are explicit non-goals for this
machine-JSON slice.

## Security invariants

- `authCookie` enters only through the documented environment variable and is
  memory-only; it never appears in argv, JSON, logs, or diagnostics.
- Credentials, workspace IDs, private payloads, runner details, and raw
  exceptions never cross the JSON or diagnostic boundary.
- Malformed configuration and unknown failures map to deterministic safe
  states and reasons without echoing sensitive input.
- Limitora remains unchanged and is accessed only through its public 0.1.0
  surface.

See the [project overview](../../README.md) for repository scope and the
[Limitora repository](https://github.com/dnieblesdev/limitora) for the upstream
public API.
