# yasb-limitora

A lightweight YASB widget that consumes the [Limitora](https://github.com/dnieblesdev/limitora) library for provider-agnostic LLM interaction.

> **Current status**: scaffolding and research. No widget logic, provider code, or network implementation exists yet.

## Purpose

`yasb-limitora` is the YASB-side integration for Limitora. It keeps all LLM provider concerns inside Limitora and only renders native YASB components on this side. The dependency is unidirectional:

```text
yasb-limitora -> limitora
```

YASB never talks to providers directly; Limitora never imports YASB, PyQt, or any UI framework.

## What this repository is

- A future YASB widget for selecting a provider and showing LLM output.
- A thin Python package that imports Limitora at runtime once it is installed separately (no package dependency is declared).
- A place to research how Limitora fits into the official YASB extension model.

## What this repository is not

- It does not duplicate auth, endpoints, rate limiting, or provider logic from Limitora.
- It is not a standalone LLM client.
- It does not ship PyQt, network, or provider-specific code.
- It does not store credentials, tokens, sessions, or cookies.

## Design references

Reference material lives in `docs/design/ai-usage/`. The directory is reserved for Open Design exports such as `widget.html`, `styles.css`, `critique.json`, and `reference-final.png`. Any assets copied there are byte-for-byte exports; source files are never edited.

See [`docs/design/ai-usage/README.md`](docs/design/ai-usage/README.md) for the current asset inventory, provenance, and the list of native pieces to reproduce.

## Scope

| In scope | Out of scope |
|----------|--------------|
| YASB widget scaffolding and research | Provider adapters, API clients, and rate-limit logic |
| Native YASB component layout and styling | PyQt / Qtile / system tray code |
| Consuming Limitora's public API once stable | Auth, token, session, or endpoint management |
| Documentation and integration research | Tests, CI, network calls, and release automation in this phase |

## Provider support

Providers are handled by Limitora. This widget only consumes whatever Limitora exposes.

| Phase | Provider | Status |
|-------|----------|--------|
| 1 | Codex | planned via Limitora |
| 1 | OpenCode Go | planned via Limitora |
| 2 | Claude | future via Limitora |
| 2 | Gemini | future via Limitora |

## Installation (future)

Once published:

```bash
python -m pip install yasb-limitora
```

This will pull `limitora` as a dependency. No manual provider setup is required from this package.

## Local development

`yasb-limitora` declares no package dependencies in `pyproject.toml`; it expects `limitora` to be installed separately. For local development against an unpublished sibling checkout:

1. Install the `limitora` checkout in editable mode.
2. Install this package in editable mode.

```bash
python -m pip install -e ..\limitora
python -m pip install -e .
```

The first command installs the unpublished `limitora` checkout; the second installs `yasb-limitora` only.

> These commands assume both repositories share the same parent directory on Windows. Adjust the path separator when working on Linux or macOS.

## Architecture

The high-level direction is documented in [`docs/architecture/README.md`](docs/architecture/README.md).

Key constraints:

- `yasb_limitora` imports `limitora` only.
- HTML/CSS reference exports become native YASB components; no webview or embedded browser.
- Provider selection and request lifecycle stay inside Limitora.
- No auth, endpoint, or provider logic is duplicated here.

## Pending research

- Official YASB widget/extension API and lifecycle.
- How Limitora's public surface maps to YASB callbacks and signals.
- Whether the widget runs in-process with YASB or as a thin external helper.

See [`docs/research/README.md`](docs/research/README.md) for the full research tracker.

## Security and privacy

- Never store tokens, cookies, sessions, credentials, or provider cache data in this repository.
- Do not commit `.env` files, private keys, or unredacted diagnostic dumps.
- Redacted artifacts must use the names `*.redacted.json` or `*.redacted.txt`.
- All provider secrets and request logic remain inside Limitora.

## Roadmap

1. Confirm the official YASB integration model.
2. Define the widget contract and native component layout.
3. Wire the widget to Limitora's public API once it is stable.
4. Validate Codex and OpenCode Go flows through Limitora.
5. Evaluate Claude and Gemini when Limitora adds support.

## License

MIT. See [LICENSE](LICENSE).
