# Scripts

This directory holds optional helper scripts for development, research, and
diagnostics for the YASB-side integration.

## Rules

| Rule | Description |
|------|-------------|
| Read-only | Scripts must not modify source files, test data, or active sessions without explicit confirmation. |
| Safe | Scripts must validate inputs and fail cleanly. |
| Documented | Each script must include a header comment explaining purpose, usage, and exit codes. |
| Removable | Scripts must not be required for the widget to function; they are optional tooling. |
| No secrets | Scripts must not store, log, or transmit credentials, tokens, sessions, cookies, or API keys. |
| No session modification | Scripts must never create, alter, or terminate user/provider sessions. |
| No provider calls | Scripts must not call LLM providers directly; they may only inspect local Limitora state or YASB config. |

## Allowed extensions

- Python (`.py`)
- Shell (`.sh`)

## Prohibited

- Storing `.env` files or credentials.
- Writing unredacted diagnostic dumps.
- Network calls that are not explicitly documented in the script header.
- Duplicating provider auth, endpoint, or request logic that belongs in Limitora.
