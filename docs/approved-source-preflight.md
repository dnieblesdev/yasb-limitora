# Approved-source preflight

Fail-closed import-identity tooling for a candidate checkout. Optional development
tooling; the widget does not depend on it.

## Purpose

Before any separately authorized native proof, establish that the Python modules that
would run come from the expected approved source tree and not from an unexpected
checkout, a stray editable install, or something else on the import path.

## The trust boundary

An earlier design anchored the approved identity inside the very repository being
validated: the tool read its own clone's Git objects and compared against a revision
constant that shipped with the candidate. A candidate could therefore certify itself,
because nothing distinguished "this candidate matches the approval" from "this candidate
says it matches the approval".

That circularity is removed by separating three roles:

| Role | Who provides it |
|---|---|
| Anchor content | produced by `approved_source_anchor.py` from a pinned Git revision |
| Anchor authenticity | a digest published out of band (release notes, ticket, CI artifact) |
| Candidate | the checkout being validated, which supplies nothing about its own identity |

`approved_source_preflight.py` accepts a candidate root, an anchor file, and the pinned
digest. It refuses an anchor that lives inside the candidate root, and it refuses an
anchor whose bytes do not hash to the pinned digest. Authority travels separately from
the artifact under test; the candidate has no vote.

This is a trust *seam*, not a trust anchor service. Publishing the digest is the
operator's or release process's responsibility. If the digest is distributed through the
candidate itself, the circularity returns.

## Usage

Freeze an anchor from a pinned revision, then publish its digest out of band:

```
python -B -I -E scripts/approved_source_anchor.py \
    --repo <repo> --revision <40-hex-or-ref> --version <version> \
    --output anchor.json
# then copy the anchor_sha256 value into your release notes or ticket
```

Validate a candidate from a dedicated, isolated interpreter:

```
<dedicated-python> -B -I -E scripts/approved_source_preflight.py \
    --candidate-root <candidate> --anchor <anchor.json> \
    --anchor-sha256 <pinned digest> --expected-executable <dedicated-python>
```

Exit `0` means `PASS` with `IDENTITY_VERIFIED` and sanitized evidence. Exit `1` means
`FAIL` with a fixed reason code. Neither path prints paths, environment values,
exception text, provider data or credentials.

## Fail-closed reasons

| Reason | Meaning |
|---|---|
| `ANCHOR_INSIDE_CANDIDATE` | the anchor is shipped by the artifact it is meant to judge |
| `ANCHOR_DIGEST_MISMATCH` | the anchor is not the one whose digest was pinned |
| `ANCHOR_NONCANONICAL` | the bytes do not match the digest's canonical encoding |
| `ANCHOR_INVALID` | malformed anchor, or a path outside the package, or a missing required module |
| `HASH_MISMATCH` | an anchored module differs from its approved digest |
| `MISSING_MODULE` | an anchored module is absent from the candidate |
| `CANDIDATE_EXTRA_MODULE` | the candidate has a module the approval never knew |
| `ORIGIN_MISMATCH` / `ORIGIN_UNKNOWN` | a module resolves outside the candidate package, or not as a source file |
| `UNEXPECTED_EDITABLE` | an unrelated distribution is installed as an editable checkout |
| `EDITABLE_MISMATCH` | the candidate's editable install points at a different root |
| `VERSION_MISMATCH` | installed version differs from the anchor |
| `DISTRIBUTION_MISMATCH` | not exactly one candidate distribution is installed |
| `FLAGS_INVALID` / `VENV_REQUIRED` / `SYSTEM_SITE_FORBIDDEN` / `EXECUTABLE_MISMATCH` | the interpreter is not the dedicated isolated one |
| `METADATA_UNKNOWN` / `IDENTITY_UNKNOWN` / `CLI_INVALID` | identity could not be established |

## Known limits

- **Line endings.** Anchored hashes come from Git blobs, which store LF. A working tree
  with `core.autocrlf` enabled checks text files out with CRLF, so the comparison
  normalises CRLF to LF before hashing. The documented consequence: a change that only
  alters line endings is not treated as a content divergence.
- **Not an execution check.** The preflight inspects specs, hashes and metadata. It does
  not import the provider modules, call Limitora, start a helper, or prove that a native
  run would behave. It is a gate before such a run, never a substitute for it.
- **The digest channel is out of scope.** The tool cannot verify how the pinned digest
  reached the operator; that step is process, not code.
- **No frozen-bundle proof.** `frozen` is reported as observed, but a frozen deployment
  is a different identity model and is not covered here.
