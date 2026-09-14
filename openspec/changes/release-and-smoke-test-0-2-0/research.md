# Research: R11 release and smoke test 0.2.0

```yaml
schema: gentle-ai.sdd-research/v1
revision: 1
outcome: blocked
change: release-and-smoke-test-0-2-0
admission:
  admitted: false
  denial: >-
    Research admission is denied because this executor observed no formal
    evidence grants: documentation=[]; open-web=[]. The requested questions
    require external documentation and/or open-web evidence.
observed_evidence_grants:
  documentation: []
  open-web: []
requested_source_classes:
  - documentation
  - open-web
questions:
  - What installer technology and per-user installation conventions are supported and appropriate?
  - What PyInstaller onedir and onefile behaviors affect the frozen helper topology?
  - How does the release-target YASB execute run_cmd, including PATH and paths containing spaces?
  - What signing and SmartScreen policy applies to the release?
  - What artifact integrity and provenance materials are required?
  - What lifecycle semantics apply to install, reinstall, upgrade, repair, rollback, and uninstall?
  - What RC, release, and post-release smoke-test thresholds are required?
sources:
  - id: openspec-explore
    class: repository-artifact
    reference: openspec/changes/release-and-smoke-test-0-2-0/explore.md
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-explore
    class: engram-artifact
    reference: sdd/release-and-smoke-test-0-2-0/explore (observation 2638)
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-bundle-2201
    class: engram-observation
    reference: observation 2201
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-bundle-2114
    class: engram-observation
    reference: observation 2114
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-bundle-2226
    class: engram-observation
    reference: observation 2226
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-bundle-2234
    class: engram-observation
    reference: observation 2234
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-bundle-2266
    class: engram-observation
    reference: observation 2266
    status: read-not-admitted-as-formal-external-evidence
  - id: engram-onefile-2150
    class: engram-observation
    reference: observation 2150
    status: read-not-admitted-as-formal-external-evidence
validated_claims: []
missing_evidence:
  - Current authoritative installer documentation for the candidate technology and per-user, PATH, uninstall, and rollback conventions.
  - Current PyInstaller documentation for onedir/onefile extraction, child-process, and distribution behavior.
  - Current YASB implementation or documentation plus a real target-version path-with-spaces discovery spike.
  - Applicable code-signing and SmartScreen guidance and an approved signing-key custody policy.
  - Authoritative integrity/provenance guidance for checksums, manifests, SBOMs, and attestations.
  - Approved lifecycle and smoke acceptance policy.
unblock:
  - Grant this research executor documentation and/or open-web evidence capability, then collect admissible source records for every required external question.
  - Obtain orchestrator product decisions for artifact set, installer/scope, PATH policy, mutable-state retention, signing policy, and acceptance thresholds.
proposal_ready: false
```

No external evidence claim is validated in this phase. The exploration and recovered Engram observations were read as context only; their external assertions are not re-presented as research findings under this executor's evidence authority.
