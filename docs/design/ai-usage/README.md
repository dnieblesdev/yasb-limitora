# AI Usage and Design References

This directory records Open Design reference exports and their provenance. The
exports are immutable visual references, not runtime code and not a roadmap
authorization.

## Design reference assets

| File | Purpose | Status | Source |
|------|---------|--------|--------|
| `widget.html` | Reference widget markup | missing | Open Design export |
| `styles.css` | Reference widget styling | missing | Open Design export |
| `critique.json` | Design critique or feedback export | missing | Open Design export |
| `reference-final.png` | Final reference image | missing | Open Design export |

All assets are currently missing. If approved assets are added later, they must
be copied byte-for-byte. Do not generate, edit, optimize, or invent missing
exports.

## Product boundary

The 0.2 product uses YASB `CustomWidget` and the CLI/JSON seam defined by the
roadmap and R2 specification. CustomWidget may render compact and alternate
labels, multiline tooltip text, static CSS, and periodic/manual refresh.

The Open Design references do **not** authorize implementation of a native
popover, tabs, interactive progress, dynamic severity CSS, or any native YASB
widget. Those capabilities exceed the verified CustomWidget boundary.

## Asset provenance

No candidate visual references were found during scaffold preparation. Searches
covered this repository, the Limitora checkout, `/home/dniebles/workplace/`, and
`/home/dniebles/` for `.png`, `.html`, `.css`, and `.json` files. No unrelated
asset may be copied as a substitute.

## Rules for future assets

- Inspect every candidate for credentials or secrets before copying.
- Document the exact source path when an asset is approved.
- Preserve source bytes, metadata, and image encoding exactly.
- Keep visual specifications separate from the JSON contract and runtime code.

## AI assistance record

- The initial repository scaffold and documentation were produced with
  assistance from an LLM coding agent.
- No provider endpoints, auth logic, or network code were generated here.
- No credentials, tokens, or secrets were inserted into any file.
