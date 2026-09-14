# Release Distribution Specification

## Purpose

Define the public identity, supported artifacts, release evidence, and promotion rules for the first public `yasb-limitora` release.

## Requirements

### Requirement: 0.2.0 is the first public release identity

The product, runtime, installer, release metadata, release notes, and migration guidance MUST identify `0.2.0` consistently as the first public release. The project MUST NOT publish a retroactive `0.1.0` release, tag, or compatibility promise, and MUST NOT publish a public `-rc` version or tag.

#### Scenario: First-public release is identified

- GIVEN a user or release reviewer examines an active version or release surface
- WHEN the 0.2.0 release is prepared
- THEN it identifies `0.2.0` as the first public release
- AND no active public release surface presents `0.1.0` as a released version

#### Scenario: Internal RC does not become a public version

- GIVEN a final-version candidate is undergoing internal RC validation
- WHEN release metadata and tags are published
- THEN the candidate remains an internal workflow state
- AND no public `-rc` version or tag is created

### Requirement: The release migration documents the sole current JSON contract

Release notes and migration guidance MUST state that the selector-free current JSON document is the sole supported output and MUST explain the #137 contract break, including removal of the root `version` field and the removed version-selection surface. The release MUST NOT introduce a compatibility selector, v1 fallback, or second JSON contract.

#### Scenario: Existing consumer receives migration guidance

- GIVEN a consumer relied on the former root `version` field or version-selection surface
- WHEN the consumer reads the 0.2.0 release notes and migration guidance
- THEN the removed surface and its incompatibility are stated plainly
- AND the current JSON document without the root `version` field is identified as the migration target

### Requirement: The supported public artifact has one distribution form

The supported public product artifact MUST be a per-user `setup.exe` produced with Inno Setup. The internal frozen runtime candidate MUST use PyInstaller onedir as a packaging input and verification subject, but the onedir bundle MUST NOT be presented as a second supported public distribution form. A portable ZIP MUST NOT be published or supported as an alternative product artifact.

#### Scenario: Public artifact set is reviewed

- GIVEN the release artifacts are presented to a user
- WHEN the supported download and its packaging inputs are reviewed
- THEN exactly the per-user Inno Setup `setup.exe` is identified as the supported public product artifact
- AND the PyInstaller onedir bundle is identified only as an internal input
- AND no portable ZIP is presented as supported

### Requirement: Release artifacts have reviewable integrity and custody evidence

The release process MUST retain a manifest, exact SHA-256 values, an SBOM, and provenance or attestation for each published product artifact. The 0.2.0 release materials MUST disclose that the artifact is unsigned and explain the resulting SmartScreen implications without implying code-signing assurance. Publication MUST use the exact bytes that passed candidate validation.

#### Scenario: Unsigned artifact evidence is available

- GIVEN a reviewer inspects the 0.2.0 release materials
- WHEN artifact trust and integrity are evaluated
- THEN unsigned status and SmartScreen implications are disclosed
- AND the manifest, SHA-256 values, SBOM, and provenance or attestation are available

#### Scenario: Validated candidate bytes are promoted

- GIVEN a final-version candidate has passed the required release gates
- WHEN the final release is published
- THEN each published artifact is byte-identical to the validated candidate
- AND its published hash matches the validated hash

### Requirement: Release publication is blocked by failed required evidence

The release MUST NOT publish a candidate that fails exact-hash validation, applicable native or source verification, installer lifecycle verification, the release-target YASB path-with-spaces gate, security evidence, or the required provider evidence. A missing external gate MUST be reported as unrun rather than treated as a pass.

#### Scenario: Failed or missing gate prevents publication

- GIVEN a required release gate fails or an external gate was not run
- WHEN publication readiness is evaluated
- THEN the candidate is rejected or quarantined
- AND it is not published as a public RC or final release
- AND the missing evidence is recorded as outstanding when applicable
