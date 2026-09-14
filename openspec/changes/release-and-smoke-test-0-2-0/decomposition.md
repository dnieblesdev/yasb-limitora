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
| D01a1 | Guard domain and real deadline | Context-managed primary Guard lease keyed by exact fixed config.json path; retry Guard's 250ms waits against one 5-second DeadlineContext; guard_wait_timeout remains contention and never activates fallback | S08 |
| D01a2a | Marker codec | Canonical UTF-8 JSON marker `{"pid": <DWORD 1..4294967295>, "token": <1..64 lowercase hex>, "version": 1}` with sorted keys, no whitespace, 256-byte preparse max; one sanitized validation error for duplicate/extra/missing/bool/invalid/uppercase/nonhex/oversize/non-object; deterministic roundtrip; zero file I/O | D01a1 |
| D01a2b | Win32 process identity | OpenProcess/GetProcessTimes creation token via reusable safe primitive; CloseHandle failure/unavailability is unprovable, not a usable token; no os.kill/process control | D01a2a |
| D01a3a1 | Safe marker create and identity | Verified parent hold/non-reparse/final identity; correct Win32 CreateFileW CREATE_NEW handle with explicit DELETE+read/write/attributes access, FILE_SHARE_DELETE compatibility, and NULL template; verify leaf final path, reparse status, regular-file status, and handle identity after create; reuse repo-validated FILETIME/BY_HANDLE_FILE_INFORMATION/native helpers; at least one real Windows test — fakes cannot redefine API semantics; real native create/close proof; no IO, no delete, no Guard/reclaim/deadline policy | D01a2b |
| D01a3a2 | Safe marker IO and disposition delete | Bounded ≤256 read through same acquired handle; partial/full write+FlushFileBuffers through same acquired handle; identity re-open before delete; handle disposition delete and successor/no-residue proof; low-level sanitized errors; no Guard/reclaim/deadline policy | D01a3a1 |
| D01a3b | Fallback policy and integration | Private typed ConfigLease unifies mutex/marker ownership; one shared DeadlineContext for D01a3b and D01b; fallback only on guard_acquisition_failed; retry/contention; decode/owner predicate; conservative busy rules; reclaim only for ProcessTokenMissing or returned token mismatch; cleanup outcome maps config-lock-release-failed | D01a3a2 |
| D01b | Immutable config snapshot and assist wiring | Handle-bound fstat read, exactly-once validation under owned lease, deeply immutable snapshot, and setup-assist wiring | D01a3b |
| D02 | Owned-field merge and atomic write | Preserve unowned fields and atomically replace only a valid result | D01b |
| D03 | Config rollback and reread verification | Restore prior bytes or remove only a failed new creation | D02 |
| D04 | Explicit provider selection state | Only explicit selection changes `enabled`; missing requirements only warn | D02 |

Together these replace oversized S09. Each unit must retain the S08 reject-and-preserve boundary.

