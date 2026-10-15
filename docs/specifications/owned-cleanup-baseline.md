# Owned-cleanup baseline contract

`proof-harness/contracts/owned-cleanup-baseline.ps1` is a pure PowerShell 5.1
contract. Dot-sourcing it emits nothing. It does not collect observations, read
registry/filesystem state, authorize ownership, or invoke historical consumers.

## API and inputs

- `Get-OwnedCleanupPathOwnershipFacts -PathValue <object> -RecordValue <object>
  -AppElement <string>` returns one ordered seven-field ownership object.
- `Assert-OwnedCleanupBaseline -Capture <object>` retains the runtime predicate.
- `Assert-OwnedCleanupEvidenceBaseline -Capture <object>` retains the stricter
  offline predicate. Success emits nothing; failure throws the historical message.

Value observations have `present`, `kind`, and `value` fields. The caller supplies
an already-canonical app element and validated observations. Missing observations
are not proof of absence. These functions do not validate evidence provenance or
replace full capture-schema validation.

The ownership fields are `recordPresent`, `recordValid`, `recordPathMatches`,
`recordTypeMatches`, `recordElementMatchesExpected`, `appElementCount`, and
`appElementIsFinal`. PATH membership is independent of record validity/presence;
membership does not imply ownership. Raw PATH and record values are not returned.

PATH is split literally on `;`, preserving empty tokens and duplicate elements.
Membership/element comparison uses OrdinalIgnoreCase; recorded PATH comparison
uses Ordinal. No trimming, normalization, variable expansion, or quote removal
occurs. String/ExpandString map to 1/2 exactly as historically, including the
existing case-sensitive mapping after the case-insensitive allowed-kind check.
PATH and record fields retain the 32768-character limits; the JSON record retains
its 65536-character bound, exact element/path/type fields, and int/long type rule.
The original catch and intermediate fact assignments are intentionally unchanged.

Both guards read appTree.present, stateTree.present, registration.present, and
ownership. The runtime guard casts appElementCount to int. The offline guard does
not cast it and also rejects the five unexpected ownership flags plus
registration.installLocationMatchesExpected and registration.uninstallerMatchesExpected.
Do not merge these predicates or treat the minimal view as a full v1 capture.

## Differential proof and boundaries

Run `python -m pytest -q --strict-markers tests/test_owned_cleanup_baseline_contract.py`
on Windows. The wrapper checks exact exit/stdout/stderr using real PowerShell 5.1.
The PowerShell test embeds only 69 lines of fixed historical pure projection,
helpers, and guards; source-file hashes and a checked UTF-8/LF slice hash identify
its provenance. It is a frozen test oracle, not a second production implementation.
The pre-fix negative control moves only the membership block under record validity.
All seven values and types, guard decisions/messages, and input immutability are
compared across the matrix; both guards are exercised independently.

No registry, VM, installer, jobs, operational manifests, laboratory IO, or historical
build input is needed. The historical C4 v4 run is not the equivalence oracle.
No operational consumer is connected by this extraction.
