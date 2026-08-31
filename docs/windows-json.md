# Windows-only JSON runtime

`yasb-limitora` provides an executable Windows-only machine-JSON boundary for
Codex and OpenCode Go. The official 0.2 consumer is YASB's existing
`CustomWidget`; this repository does not implement a native YASB widget or
popover. This page documents the sole current JSON contract, selector-free
invocation, and the OpenCode Go Bearer-key delivery boundary. The immutable
normative reference is [`specifications/json-v2.md`](specifications/json-v2.md).

## Quick path

1. Use native Windows 10 or 11. WSL is not the production runtime or proof environment.
2. Install Python and the checkout runtime from the repository root. The
   `yasb-limitora` package is not published to PyPI:

   ```powershell
   py -m pip install --upgrade pip
   py -m pip install -e .
   ```

3. Create a local JSON configuration file. Do not put keys, tokens, or other
   credentials in it.
4. For OpenCode Go, follow [the `.env` flow](#opencode-go-key-flow).
5. Run the module or installed console entry point and parse stdout as one JSON
   document.

### Copy-ready OpenCode flow

Create or select the separate Limitora JSON configuration before starting YASB:
use `%LOCALAPPDATA%\yasb-limitora\config.json`, or set `YASB_LIMITORA_CONFIG` to an explicit startup path. Enable OpenCode Go and keep the file key-free:

```json
{"opencode_go": {"enabled": true, "timeout_seconds": 7}}
```

Create the startup-loaded `.env` with `LIMITORA_OPENCODE_API_KEY=<key>`, then merge
`limitora_r9_opencode_manual` from `examples/customwidget/customwidget.yaml` into YASB's
`widgets:` map and register it in a YASB bar. Its literal command is the selector-free `yasb-limitora`; its label/tooltip read `providers[1]`. Keep `limitora_r9` Codex-only on `providers[0]` and follow the `.env` reload/manual acceptance steps before treating this as a real provider check.

## Runtime support boundary

The installed console route and `python -m yasb_limitora` use the same central
gate. Outside Windows, either route returns exit code `2`, writes exactly
`yasb-limitora: unsupported_platform\n` to stderr, and writes zero stdout
bytes. This rejection happens before argv inspection, environment lookup,
configuration, provider or native-process work, and clock reads.

Linux, macOS, and WSL are not supported execution environments. Hermetic tests
may inject the private platform predicate to exercise supported behavior, but
that seam is not a compatibility mode or Windows integration proof.

## Configuration

The CLI accepts only `--config PATH`, `-c PATH`, or `--config=PATH`. The file is
local JSON with these provider fields:

```json
{
  "codex": {
    "enabled": true,
    "runner": "C:\\Program Files\\Codex\\codex.exe",
    "timeout_seconds": 7
  },
  "opencode_go": {
    "enabled": true,
    "timeout_seconds": 7
  }
}
```

The Codex runner must be an absolute Windows path. OpenCode Go has no workspace,
cookie, dashboard, or endpoint setting in this consumer. A disabled provider is
represented as `not_run` with `not_run_reason: disabled`.

Configuration failures split by scope. A malformed provider object is
provider-scoped: only that provider is projected as `provider_failed/provider`,
and a valid peer provider remains eligible to run. Top-level grammar, path,
JSON decoding, and deadline errors remain document/global configuration
failures and produce `configuration_invalid` with exit code `2`.

For manual OpenCode acceptance, use the Limitora JSON at
`%LOCALAPPDATA%\yasb-limitora\config.json`, or set `YASB_LIMITORA_CONFIG` to an
explicit JSON path. That file must set `"opencode_go": {"enabled": true}`.
`YASB_CONFIG_HOME` controls only YASB's YAML and `.env` directory; it does not
select the Limitora JSON.

### Configuration resolution

Every selector-free invocation selects exactly one configuration source in this order:

1. An explicit `--config PATH`, `-c PATH`, or `--config=PATH`.
2. The non-empty `YASB_LIMITORA_CONFIG` environment variable.
3. `%LOCALAPPDATA%\yasb-limitora\config.json`.

An empty or whitespace-only `YASB_LIMITORA_CONFIG` is a
`configuration_invalid` error; it does not fall back to the default. If
`LOCALAPPDATA` is absent, empty, or whitespace-only when the default is needed,
the result is also `configuration_invalid`. A selected missing, unreadable, or
invalid file fails closed with no fallback, auto-creation, migration, or file
mutation. Paths and environment values are never included in stdout or stderr.

A former output selector is invalid input and cannot route to another document.
There is no compatibility output. The current contract is a deliberate pre-stable
wire and schema break; private consumers are not ruled in or out.

### OpenCode Go key flow

The supported operator flow is one startup-loaded YASB `.env` file:

```dotenv
LIMITORA_OPENCODE_API_KEY=<key>
```

Store that line in `%USERPROFILE%\.config\yasb\.env`, or `%YASB_CONFIG_HOME%\.env` when that OS variable was set before startup. `YASB_CONFIG_HOME` is only YASB's YAML/.env location, not Limitora JSON; an existing OS environment value wins over `.env`. The key is read only from the effective environment, and YASB's CustomWidget subprocess inherits it without changing the command.

After creating/changing `.env`, run `yasbc reload`; it starts a fresh YASB process and reloads `.env`. If YASB is not running, use the manual restart/start fallback. Keep the file user-private; never copy its contents into YAML, JSON, `run_cmd`, argv, stdout, stderr, logs, fixtures, dumps, or bug reports.

### Bounded OpenCode outcomes

The following public errors are intentionally short and stable. They contain
only `code` and `phase`; raw responses, exception text, paths, and credentials
are never exposed.

| Code | Cause | Operator action |
|---|---|---|
| `credential_invalid` | The attempted key is invalid, revoked, or unauthorized. | Check the approved key source, replace it there, then run `yasbc reload` or use the manual restart/start fallback. |
| `provider_timeout` | The provider request exceeded its bounded timeout or remaining document deadline. | Check provider reachability and use a timeout within the documented bound; retry on the next refresh. |
| `provider_rate_limited` | OpenCode returned a provider-level rate-limit response (HTTP 429). | Wait and retry; do not interpret it as a per-window quota result. |
| `provider_failed` | OpenCode failed without a more specific bounded classification. | Retry and inspect only the bounded public state and code. |
| `provider_unavailable` | OpenCode was attempted but no supported provider observation was available. | Check the installation/provider availability and retry; inspect only the bounded public state. |
| `invalid_provider_data` | A provider response failed validation. | Retry and report only the bounded error; do not expose the response. |
| `unknown_provider_state` | A future or unrecognized provider state was received. | Treat it as failed closed and wait for a compatible provider adapter. |

A missing or empty `LIMITORA_OPENCODE_API_KEY` is **not** an invalid-credential
error: OpenCode alone is `not_run` with `not_run_reason: disabled`, and
no request is attempted. It is neither public state `unavailable` nor error
`provider_unavailable`. `unavailable` is a state inside a returned snapshot;
`provider_unavailable` is an attempted-provider execution error. Likewise,
`invalid_data` is a public state, while `invalid_provider_data` is a sanitized
validation error. Codex and OpenCode outcomes are independent, so one provider's
error never erases the other provider's valid result.

The complete provider-state vocabulary is `available`, `partial`,
`unavailable`, `unauthorized`, `rate_limited`, `transient_error`, and
`invalid_data`. The complete public error vocabulary is
`invocation_invalid`, `configuration_invalid`, `guard_acquisition_failed`,
`guard_wait_timeout`, `deadline_exhausted`, `credential_invalid`,
`provider_timeout`, `provider_rate_limited`, `provider_unavailable`,
`provider_failed`, `ipc_failed`, `cleanup_failed`, `invalid_provider_data`,
`unknown_provider_state`, and `internal_error`.

### Numeric-window contract

For OpenCode `available` or `partial` snapshots, the public contract has exactly the commercial periods `five_hour`, `monthly`, and `weekly`. A validated numeric window with source `opencode-go-api` remains known; missing or invalid fixed slots, including ambiguous duplicates, become unavailable with null numeric values. Unavailable is reserved for those fixed-slot cases.
Unrecognized extra commercial periods are discarded; no zero or substitute value is invented. Rate-limited snapshots preserve only technical rate-limit windows. Limitora #55 was implemented and released in v0.3.0 as historical upstream context; #133 remains the downstream follow-up and is outside the #130/0.2 migration until separately approved and verified. This consumer exposes only the current provider-level bounded error.

## Running and streams

### Current commands

Both forms invoke the same `yasb_limitora.cli:main` entry point and use the
selector-free current contract:

```powershell
py -m yasb_limitora --config .\limitora.json
yasb-limitora --config .\limitora.json
```

Stdout contains exactly one UTF-8 JSON document and its terminating newline.
The envelope is ordered `execution_state`, `execution_error`, `providers`, with no root
`version` field. Providers remain in the fixed order `codex`, then `opencode_go`.
Sanitized diagnostics, when needed, go to stderr;
credentials, workspace IDs, private provider payloads, raw exceptions, and
runner details are not emitted.

The document uses `execution_state` values `complete`, `partial`, `not_run`, and
`execution_error`; providers use `snapshot`, `undetected`, `not_run`, or
`execution_error`, with validated snapshot status in `public_state`. Document and
provider fields remain independent, preserving each provider error in its own slot.

The exit matrix is unchanged. A mixed usable result
keeps exit code `0` even when another provider carries a provider-scoped
failure. A provider-owned failure with no usable provider uses exit code `1`.
A document/global execution failure uses exit code `2`, and unsupported-runtime,
invocation, or configuration failures also use exit code `2`. A provider-scoped
configuration error behaves like a provider failure for exit purposes; it never
changes a valid peer result.

| Code | Meaning |
| ---: | --- |
| `0` | No document `execution_error`, including a mixed usable result where another provider carries a provider-scoped failure. |
| `1` | A provider-owned failure was projected as `execution_error` and no provider result remains usable. |
| `2` | A document/global execution failure, including `guard_acquisition_failed`, `guard_wait_timeout`, or `deadline_exhausted`. |
| `2` | An unsupported runtime, or malformed invocation/configuration. Unsupported-platform rejection uses the exact stderr contract above and no JSON stdout. |

### Frozen PyInstaller runtime

In the frozen PyInstaller runtime, the installed and module routes keep
the same JSON/stream/exit contracts as the source runtime, including selector-free
configuration resolution, the exit matrix, and bounded stderr;
unsupported-platform, invocation, and configuration rejection keep their exact
streams and exit code `2`. The Codex helper still runs in a disposable child
process, but the frozen build relaunches it as an internal child of the frozen
executable instead of spawning a Python interpreter. That internal child
relaunch is not a public CLI invocation: it uses the private helper environment
only, and it preserves the same JSON stream, bounded IPC, and exit contracts as
the source-runtime child.

## Availability and fail-safe behavior

Codex runs in a disposable helper process. The helper receives bounded private
IPC and is authorized only after the native Windows Job Object containment and
readiness handshake succeed. A setup, assignment, nested-Job, handshake, or
cleanup verification failure becomes a safe provider error. The runtime never
continues with an uncontained helper and never substitutes PID killing for Job
Object tree cleanup.

OpenCode Go remains an independent direct provider call with its own configured
timeout. A Codex timeout does not erase an OpenCode Go result, and vice versa.

The public cache uses schema-3 validation. A previous-schema entry is stale and is
cold-refreshed rather than migrated or served. Its filename remains
`quota-v2-cache.json`; guard identities remain exactly
`Global\\yasb-limitora-v2-guard-*`, and provider source IDs remain exactly
`codex-app-server-v2` and `opencode-go-api`.

## YASB CustomWidget seam

The sole handoff to YASB CustomWidget is the current stdout JSON envelope. The
CustomWidget configuration consumes provider outcomes and bounded presentation
fields through its
compact/alternate labels and tooltip. Native widget code, popovers, tabs,
interactive progress, dynamic state CSS, and subprocess termination are not
part of this runtime boundary.

### Executable discovery

The bare `yasb-limitora` command in the documented
`run_cmd: "yasb-limitora"` form requires YASB
to inherit a user `PATH` that contains the installed console script. After
installing or changing that user `PATH`, restart YASB so its process receives
the updated environment. A fully qualified executable may be used locally as a
diagnostic or workaround when investigating PATH inheritance; machine-specific
paths must not be published in configuration, documentation, or issue logs.

## Manual native YASB acceptance

R10 generic YASB CustomWidget acceptance is complete, and OpenCode Bearer API
migration #130 is complete and integrated via PR #159. This is the remaining R11
gate after completed #130: real OpenCode provider acceptance is a **manual
acceptance procedure, not automated E2E**. Run it only with an existing real
Windows YASB installation and authorized test environment; do not install/embed
YASB, invent a key, or make an unauthorized request. Otherwise the provider gate
remains externally pending.

Using the copy-ready example in `examples/customwidget/`:

1. Create/select the dedicated Limitora JSON with
   `"opencode_go": {"enabled": true}`. Temporarily add
   `limitora_r9_opencode_manual` to YASB's `widgets:` config and bar list. It uses
   `providers[1]`; keep `limitora_r9` on `providers[0]` and label it Codex-only.
2. Put the approved test key only in `.env`, run `yasbc reload` to start a fresh
   process and reload it (or manually restart/start if YASB is not running), then
   observe the temporary OpenCode label/tooltip and safe quota data.
3. Disable the key from **both** sources: remove the
   `LIMITORA_OPENCODE_API_KEY` line from `.env` and clear/unset any
   `LIMITORA_OPENCODE_API_KEY` value in the current/inherited OS environment,
   including persistent User/Machine definitions. Do not print it. Reload (or manually restart/start), verify only OpenCode is
   `not_run` with `not_run_reason: disabled`, and restore it only to an approved
   source if needed; restore it securely and never put it in YAML, JSON, `run_cmd`, argv, output, logs, or
   reports.
4. Exercise authorized invalid/revoked-key, provider failure, timeout, rate-limit,
   and unavailable-provider cases; verify each bounded code/action without raw
   response. Exercise current/partial windows: valid values remain, invalid or
   ambiguous fixed periods are unavailable/null, extras are discarded, and no
   zero is invented.
5. Review YAML, `run_cmd`, argv, JSON, stdout, stderr, logs, fixtures, and dumps
   for secret absence. Record only redacted pass/fail observations; never attach
   `.env`, a secret, raw response, or environment-specific path.

The acceptance result must state the existing YASB version/environment, remain
explicitly manual, and remove/revert the temporary widget from both the YASB bar
list and `widgets:` config after acceptance.

## Verified limitations and troubleshooting

- Native Job Object and descendant cleanup require native Windows. Linux and
  WSL may run hermetic protocol tests, but they are not native proof.
- A Codex runner must be an existing absolute path accepted by Limitora's public
  Codex adapter. Relative paths are invalid configuration.
- OpenCode Go requires the `opencode-go` installation extra. A missing
  key leaves only OpenCode `not_run` with `not_run_reason: disabled`, not
  `unavailable`; configuration files reject credential-like keys.
- Put no key or token in JSON, YAML, argv, logs, fixtures, dumps, or artifacts.
- If native containment is unavailable or the process is already in a Job that
  cannot accept a nested Job, expect an `execution_error` rather than
  unisolated execution.
  Inspect only the sanitized stderr diagnostic and bounded JSON error code.
- The native proof is explicitly selected by
  [`.github/workflows/windows-proof.yml`](../.github/workflows/windows-proof.yml)
  on `windows-latest`; a skipped test is not proof.
