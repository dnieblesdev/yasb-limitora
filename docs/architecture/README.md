# yasb-limitora architecture

This document describes the intended data flow, layers, and non-negotiable
rules for the YASB-side integration.

## Intended flow

```text
┌─────────────────────────────────────────────┐
│                 YASB bar                    │
│  ┌───────────────────────────────────────┐  │
│  │  yasb-limitora widget (native comp.)  │  │
│  │  - provider selector                  │  │
│  │  - status / output area               │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                       │
                       │ imports
                       ▼
              ┌─────────────────┐
              │    limitora     │
              │  core / models  │
              └─────────────────┘
                       │
                       │ adapters
                       ▼
              ┌─────────────────┐
              │    providers    │
              │ Codex/OpenCode  │
              └─────────────────┘
```

1. YASB loads `yasb_limitora` as a widget.
2. The widget renders native YASB components based on user interaction.
3. Widget events are translated into calls to `limitora`'s public API.
4. `limitora` executes provider requests, rate limiting, and auth.
5. Results flow back to the widget for display.

## Layers

| Layer | Responsibility | What it must NOT do |
|-------|----------------|---------------------|
| Widget layout | Define native YASB components, labels, and styling | Import provider SDKs or manage tokens |
| Popup | Expanded native view with tabs, All view, provider views, quota rows, states, and alerts | Call providers directly or store credentials |
| Backend bridge | Convert YASB lifecycle events into Limitora calls | Duplicate auth, rate limiting, or endpoint logic |
| Settings | Surface widget configuration to the YASB config file | Store credentials |
| `limitora` | All provider interaction, request lifecycle, and rate limiting | Import YASB or any UI framework |

## Mandated rules

- `yasb_limitora` imports `limitora` only.
- `limitora` never imports YASB, PyQt, Waybar, or any UI integration.
- HTML/CSS reference exports become native YASB components; no embedded webview.
- No auth, endpoint, provider, or network logic is duplicated in this repository.
- No tokens, cookies, sessions, credentials, or provider cache data are stored here.
- The compact widget and popup must use native YASB components.
- Decorative reference pieces (fake desktop, code editor, demo scene) are not implemented.

## MVP constraints

- No provider network code.
- No auth, token, session, or credential handling.
- No release automation, CI, or tests in this phase.
- No PyQt, Qtile, or system-tray code outside what YASB itself requires.

## Open questions

- Does YASB expect an in-process Python module, an external command, or a socket-based widget?
- What is the official lifecycle (init, update, destroy) for a YASB widget?
- How should Limitora's configuration be exposed inside YASB's config file?
