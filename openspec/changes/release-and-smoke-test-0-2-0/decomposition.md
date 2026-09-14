# R11 completion decomposition

**Status:** Approved as the R11 stabilization and completion routing baseline. Implementation, tag, release, and publication remain separately gated.

## Decision

R11 remains the roadmap-level release outcome. It is no longer treated as one implementation-sized SDD change.

The remaining work uses three routes:

1. **Small SDD → TDD implementation → RDD** when product, architecture, authority, or evidence design is still ambiguous.
2. **Direct TDD implementation → RDD** when the existing R11 proposal, specs, and design already define the behavior and rollback boundary.
3. **Verification-only evidence gate** when the work proves an exact candidate but does not implement product behavior.

This document is a routing and decomposition record. It does not authorize implementation, enable RDD, modify GitHub policy, create a tag, or publish a release.

## Preserved baseline

The current change remains the historical and architectural baseline:

- Change: `release-and-smoke-test-0-2-0`
- Roadmap outcome: `docs/roadmap.md` R11
- Existing artifacts: `proposal.md`, `design.md`, `tasks.md`, five delta specs, `apply-progress.md`, and `verify-report.md`

The following completed work is preserved and must not be reopened without a concrete defect:

- S01, S02a, S02b, S03, S04a, S04c, S05, S06, S07, S08, and S10
- G1 pre-install evacuation proof
- G2a feasibility/selection proof with M6 selected

S03 already owns immutable manifest, hashes, sizes, build identity, and the separation between build identity and acceptance. The future integrity work extends the candidate pipeline; it does not redesign or replace S03.

## Routing rules

Use the smallest route that preserves correctness.

| Question | Route |
| --- | --- |
| Is a product, architecture, authority, or evidence decision unresolved? | Small SDD |
| Are behavior, acceptance scenarios, rollback, and owned surfaces already explicit? | Direct TDD + RDD |
| Does the unit only execute a native/manual/external proof? | Verification-only |
| Did a direct unit discover a genuine decision gap? | Stop and promote that gap to a small SDD |
| Does a unit contain independent invariants or rollback boundaries? | Split before implementation |

Complexity and risk alone do not select SDD. RDD is candidate-bound review evidence; it does not replace planning, implementation, tests, native proof, or human release authority.

### Work-unit size

- Prefer approximately 100–250 changed lines per direct implementation unit.
- Treat 400 additions plus deletions as a hard review boundary, not a target.
- Keep production behavior and its tests in the same unit.
- Give each unit one primary invariant, one rollback boundary, and an independently reviewable result.
- Do not create ceremonial SDDs for individual files, helpers, warnings, or documentation lines.

## Small SDD route

Three small SDDs are initially justified by the current evidence. No fourth SDD is planned unless a direct unit exposes a concrete unresolved product, architecture, authority, or evidence decision.

### SDD-C1 — Candidate build and custody

**Outcome:** define the CI architecture that builds one exact final-version candidate and retains it under an explicit immutable identity.

**Resolved product decisions:**

- Start the build only with `workflow_dispatch` and an exact commit SHA.
- Do not create the final tag before candidate acceptance.
- Use GitHub Artifacts v4 with explicit artifact identity.
- Retain candidate artifacts for 90 days.
- Promotion must consume the retained bytes without rebuild or repack.
- A public RC tag or version is forbidden.

**The SDD must specify:**

- Workflow inputs and exact commit validation.
- Job ordering and failure boundaries.
- Artifact names, IDs, contents, and upload/download contracts.
- Official action versions and immutable full-commit-SHA pins for upload, download, and every other action used.
- Rerun and concurrency semantics.
- Quarantine behavior for incomplete or invalid builds.
- Rejection when an artifact ID is missing, expired, or deleted; lost candidate bytes require a new candidate identity and must never be rebuilt under the old identity.
- Minimum GitHub permissions.
- The evidence that proves retained candidate identity for G2b.

**Out of scope:** acceptance status, public tags, GitHub Release creation, and publication.

### SDD-C2 — Candidate integrity and attestation

**Outcome:** define reproducible SBOM generation and attestations that bind the exact installer and release manifest without mixing identity with acceptance.

**Resolved product decisions:**

- Generate reproducible CycloneDX JSON from the exact Python environment used to build the candidate.
- Use `actions/attest@v4`.
- Emit build provenance for `setup.exe`.
- Emit an SBOM attestation binding that same installer to the CycloneDX document.
- Attest the release manifest.
- Bind auxiliary artifacts through SHA-256 entries in the manifest instead of attesting every attachment independently.
- Keep `rc-manifest.json` free of gate, approval, acceptance, and post-publication state.

**The SDD must specify:**

