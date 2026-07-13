# AI usage and design references

This directory holds Open Design reference exports and records how generative AI
tools were used to produce or refine this project.

## Design reference assets

The following files are reserved for Open Design exports and visual references.
They are **specifications, not implementation**. They show the intended look and
layout but must be reproduced with native YASB components; no webview, embedded
browser, or copied DOM is allowed.

| File | Purpose | Status | Source |
|------|---------|--------|--------|
| `widget.html` | Reference widget markup | missing | Open Design export |
| `styles.css` | Reference widget styling | missing | Open Design export |
| `critique.json` | Design critique or feedback export | missing | Open Design export |
| `reference-final.png` | Final reference image | missing | Open Design export |

All assets are currently missing. They will be copied byte-for-byte from an Open
Design session once available. Do not generate or invent missing assets.

## Asset provenance

No candidate visual references were found in the workspace during scaffold
preparation. Searches covered:

- `/home/dniebles/workplace/yasb-limitora`
- `/home/dniebles/workplace/limitora`
- `/home/dniebles/workplace/`
- `/home/dniebles/` for `.png`, `.html`, `.css`, and `.json` files

Only unrelated assets were discovered. No Open Design exports were present, so
nothing was copied.

## HTML/CSS disclaimer

Reference HTML and CSS are **visual specifications only**. They describe the
intended appearance and behavior of the widget but are not runnable code for this
repository. The actual implementation must use native YASB components, layout
primitives, and styling mechanisms.

## Native pieces to reproduce

When assets become available, reproduce the following functional pieces as
native YASB components:

- **Compact widget**: small status/selector shown in the YASB bar.
- **Popup**: expanded view triggered from the compact widget.
- **Tabs**: navigation between provider groups or categories.
- **All view**: aggregate provider overview.
- **Provider views**: per-provider detailed views.
- **Quota rows**: usage/remaining quota display rows.
- **States**: loading, idle, success, error, and disabled visual states.
- **Alerts**: warning or error notifications.

## Non-implemented decorative pieces

The following decorative context pieces shown in the reference image must not be
implemented as part of the widget:

- Fake desktop background or wallpaper.
- Code editor window or IDE chrome.
- Demo scene, mock browser, or staged environment decorations.

## Rules for future assets

- Copy approved assets byte-for-byte. Do not edit HTML, CSS, JSON metadata, or
  image optimization.
- Inspect every candidate for credentials or secrets before copying.
- Document the exact source path in this readme.
- Never invent or generate missing reference assets.

## AI assistance record

- The initial repository scaffold, README, and documentation were produced with
  assistance from an LLM coding agent.
- No provider endpoints, auth logic, or network code were generated.
- No credentials, tokens, or secrets were inserted into any file.
