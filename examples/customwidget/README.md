# Limitora CustomWidget example

This directory is a copy-ready **YASB CustomWidget** example for the sole current
JSON contract. It invokes `yasb-limitora` without selector
negotiation and adds no widget runtime, provider logic, quota calculations, or
CSS state machine.

## Quick path

1. From the checkout root, install the unpublished package with
   `py -m pip install -e .`.
2. Create or select the separate Limitora JSON at
   `%LOCALAPPDATA%\yasb-limitora\config.json` (or select an explicit
   `YASB_LIMITORA_CONFIG` path) with `"opencode_go": {"enabled": true}` and no
   credential. The selector-free command in the YAML uses the sole current output.
3. Before starting YASB, create `%USERPROFILE%\.config\yasb\.env`, or
   `%YASB_CONFIG_HOME%\.env` when that OS variable was set before startup, with
   `LIMITORA_OPENCODE_API_KEY=<key>`.
4. For the OpenCode flow, temporarily merge the named
   `limitora_r9_opencode_manual` entry from `customwidget.yaml` into YASB's
   `widgets:` map and register `limitora_r9_opencode_manual` in the desired bar.
   It reads `providers[1]`. The default `limitora_r9` entry is Codex-only: it
   reads `providers[0]` and its label is not an OpenCode indicator.
5. Merge the named `limitora_r9` entry from `customwidget.yaml` into YASB's
   `widgets:` map, then add `limitora_r9` to the desired bar widget list.
6. Copy or merge `styles.css` into the YASB stylesheet.
7. Ensure YASB inherits the user `PATH` containing `yasb-limitora`, then fully
   restart YASB and confirm that the selected label and tooltip show the CLI output.

The installation advice is provisional. It is not an R11 release, packaging,
or automatic-installation contract. The command in the YAML is the real CLI;
the JSON files in `fixtures/` are validation-only documents and are not
executable commands.

The bare `yasb-limitora` command depends on YASB inheriting the updated user
`PATH`; restart YASB after installing or changing PATH. `.env` reload uses
`yasbc reload`, which starts a fresh process; use a manual restart/start fallback
when YASB is not running. An already-defined OS `LIMITORA_OPENCODE_API_KEY` takes
precedence over `.env`. A fully qualified executable is only a local
diagnostic/workaround for PATH troubleshooting. Do not commit or publish a
machine-specific path.

## What the YAML renders

The YAML is a named YASB widget entry with `type: yasb.custom.CustomWidget`
and its verified options nested under `options:`.
The primary label uses `compact_text`, the alternate label uses
`alternate_text`, and the tooltip uses `tooltip_text` as supplied. The YAML
does not calculate percentages, inspect windows, infer quota models, invent
states, turn absence into zero, or expose diagnostics. Its command is
intentionally literal and uses `use_shell: false`; the inherited environment
carries the key. Never place the key in YAML, `run_cmd`, argv, JSON, logs,
fixtures, or dumps.

YASB's formatter has no provider identity selector within one widget. The
copy-ready `limitora_r9` entry therefore uses the explicitly bounded provider
order `[codex, opencode_go]` and `providers[0]` is the codex adapter. The order
is part of the current JSON contract; do not reuse this path for an unverified
provider order.

`styles.css` is static. It targets `.custom-widget.limitora-r9` and supported
descendants only. It does not promise JSON-driven, severity, freshness, or
provider-dependent CSS classes.

## Fixture boundary

The baseline fixtures cover complete, partial, stale, undetected,
provider-unavailable, providers-disabled, and safe-error presentation. They
are strict current JSON validation inputs with safe presentation strings. They do
not contain process exit codes or stderr metadata, and they are not a runtime
proof of YASB rendering.

The fixtures validate the repository's bounded presentation data only. Generic
YASB CustomWidget acceptance is complete; OpenCode Bearer API migration #130 is
complete/integrated via #159; real-provider manual acceptance remains pending for
R11. Follow the manual native procedure in
[`docs/windows-json.md`](../../docs/windows-json.md) only when an existing real
Windows YASB installation and authorized test environment are available.
