# yasb-limitora research

This document tracks open investigations and sanitized reference material for
the YASB integration.

## Active investigations

| Topic | Goal | Status |
|-------|------|--------|
| Official YASB widget API | Identify the supported integration model (in-process, external, socket) | open |
| YASB widget lifecycle | Document init, update, destroy, and refresh semantics | open |
| Native component mapping | Map reference HTML/CSS to YASB native widgets | open |
| Limitora public API | Determine how YASB will call Limitora once the core is stable | open |
| Configuration pattern | Decide how Limitora settings appear in YASB config | open |
| Codex via Limitora | Validate end-to-end flow once Limitora implements Codex | pending |
| OpenCode Go via Limitora | Validate end-to-end flow once Limitora implements OpenCode Go | pending |
| Claude via Limitora | Evaluate when Limitora adds support | future |
| Gemini via Limitora | Evaluate when Limitora adds support | future |

## Sanitized samples

All samples checked into this repository must be redacted. Use the file
extensions `*.redacted.json` or `*.redacted.txt`.

Rules for samples:

- Replace tokens, cookies, sessions, and credentials with placeholders.
- Remove hostnames, user IDs, and project IDs unless they are public examples.
- Never include `.env` files, private keys, or unredacted dumps.

## Notes

- Keep provider-specific research in the `limitora` repository, not here.
- Link external references rather than copying sensitive content.
- Record YASB API findings in provider-agnostic terms so they remain valid as
  Limitora evolves.
