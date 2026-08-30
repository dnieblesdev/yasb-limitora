# yasb-limitora

`yasb-limitora` is a Windows-only command and JSON boundary for the YASB
`CustomWidget`. It reads quota-focused data through the released public
[Limitora](https://github.com/dnieblesdev/limitora) API and never makes provider
calls from YASB.

> **Current status:** R1-R10 and generic real YASB CustomWidget manual acceptance
> are complete. Automated native Windows proof covers the `yasb-limitora` CLI/JSON v2
> contract; real OpenCode provider acceptance remains an external pending gate for
> R11/#130. No automated YASB rendering or external YASB E2E is claimed; the CLI is
> Windows-only.

## Runtime support boundary

Every public route (`yasb-limitora` and `python -m yasb_limitora`) converges on
the same CLI gate. On a non-Windows runtime, both routes return exit code `2`,
write exactly `yasb-limitora: unsupported_platform\n` to stderr, and write no
stdout bytes. The gate runs before argument parsing, configuration, provider,
native-process, or clock activity.

Linux, macOS, and WSL are not supported product runtimes. Tests may inject the
private platform predicate to exercise Windows behavior hermetically; that test
seam does not expand product support or provide Windows integration proof.

## Official architecture

```text
YASB CustomWidget -> yasb-limitora CLI / JSON v2 -> Limitora public API
```

The dependency direction is one-way. Limitora owns provider selection,
authentication, transport, and provider-specific interpretation. The CLI owns
configuration resolution, execution safety, sanitized projection, and the
versioned machine boundary. YASB owns only CustomWidget lifecycle and display.

The v1 document remains frozen; missing or empty OpenCode keys retain v1's existing
`unavailable` behavior. JSON v2 is specified in
[`docs/specifications/json-v2.md`](docs/specifications/json-v2.md) and uses `not_run` with
`not_run_reason: disabled` instead, behind the same Windows-only boundary.

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
public provider sources verified in Limitora 0.3.1. Claude and Gemini are not
roadmap work for this contract.

## Installation and v1 runtime

On native Windows 10/11:

```powershell
py -m pip install -e .
```

`yasb-limitora` is not published to PyPI; run `py -m pip install -e .` from the
checkout root (the checkout pins `limitora[opencode-go]==0.3.1`). See
[`docs/windows-json.md`](docs/windows-json.md) for `.env`, reload, precedence,
security, bounded-error, and manual YASB procedures. Frozen v1 keeps missing/empty
OpenCode-key `unavailable`, independent Codex/document execution, and all-disabled
no-argument behavior without consulting a default configuration path.

## Documentation map

- [`docs/roadmap.md`](docs/roadmap.md): official 0.2 R1-R11 order and gates.
- [`docs/architecture/README.md`](docs/architecture/README.md): ownership and
  boundary decisions.
- [`docs/research/README.md`](docs/research/README.md): verified CustomWidget
  and Limitora evidence.
- [`docs/specifications/json-v2.md`](docs/specifications/json-v2.md): normative
  R2 contract, acceptance criteria, and the historical abandoned-harness boundary
  alongside the completed R10 proof split.
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

R1-R10 are the completed product units recorded in
[`docs/roadmap.md`](docs/roadmap.md). Generic YASB CustomWidget acceptance is complete;
real OpenCode provider acceptance remains an external manual gate for R11/#130.
Automated proof covers the native CLI/JSON v2 boundary; abandoned R10 automation is
historical context only, with no automated YASB rendering claim.

## License

MIT. See [LICENSE](LICENSE).