- The reproducible CycloneDX command and normalized inputs.
- Official publisher/version validation for CycloneDX and `actions/attest@v4`, followed by immutable full-commit-SHA pins for the workflow implementation.
- Exact attestation subjects and predicates.
- Ordering between candidate build, SBOM, manifest, and attestations.
- Manifest/SBOM/setup binding validation.
- Fail-closed behavior for missing or mismatched integrity material.
- Required `id-token`, attestation, and repository permissions.

**Out of scope:** reopening S03, generating `rc-acceptance.json`, or granting publication authority.

### SDD-C3 — Release promotion authority

**Outcome:** define who may promote an accepted candidate and how a protected workflow creates the final tag and GitHub Release exactly once.

**Resolved product decisions:**

- Use a protected GitHub Environment.
- Require one human reviewer.
- Use least-privilege permissions.
- Require explicit build-run and acceptance-run identities.
- Let the protected workflow create the final tag and GitHub Release.
- Publish only the exact accepted candidate bytes.
- Never rebuild or repack during promotion.

**The SDD must specify:**

- Authorized trigger and actor boundaries.
- Exact tag name and commit/tag validation.
- GitHub token permissions and environment protection assumptions.
- Official action versions and immutable full-commit-SHA pins for every promotion action.
- Idempotency when a tag or release already exists.
- Attachment ordering and partial-publication handling.
- Safe retries and duplicate-promotion refusal.
- Incident handoff when creation or attachment outcome is uncertain.

**Out of scope:** treating review evidence as delivery authority or allowing post-publication smoke to rewrite pre-publication acceptance.

## Direct TDD + RDD route

These units are already specified by the parent R11 artifacts or become direct after one of the three small SDDs resolves its contract.

### Configuration completion

| ID | Small unit | Primary invariant | Dependency |
| --- | --- | --- | --- |
| D01 | Config lock and snapshot | One writer owns one safe, runtime-valid snapshot | S08 |
| D02 | Owned-field merge and atomic write | Preserve unowned fields and atomically replace only a valid result | D01 |
| D03 | Config rollback and reread verification | Restore prior bytes or remove only a failed new creation | D02 |
| D04 | Explicit provider selection state | Only explicit selection changes `enabled`; missing requirements only warn | D02 |

Together these replace oversized S09. Each unit must retain the S08 reject-and-preserve boundary.

### Installer completion

| ID | Small unit | Primary invariant | Dependency |
| --- | --- | --- | --- |
| D05 | Inno build driver | Validate exact inputs, version defines, and unique setup output | S10 |
| D06 | Initial install and upgrade transaction | Stage, verify, evacuate, register, and commit in the proven order | D05, G1, S04c |
| D07 | Installer rollback | Restore coherent program and registry identity after induced failure | D06 |
| D08 | Installer assist bridge | Exchange bounded nonce-derived request/result data and clean it exactly | D01–D04, D06, S05–S08 |
| D09 | Manual-close and uninstall lifecycle | Never control YASB; preserve state unless cleanup is explicitly selected | D06–D08 |

Together these replace oversized S11. G1 and M6 are fixed inputs, not new design choices.

### Candidate pipeline implementation

| ID | Small unit | Primary invariant | Dependency |
| --- | --- | --- | --- |
| D10 | Candidate build workflow | Build the exact commit and retain one complete candidate | SDD-C1, D05–D09 |
| D11 | Candidate CI verification and secret scan | Reject candidates without required source, full, native, and secret checks | D10 |
| D12 | SBOM and attestation implementation | Materialize the exact integrity contract without changing candidate bytes | SDD-C2, D10 |
| D13 | Candidate custody validation | Prove explicit artifact identity, retention, and no-rebuild consumption | D10–D12 |

These replace the implementation portion of oversized S12.

### Smoke and acceptance material

| ID | Small unit | Primary invariant | Dependency |
| --- | --- | --- | --- |
| D14 | Smoke matrix contract | Every gate is explicit `pass`, `fail`, or `unrun (external)` with owner and evidence | Parent R11 design §8.1 |
| D15 | Acceptance schema and gate set | Accept only the exact pre-publication gates and legal state/reason combinations | D14 |
| D16 | Acceptance binding rules | Bind explicit runs, manifest digest, artifact hashes, evidence, and G2b | D15 |
| D17 | Deterministic acceptance generator | Emit only separate `rc-acceptance.json` without mutating candidate identity | D16 |
| D18 | Acceptance workflow | Select explicit retained inputs and emit only the separately custodied ledger | D17 |

D14 extracts the structural portion of S13. D15–D18 replace S14 and the acceptance half of S15. Their code and workflow definitions may be implemented and tested with fixtures before external evidence passes; executing D18 to create the real acceptance ledger remains blocked until V01–V04 pass for the exact retained candidate.

### Publication implementation

| ID | Small unit | Primary invariant | Dependency |
| --- | --- | --- | --- |
| D19 | Publish input verification | Recompute and verify all candidate, manifest, SBOM, attestation, and ledger bindings | D18 |
| D20 | Protected promotion workflow | Create the final tag/release and attach exact accepted bytes once | SDD-C3, D19 |

