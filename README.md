# yasb-limitora

`yasb-limitora` is a Windows command and JSON boundary for the YASB
`CustomWidget`. It reads quota-focused data through the released public
[Limitora](https://github.com/dnieblesdev/limitora) API and never makes provider
calls from YASB.

> **Current status:** R1 product source of truth and R2 JSON v2 specification
> work are the only approved 0.2 units. R3 runtime implementation is blocked.

## Official architecture

```text
YASB CustomWidget -> yasb-limitora CLI / JSON v2 -> Limitora public API
```

The dependency direction is one-way. Limitora owns provider selection,
authentication, transport, and provider-specific interpretation. The CLI owns
configuration resolution, execution safety, sanitized projection, and the
versioned machine boundary. YASB owns only CustomWidget lifecycle and display.

The v1 document remains frozen for existing consumers. JSON v2 is specified in
[`docs/specifications/json-v2.md`](docs/specifications/json-v2.md), but is not
implemented by this review unit.

## CustomWidget boundary

The supported product path is the existing YASB CustomWidget. Its honest 0.2
capabilities are:

| Supported | Not promised by CustomWidget |
|-----------|------------------------------|
| Compact label and alternate label | Dynamic state-dependent CSS |
| Multiline tooltip | Intermediate `refreshing` output |
| Static CSS classes | Native popover or tabs |
| Periodic refresh | Interactive progress controls |
| Manual/callback refresh | Termination of a running YASB subprocess |

The adapter must therefore publish safe quota-focused evidence, including
truthful partial, undetected, not-run, and error outcomes, or safe fallback text.
It must not invent a native widget, a native popover, a severity class, or an
in-progress state that CustomWidget cannot render or cancel.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Windows CLI, JSON v1 compatibility, and JSON v2 contract | Native YASB widget code |
| Limitora public API integration | YASB upstream contribution or maintainer approval |
| Hermetic fixtures, contract tests, and pinned CustomWidget validation | Native popover, tabs, history, predictions, or interactive progress |
| Sanitized configuration and process execution | Credentials, tokens, sessions, or duplicated provider logic |

Only Codex and OpenCode Go are current 0.2 provider inputs because they are the
public provider sources verified in Limitora 0.1.0. Claude and Gemini are not
roadmap work for this contract.

## Installation and v1 runtime

On native Windows 10/11:

```powershell
py -m pip install "limitora==0.1.0"
py -m pip install "yasb-limitora[opencode-go]"
```

The current v1 command and its environment-only `LIMITORA_AUTH_COOKIE` rule are
documented in [`docs/windows-json.md`](docs/windows-json.md). No-argument v1
execution remains all-disabled and must not consult a default configuration
path. Do not place credentials in configuration, argv, stdout, stderr, or test
artifacts.

## Documentation map

- [`docs/roadmap.md`](docs/roadmap.md): official 0.2 R1-R11 order and gates.
- [`docs/architecture/README.md`](docs/architecture/README.md): ownership and
  boundary decisions.
- [`docs/research/README.md`](docs/research/README.md): verified CustomWidget
  and Limitora evidence.
- [`docs/specifications/json-v2.md`](docs/specifications/json-v2.md): normative
  R2 contract, acceptance criteria, and R3 block.
- [`docs/specifications/json-v2.schema.json`](docs/specifications/json-v2.schema.json):
  structural machine-checkable support for the normative specification.

Open Design exports remain immutable, byte-for-byte reference artifacts. They do
not authorize native YASB implementation work.

## Security invariants

- Provider secrets and request logic remain inside Limitora.
- Credential-like configuration keys are rejected.
- Workspace identifiers, raw provider payloads, runner details, and exceptions
  never cross the machine boundary.
- Unknown provider states and invalid data fail closed without raw-value leakage.
- The cross-process execution guard is bounded and scoped to the Windows user
  and canonical effective configuration path; it is not request coalescing.

## Roadmap gate

R3 is explicitly blocked until R2 has an accepted normative specification,
passing v1 golden fixtures, traceable acceptance criteria, and a final
technical review pass. See [`docs/roadmap.md`](docs/roadmap.md).

## License

MIT. See [LICENSE](LICENSE).
