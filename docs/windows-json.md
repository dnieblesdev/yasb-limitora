# Windows-only JSON runtime

`yasb-limitora` provides an executable Windows-only machine-JSON boundary for
Codex and OpenCode Go. The official 0.2 consumer is YASB's existing
`CustomWidget`; this repository does not implement a native YASB widget or
popover. This page documents the frozen v1 runtime and v2 configuration behavior. The normative v2 contract
is [`specifications/json-v2.md`](specifications/json-v2.md).

## Quick path

1. Use native Windows 10 or 11. WSL is not the production runtime or proof environment.
2. Install Python and the pinned runtime:

   ```powershell
   py -m pip install --upgrade pip
   py -m pip install "limitora==0.1.0"
   py -m pip install "yasb-limitora[opencode-go]"
   ```

   For a checkout, replace the last command with:

   ```powershell
   py -m pip install -e ".[opencode-go]"
   ```

3. Create a local JSON configuration file. Do not put cookies, tokens, or other
   credentials in it.
4. Set `LIMITORA_AUTH_COOKIE` only in the process environment when OpenCode Go
   is enabled.
5. Run the module or installed console entry point and parse stdout as one JSON
   document.

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
    "workspace_id": "your-workspace-id",
    "timeout_seconds": 7
  }
}
```

The Codex runner must be an absolute Windows path. `workspace_id` is local
configuration and is never projected into machine JSON or diagnostics. Missing
or disabled provider configuration produces `unavailable`; malformed local
configuration produces `configuration_invalid` and exit code `2`.

### v2 configuration resolution

V2 is selected only with `--output-version 2` or `--output-version=2`. For v2,
the CLI selects exactly one configuration source in this order:

1. An explicit `--config PATH`, `-c PATH`, or `--config=PATH`.
2. The non-empty `YASB_LIMITORA_CONFIG` environment variable.
3. `%LOCALAPPDATA%\yasb-limitora\config.json`.

An empty or whitespace-only `YASB_LIMITORA_CONFIG` is a
`configuration_invalid` error; it does not fall back to the default. If
`LOCALAPPDATA` is absent, empty, or whitespace-only when the default is needed,
the result is also `configuration_invalid`. A selected missing, unreadable, or
invalid file fails closed with no fallback, auto-creation, migration, or file
mutation. Paths and environment values are never included in stdout or stderr.

V1 remains frozen: no selector and explicit v1 selectors continue to ignore
`YASB_LIMITORA_CONFIG` and `LOCALAPPDATA`, preserve the existing bytes and
streams, and do not use or create a default configuration file.

### Environment-only `authCookie`

`authCookie` is represented by the environment variable
`LIMITORA_AUTH_COOKIE`; it is not a JSON field, command-line argument, or
output field. Set it for the process that runs the CLI, for example:

```powershell
$env:LIMITORA_AUTH_COOKIE = "<set-from-your-secret-store>"
yasb-limitora --config .\limitora.json
```

The value remains memory-only in this package. Do not use `setx` for a shared
machine unless that is the intended Windows secret-handling policy, because it
persists the value outside the current process.

## Running and streams

Both forms invoke the same `yasb_limitora.cli:main` entry point:

```powershell
py -m yasb_limitora --config .\limitora.json
yasb-limitora --config .\limitora.json
```

Stdout contains exactly one UTF-8 JSON document and its terminating newline.
The envelope has integer `version: 1` and providers in the fixed order
`codex`, then `opencode_go`. Sanitized diagnostics, when needed, go to stderr;
credentials, workspace IDs, private provider payloads, raw exceptions, and
runner details are not emitted.

Exit codes are:

| Code | Meaning |
|---:|---|
| `0` | The document contains no `safe_error`. |
| `1` | A provider runtime, timeout, or internal failure was projected as `safe_error`. |
| `2` | The runtime is unsupported, or local invocation/configuration was malformed. Unsupported-platform rejection uses the exact stderr contract above and no JSON stdout. |

The only provider states are `loading`, `success`, `unavailable`, and
`safe_error`. The one-shot CLI normally returns completed `success`,
`unavailable`, or `safe_error` views; `loading` remains part of the closed
contract for future consumers.

## Availability and fail-safe behavior

Codex runs in a disposable helper process. The helper receives bounded private
IPC and is authorized only after the native Windows Job Object containment and
readiness handshake succeed. A setup, assignment, nested-Job, handshake, or
cleanup verification failure becomes a safe provider error. The runtime never
continues with an uncontained helper and never substitutes PID killing for Job
Object tree cleanup.

OpenCode Go remains an independent direct provider call with its own configured
timeout. A Codex timeout does not erase an OpenCode Go result, and vice versa.

## YASB CustomWidget seam

The sole handoff to YASB CustomWidget is the versioned stdout JSON envelope. The
CustomWidget configuration may use documented v1 fields (`version`, provider
key, state, optional safe error code, and optional display label) through its
compact/alternate labels and tooltip. Native widget code, popovers, tabs,
interactive progress, dynamic state CSS, and subprocess termination are not
part of this runtime boundary.

## Verified limitations and troubleshooting

- Native Job Object and descendant cleanup require native Windows. Linux and
  WSL may run hermetic protocol tests, but they are not native proof.
- A Codex runner must be an existing absolute path accepted by Limitora's public
  Codex adapter. Relative paths are invalid configuration.
- OpenCode Go requires the `opencode-go` installation extra and a non-empty
  `LIMITORA_AUTH_COOKIE`; without both, its state is `unavailable`.
- Configuration files reject credential-like keys. Put no cookie or token in
  JSON, argv, logs, or artifacts.
- If native containment is unavailable or the process is already in a Job that
  cannot accept a nested Job, expect `safe_error` rather than unisolated
  execution. Inspect only the sanitized stderr diagnostic and the safe JSON
  error code.
- The native proof is explicitly selected by
  [`.github/workflows/windows-proof.yml`](../.github/workflows/windows-proof.yml)
  on `windows-latest`; a skipped test is not proof.
