# yasb-limitora

`yasb-limitora` is a Windows-only command and JSON boundary for the YASB
`CustomWidget`. It reads quota-focused data through the released public
[Limitora](https://github.com/dnieblesdev/limitora) API and never makes provider
calls from YASB.

> **Current status:** R1-R10 and generic real YASB CustomWidget manual acceptance
> are complete. OpenCode Bearer API migration #130 is implemented and integrated
> via PR #159. Automated native Windows proof covers the `yasb-limitora` CLI and the
> sole current JSON contract; real OpenCode provider acceptance remains an external pending gate for
> R11. No automated YASB rendering or external YASB E2E is
> claimed; the CLI is Windows-only.

## Runtime support boundary

Every public route (`yasb-limitora` and `python -m yasb_limitora`) converges on
the same CLI gate. On a non-Windows runtime, both routes return exit code `2`,
write exactly `yasb-limitora: unsupported_platform\n` to stderr, and write no
stdout bytes. The gate runs before argument parsing, configuration, provider,
native-process, or clock activity.

Linux, macOS, and WSL are not supported product runtimes. Tests may inject the
private platform predicate to exercise Windows behavior hermetically; that test
seam does not expand product support or provide Windows integration proof.

## Sole current contract

```text
YASB CustomWidget -> yasb-limitora CLI / current JSON -> Limitora public API
```

The current JSON document is the sole supported output. This is a deliberate
pre-stable wire and schema break: invocation is selector-free, the root `version`
field was removed, and private consumers are not ruled in or out. Configuration
resolves explicit `--config`/`-c`, then `YASB_LIMITORA_CONFIG`, then
`%LOCALAPPDATA%\yasb-limitora\config.json`.

The root order is `execution_state`, `execution_error`, `providers`. Public
provider outcomes, streams, exit codes, shared deadline, guard, process, and
cleanup behavior are unchanged. Schema-3 cache validation cold-refreshes stale
entries rather than migrating them. `quota-v2-cache.json`,
`Global\\yasb-limitora-v2-guard-*`, `codex-app-server-v2`, and `opencode-go-api`
remain exact operational identity literals.

Limitora owns provider selection, authentication, transport, and interpretation;
the CLI owns configuration, bounded execution, sanitized projection, and the
machine boundary. YASB owns only CustomWidget lifecycle and display.

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
| Windows CLI and sole current JSON contract | Native YASB widget code |
| Limitora public API integration | YASB upstream contribution or maintainer approval |
| Hermetic fixtures, contract tests, and pinned CustomWidget validation | Native popover, tabs, history, predictions, or interactive progress |
| Sanitized configuration and process execution | Credentials, tokens, sessions, or duplicated provider logic |

Only Codex and OpenCode Go are current 0.2 provider inputs because they are the
public provider sources verified in Limitora 0.3.1. Claude and Gemini are not
roadmap work for this contract.

## Installation and configuration

On native Windows 10/11:

```powershell
py -m pip install -e .
```

`yasb-limitora` is not published to PyPI; run `py -m pip install -e .` from the
checkout root (the checkout pins `limitora[opencode-go]==0.3.1`). See
[`docs/windows-json.md`](docs/windows-json.md) for `.env`, reload, precedence,
security, bounded errors, cache refresh, and manual YASB procedures.

## Documentation map

- [`docs/roadmap.md`](docs/roadmap.md): official 0.2 R1-R11 order and gates.
- [`docs/architecture/README.md`](docs/architecture/README.md): ownership and
  boundary decisions.
- [`docs/research/README.md`](docs/research/README.md): verified CustomWidget
  and Limitora evidence.
- [`docs/specifications/json-output.md`](docs/specifications/json-output.md): normative
  R2 contract, acceptance criteria, and the historical abandoned-harness boundary
  alongside the completed R10 proof split.
- [`docs/specifications/json-output.schema.json`](docs/specifications/json-output.schema.json):
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
[`docs/roadmap.md`](docs/roadmap.md). Generic YASB CustomWidget acceptance is complete,
and OpenCode Bearer API migration #130 is implemented and integrated via PR #159;
real OpenCode provider acceptance remains an external manual gate for R11.
Automated proof covers the native CLI and current JSON boundary; abandoned R10
automation is historical context only, with no automated YASB rendering claim.

## License

MIT. See [LICENSE](LICENSE).