D19 and D20 replace the publication half of S15. They may be implemented and tested with fixtures before release readiness passes. Executing D20 against GitHub remains blocked until V05 passes and a separate human-controlled delivery decision authorizes promotion.

### Small closeout updates

Bounded documentation or index updates discovered during readiness and post-release verification may use direct work plus proportionate review. They must not rewrite candidate identity, acceptance, or historical evidence.

## Verification-only route

| ID | Evidence unit | Required result | Dependency |
| --- | --- | --- | --- |
| V01 | G2b installed-candidate proof | Exact retained setup is installed and proves real YASB M6/no-PATH behavior with bound identity | D13 |
| V02 | Pre-publication runtime proof | Frozen CLI/helper, deadlines, Job containment, streams, and no-orphan behavior pass | D13 |
| V03 | Pre-publication installer lifecycle proof | Install, reinstall, upgrade, rollback, uninstall, PATH, and state boundaries pass | D09, D13 |
| V04 | Configuration and provider proof | `.env`, config wizard, enabled state, representative live provider, and secret evidence pass | D04, D08, D13 |
| V05 | Release readiness handoff | All required gates and bindings pass; any `fail` or `unrun` blocks publication | D18 executed for the exact candidate, V01–V04 |
| V06 | Post-publication closeout | Published bytes pass clean-machine smoke; failure keeps R11 open for incident handling | D20 executed and published bytes available |

Verification-only work never invents RED/GREEN evidence, edits product code to make a gate pass, or treats a synthetic proxy as native/runtime proof.

## Dependency paths

Construction readiness and release admission are intentionally separate. Passing an external gate is not required to implement and fixture-test code that will later enforce that gate.

### Construction dependency path

```text
Config:
  preserved baseline → D01 → D02 → {D03, D04}

Installer:
  preserved baseline → D05 → D06 → D07
  {D01–D04, D06} → D08
  {D07, D08} → D09

Candidate:
  {SDD-C1, SDD-C2, D05–D09} → D10 → D11 → D12 → D13

Acceptance code and workflow definitions:
  parent R11 design §8.1 → D14 → D15 → D16 → D17 → D18

Publication code and workflow definitions:
  {SDD-C3, D18} → D19 → D20
```

### Release-admission path

```text
D13 exact retained candidate
        │
        ├── V01 G2b installed-candidate proof
        ├── V02 runtime proof
        ├── V03 installer lifecycle proof
        └── V04 configuration/provider proof
                    │
                    ▼
             all V01–V04 pass
                    │
                    ▼
      execute D18 for the exact candidate
                    │
                    ▼
       retained acceptance artifact exists
                    │
                    ▼
                   V05
                    │
                    ▼
       explicit human promotion decision
                    │
                    ▼
              execute D20
                    │
                    ▼
                   V06
```

The three SDDs may be planned before their implementation dependencies are ready. Code and workflows may be implemented with fixtures according to the construction path, while real acceptance and publication remain blocked by the release-admission path.

## Parent-change migration rules

Before implementation begins:

1. Keep the existing proposal, specs, design, progress, and evidence history.
2. Add links from the parent change to the three child SDDs when those changes are created.
3. Replace each pending parent task only with an explicit route/mapping reference; do not mark moved work complete.
4. Never duplicate the explicit completed baseline listed above into child apply scopes.
5. Keep parent R11 open as the aggregate tracker until D20 and V06 finish.
6. Perform one final requirement-to-evidence reconciliation before closing or archiving the parent.

## Delivery and authority boundaries

- RDD is currently not enabled by this planning decision.
- Before the first direct implementation unit, inspect the user-owned RDD/review mode. If it is enabled, follow the candidate-bound RDD route. If it remains disabled or is unavailable, stop for an explicit choice to enable it or proceed under ordinary repository review policy; never claim or imply that an RDD receipt exists.
- A future RDD receipt is review evidence for one exact candidate; it never authorizes commit, tag, release, or publication.
- The protected-environment decision does not itself configure GitHub or grant reviewer authority.
- `workflow_dispatch` planning does not authorize a workflow run.
- G2b and all external gates remain `fail` or `unrun (external)` until their exact evidence exists.
- Post-publication smoke cannot retroactively change `rc-manifest.json` or `rc-acceptance.json`.

## Next gated action

Stabilize the completed R11 baseline through the approved feature-branch PR chain, then update the parent task map without changing completed work. The first dependency-ready future implementation unit is **D01 — Config lock and snapshot**; planning-only work may instead begin with **SDD-C1 — Candidate build and custody** if explicitly selected in a later session. Do not create every child artifact at once; later SDDs should incorporate evidence learned from earlier units without changing the preserved R11 outcome.
