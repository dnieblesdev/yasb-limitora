# PATH cleanup: review chain (pending)

This note tracks a proposed, sanitized delivery chain for review. It is not
acceptance of the release or of the underlying changes. Work units are planned
as separate reviewable slices; each unit keeps its code, tests, and supporting
documentation together.

## Tracker status

- Draft / no-merge tracker; publication and merge are not asserted here.
- Related discussion: [issue #62](https://github.com/dnieblesdev/yasb-limitora/issues/62)
  (reference only; this is a nonclosing `Refs #62`).
- The nine units below are planned, not claims that new-source checks passed.
- Review and applicable verification belong to each actual candidate.
- Final product and release acceptance remain pending.

## Planned work units

| Unit | Topic | Depends on |
| --- | --- | --- |
| C1 | Ownership-preserving cleanup | — |
| C2 | PATH updates | C1 |
| C3 | Uninstall consent | C2 |
| C4 | Exact ownership and correction consent | C3 |
| C5 | Installer compatibility and disclosure | C4 |
| C6 | Preview and refusal evidence | C5 |
| C7 | Installer consent arguments | C6 |
| C8 | Registry I/O boundary | C7 |
| C9 | Pytest temporary isolation | C8 |

Review each slice against its clean parent; historical implementation
material does not substitute for reviewing the sanitized candidate.

## Boundaries and acceptance

This tracker is passive review context only. It changes no product runtime or
behavior and introduces no framework, dependency, or CI change. It does not
claim successful checks for the new source units, Windows or C4 acceptance,
I1 nonmutation, or native temporary-directory race custody.

Native and product acceptance remain outstanding. Do not treat this note or
the planned chain as release approval. Record verification and review outcomes
against the actual candidate before making any acceptance decision.
