# Limitora CustomWidget example

This directory is a copy-ready **YASB v2.0.5** CustomWidget example for the
existing `yasb-limitora --output-version 2` presentation contract. It adds no
widget runtime, provider logic, quota calculations, or CSS state machine.

## Quick path

1. Install `yasb-limitora` using your preferred local method.
2. Merge the named `limitora_r9` entry from `customwidget.yaml` into YASB's
   `widgets:` map, then add `limitora_r9` to the desired bar widget list.
3. Copy or merge `styles.css` into the YASB stylesheet.
4. Ensure YASB inherits the user `PATH` containing `yasb-limitora`, restart YASB,
   and confirm that the label and tooltip show the CLI output.

The installation advice is provisional. It is not an R11 release, packaging,
or automatic-installation contract. The command in the YAML is the real CLI;
the JSON files in `fixtures/` are validation-only documents and are not
executable commands.

The bare `yasb-limitora` command depends on YASB inheriting the updated user
`PATH`; restart YASB after installing or changing PATH. A fully qualified
executable is only a local diagnostic/workaround for PATH troubleshooting. Do
not commit or publish a machine-specific path.

## What the YAML renders

The YAML is a named YASB widget entry with `type: yasb.custom.CustomWidget`
and its verified options nested under `options:`.
The primary label uses `compact_text`, the alternate label uses
`alternate_text`, and the tooltip uses `tooltip_text` as supplied. The YAML
does not calculate percentages, inspect windows, infer quota models, invent
states, turn absence into zero, or expose diagnostics.

YASB's formatter has no provider identity selector. This example therefore
uses the explicitly bounded provider order `[codex, opencode_go]` and
`providers[0]` is the codex adapter. The order is part of the JSON v2
contract; do not reuse this path for an unverified provider order.

`styles.css` is static. It targets `.custom-widget.limitora-r9` and supported
descendants only. It does not promise JSON-driven, severity, freshness, or
provider-dependent CSS classes.

## Fixture boundary

The baseline fixtures cover complete, partial, stale, undetected,
provider-unavailable, providers-disabled, and safe-error presentation. They
are strict JSON v2 validation inputs with safe presentation strings. They do
not contain process exit codes or stderr metadata, and they are not a runtime
proof of YASB rendering.

R9 validated repository artifacts and the documented data boundary. R10 is now
complete through automated native CLI/JSON proof and maintainer manual
acceptance of the real YASB CustomWidget. This example does not claim automated
YASB rendering or OpenCode real-provider acceptance. R11 owns release,
installation, and packaging contracts.
