# yasb-limitora

A native-Windows machine-JSON boundary that consumes the [Limitora](https://github.com/dnieblesdev/limitora) library for provider-agnostic status data. A visual YASB widget remains a future consumer.

> **Current status**: the native Windows JSON runtime and process-isolated Codex proof are implemented. Widget and popover integration remain out of scope.

## Purpose

`yasb-limitora` is the YASB-side integration for Limitora. It keeps all LLM provider concerns inside Limitora and only renders native YASB components on this side. The dependency is unidirectional:

```text
yasb-limitora -> limitora
```

YASB never talks to providers directly; Limitora never imports YASB, PyQt, or any UI framework.

## What this repository is

- A future YASB widget seam backed by a versioned machine-JSON document.
- A thin Python package with the exact `limitora==0.1.0` runtime dependency and an optional `opencode-go` installation extra.
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
| Native Windows machine-JSON boundary and proof | Visual YASB widget/popover implementation |
| Consuming Limitora's released public API | Private Limitora imports or duplicated provider logic |
| Documentation, hermetic tests, and Windows CI proof | Auth, token, session, or endpoint storage |

## Provider support

Providers are handled by Limitora. This widget only consumes whatever Limitora exposes.

| Phase | Provider | Status |
|-------|----------|--------|
| 1 | Codex | available through the machine-JSON boundary |
| 1 | OpenCode Go | available through the machine-JSON boundary |
| 2 | Claude | future via Limitora |
| 2 | Gemini | future via Limitora |

## Native Windows installation

On native Windows 10/11:

```bash
py -m pip install "limitora==0.1.0"
py -m pip install "yasb-limitora[opencode-go]"
```

See [`docs/windows-json.md`](docs/windows-json.md) for configuration, environment-only `LIMITORA_AUTH_COOKIE`, execution, streams, exit codes, fail-safe behavior, and verified limitations.

## Local development

Install the package and its minimal contract-test tooling in an isolated environment:

```bash
python -m pip install -e ".[opencode-go,test]"
```

The package resolves the released Limitora dependency from its declared metadata.

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
- Whether the future widget runs in-process with YASB or consumes this JSON as a thin external helper.

See [`docs/research/README.md`](docs/research/README.md) for the full research tracker.

## Security and privacy

- Never store tokens, cookies, sessions, credentials, or provider cache data in this repository.
- Do not commit `.env` files, private keys, or unredacted diagnostic dumps.
- Redacted artifacts must use the names `*.redacted.json` or `*.redacted.txt`.
- All provider secrets and request logic remain inside Limitora.

## Roadmap

1. Confirm the official YASB integration model.
2. Define the future widget contract and native component layout.
3. Consume the versioned JSON seam from a YASB widget.
4. Evaluate Claude and Gemini when Limitora adds support.

## License

MIT. See [LICENSE](LICENSE).