> **D01 split note.** The original combined D01 candidate (evidence `sha256:115ba0a3f1bbde7832d80d544939877db44a24df0845d928de09c67c36548deb`) was rejected after native failure settlement/reset and rolled back to the clean baseline. It supplies no passing evidence. The maintainer authorized splitting D01 into two cohesive review/implementation units — D01a (lock ownership primitive, ≤300 lines, one rollback boundary) and D01b (immutable snapshot and assist wiring, ≤350 lines, one rollback boundary) — to keep each unit within a focused review scope. D02 depends on D01b and must consume the snapshot while the D01a lease remains owned.
>
> **D01a finer split.** The D01a candidate (evidence `sha256:f2d6e7e39089a09d284da0355fdf39db5be4c2acd2c98a527d5dd0f488e14fb9`) was rejected and rolled back with no passing evidence. The maintainer authorized splitting D01a into three sequential bounded sub-units — D01a1 (guard domain and real deadline, ≤180 lines), D01a2 (process identity and marker codec, ≤220 lines), and D01a3 (file fallback acquisition and cleanup, ≤280 lines) — while keeping D01a as the umbrella name. D01b depends on D01a3. D02 remains dependent on D01b.
>
> **D01a2 budget raised.** The D01a2 candidate (evidence `sha256:15a3e99d15c8e6d06d899dfbb60bce047e85a73a48355722bbe52b319f0d3bde`) produced green behavioral tests but exceeded the 220-line budget at 247 code+test lines, left the version schema undefined, had CloseHandle ambiguity, an incorrect PID upper bound, and exception-handling inconsistency. It supplies no passing evidence. The maintainer raised the D01a2 budget to ≤280 lines and defined the exact canonical marker schema to resolve the ambiguity.
>
> **D01a2 further split.** After the budget raise to ≤280, a subsequent D01a2 candidate (evidence `sha256:4405cb265935e8dffe8d56f96f597e7aca8e730f9d1bcca242121b0c9f0f1c6b`) produced a dirty working state with semantically passing marker+Win32 identity but exceeded the review budget. The maintainer split D01a2 into D01a2a (marker codec, ≤260 lines) and D01a2b (Win32 process identity, ≤220 lines, depends D01a2a). D01a3 depends on D01a2b. No passing evidence is inherited by D01a2a or D01a2b.
>
> **D01a2b budget raised.** The D01a2b candidate (evidence `sha256:9336fb10360083509dbee533ebb2ea1385d98186f04abd4ee605320a499025f5`) was rejected with no passing evidence. Rejection reasons: real PID4 ERROR_ACCESS_DENIED was falsely missing; last error unused; API/query/CloseHandle exceptions escaped; close could leak; padded token diverged from cache pattern. The maintainer raised the D01a2b budget to ≤280 lines and pinned the correction contract: only OpenProcess error87 missing is a valid refusal; all other ambiguity is unprovable; use unpadded lowercase hex matching `cache.py`; token is emitted only after successful close; invalid caller PID is unprovable/refused rather than proof the OS process is missing. D01a3 dependency and cohesive Win32 identity scope are preserved.
>
> **D01a3 pre-implementation decisions.** The maintainer recorded the following explicit decisions from pre-implementation exploration for D01a3: a private typed `ConfigLease` unifies mutex (primary) and marker (fallback) ownership, and one shared `DeadlineContext` serves both D01a3 and D01b; the fallback uses Win32 `CreateFileW` with `CREATE_NEW` disposition (the OS-native exclusive-create equivalent of `O_CREAT|O_EXCL`) requesting explicit `DELETE` + read/write + attributes access and `FILE_SHARE_DELETE` compatibility so the same verified handle can be disposition-deleted safely, under a held verified non-reparse parent, then immediately verifies the leaf's final path, reparse status, regular-file status, and handle identity, writing and flushing and fsyncing through the same acquired handle; reuse and cross-check of repo-validated `FILETIME`/`BY_HANDLE_FILE_INFORMATION`/native helpers from `_native_state_cleanup.py` is required — fakes cannot redefine API semantics; at least one real Windows test is required; empty, partial, malformed, oversize, or unverifiable marker content and own-process markers refuse conservatively as sanitized `config-lock-busy` and are never reclaimed (manual cleanup may be needed after a pre-write crash); only `ProcessTokenMissing` or a returned token mismatch permits reclaim, while `ProcessTokenUnprovable` or an equal token refuses; handle-derived identity and identity re-open before delete ensure handle-bound deletion never removes a successor; cleanup failure maps to `config-lock-release-failed`; one shared five-second deadline is checked on every Guard and marker retry; there is no fallback on `guard_wait_timeout`; the parent directory is fixed and existing with no creation. File targets are `_config_lock.py` and `test_config_lock.py`. Budget remains ≤280 lines.
>
> **D01a3 split.** The D01a3 candidate (evidence `sha256:cdfae75a600fc33e170ed1e6d2b5f90b5cacec6e0fc9b99cce071913618e824d`) was rejected with no passing evidence. Rejection reasons: 294/280 lines before adequate tests, one focused failure, no full/native/Ruff validation. The maintainer split D01a3 into D01a3a (safe marker primitives, ≤280 lines) and D01a3b (fallback policy and integration, ≤280 lines, depends D01a3a). D01b depends on D01a3b. No passing evidence is inherited by D01a3a or D01a3b.
>
> **D01a3a correction after failed evidence.** The D01a3a candidate (evidence `sha256:d9ad0c388c0603cbd6e1548e01c63e2b82b64d89654ae1e2304d44c86299213c`) was rejected with no passing evidence. The maintainer corrects the exclusive-create mechanism: the CRT `O_CREAT|O_EXCL` create-then-verify approach is replaced with Win32 `CreateFileW` `CREATE_NEW` as the OS-native exclusive-create equivalent, requesting explicit `DELETE` + read/write + attributes access and `FILE_SHARE_DELETE` compatibility so the same verified handle can be disposition-deleted safely. Held verified parent and final-path/regular/non-reparse/identity verification are preserved. The implementation must reuse and cross-check repo-validated `FILETIME`/`BY_HANDLE_FILE_INFORMATION`/native helpers from `_native_state_cleanup.py` and include at least one real Windows test; fakes cannot redefine API semantics. Rejected defects recorded: malformed 56-byte ABI `BY_HANDLE_FILE_INFORMATION` struct, `hTemplateFile` misuse (non-NULL template on create), missing `DELETE` access or `FILE_SHARE_DELETE` incompatibility preventing safe disposition-delete through the verified handle, no final-path comparison after create, partial writes without flush+fsync, handle leaks on error paths, and no real Windows test. D01a3a budget remains ≤280 lines; D01a3b is unchanged; tasks remain unchecked. No source, tests, progress, or delivery.
>
> **D01a3a split after failed budget evidence.** The corrected D01a3a candidate (evidence `sha256:df157a419b096c9ab12a04b5c23295e3d605355c183c6b105a9303d52863382d`) passed focused 45, native 11, full 898+4skip, and Ruff but exceeded the ≤280 budget at 563 lines (228 code, 335 tests). It supplies no passing evidence. The maintainer split D01a3a into two sequential bounded sub-units — D01a3a1 (safe marker create and identity, ≤280 lines) and D01a3a2 (safe marker IO and disposition delete, ≤280 lines, depends D01a3a1). D01a3a1 owns verified parent hold, correct Win32 CREATE_NEW handle with explicit access/share/NULL template, final/reparse/regular and handle identity, and real native create/close proof; no IO, no delete. D01a3a2 owns bounded ≤256 read, partial/full write+FlushFileBuffers, identity re-open, handle disposition delete and successor/no-residue proof; no Guard/policy. D01a3b now depends on D01a3a2. D01b depends on D01a3b. The CREATE_NEW decision is preserved. No passing evidence is inherited by D01a3a1 or D01a3a2. Tasks remain unchecked. No source, tests, progress, or delivery.
>
> **D01a3a1 completion.** Premature candidate `sha256:528e6d1e3d9acb183520a4a3d604e41476a86b9b85a823cf0ddd56683db375b2` was rejected for parent sharing, incomplete identity/final-path enforcement, and cleanup defects. Candidate `sha256:f1110be2ba907c2682ce71c752f455c6870596b47949ec84685af8c42e2f72aa` passed independent verification but RDD found that the verified parent handle was closed before marker creation. Final candidate `sha256:7d2e010b55fd2df41300b1ff36d8938101048ad2a47d4e0fd848c92b1ef99fcd` retains a typed `ParentHold` across `CREATE_NEW`: exactly 280/280 source+test lines; focused 35, native 11, full 888+4 skipped, Ruff clean, and real Windows rename-denial/create/identity/final/close/no-residue proof. RDD lineage `review-5177142dc314fb64` approved corrected target `sha256:ddbd3974475f32b30b1695d00404313a58c6b33ef37780b47ffa379cb19f0377`. D01a3a1 is complete; later tasks remain unchecked.

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
  preserved baseline → D01a1 → D01a2a → D01a2b → D01a3a1 → D01a3a2 → D01a3b → D01b → D02 → {D03, D04}

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

Stabilize the completed R11 baseline through the approved feature-branch PR chain, then update the parent task map without changing completed work. The first dependency-ready future implementation unit is **D01a1 — Guard domain and real deadline**; planning-only work may instead begin with **SDD-C1 — Candidate build and custody** if explicitly selected in a later session. Do not create every child artifact at once; later SDDs should incorporate evidence learned from earlier units without changing the preserved R11 outcome.
