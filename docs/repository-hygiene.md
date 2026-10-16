# Minimal sufficient retention

## Policy and scope

Physical artifacts are retained only when their exact bytes are needed to continue selected work or support a concrete non-reproducible claim. Historical provenance, a unique hash, an old run, a manifest or an unmerged working copy is not itself a preservation requirement. No physical backup/archive copies are created.

**Completed safe reduction:** all 27 ordinary sibling registrations were retired; 26 physical roots were removed and one empty, unregistered directory remains process-locked. Eleven controller views remain blocked solely by lifecycle. After retiring the temporary documentation checkout, the original 39 registrations become **12**, and 56 local branches become **37** (20 deleted, one new documentation branch). The two parked units require **zero physical I1/C11 worktrees**.

This local phase covers the original **39 worktrees and 56 local branches**, from `main@bc10800209e394015287397f2d7e197ad806e6ef`. A temporary `chore/minimal-retention` documentation checkout is additional control workspace, not an original retention candidate. Experimental source remains on local parked refs; no push, PR or experimental merge into main is authorized.

## Taxonomy

| Category | Meaning |
|---|---|
| LIVE_WORK_REQUIRED | Selected continuation or active repository control requires retained source/state. This does not automatically require a permanent checkout. |
| KNOWLEDGE_ONLY | A compact conclusion, context, refs, essential inputs, reproduction conditions and limits suffice; physical historical outputs are unnecessary. |
| DELETE_BLOCKED_BY_LIFECYCLE | No technical byte-retention need was established, but disposal of a controller-owned view lacks an authorized lifecycle route. This is not a preservation-value claim. |
| SAFE_DELETE | Required source/knowledge has a stable representation and the exact physical target may be retired within the approved scope. Actual removal is recorded separately. |

The shared `.git` store is operational infrastructure, not a disposable artifact. It holds the parked refs, objects and administration of surviving worktrees. No manual object deletion, authority reset/recovery, force-unlock or controller-token editing is part of this cleanup.

## Selected continuation bytes

### I1 / C10: minimum parked A/B unit

- Base: `f5bd66fa17480fb71c5502e590ea89df329c8e01`; local branch `test/i1-hermetic-ab`.
- Preservation commit: **1845246b0e6bfb588eec02c274446e2a5d0adcd9**.
- Retain only `scripts/i1_hermetic_ab.py`, `tests/test_i1_hermetic_ab.py` and `docs/retained-work/i1.md`. Source/tests are 19,695 original working-copy bytes; note 6,208; total 25,903 before Git EOL normalization.
- No separate fixture bytes are needed: synthetic inputs and namespace generation are in source. Original A is `8f2793246d39d3a09cf7bd39c7853db220f7e0cd`, corrected B is the pinned base above. Their commits and package objects must remain reachable in shared Git; a recorded hash alone is not a GC root.
- Historical result: A raised `OSError`, B returned controlled `path-add/refused/path-access-failed`; one fake read, zero writes and no real registry guards. This is exception containment, not successful PATH modification or proof of the original incident's cause.
- Native probe was NOT EXECUTED/accepted. Its partial implementation could report BLOCKED without `cliInvoked` when a post-call `ProbeRefused` occurred. Preserve this defect and the intended contract in the note, not four declined scaffolding files.
- Reproduction is an explicitly authorized future Windows A/B using immutable A/B source, the embedded synthetic request and a fresh owned namespace. Exact command, dependencies, inputs and limitations are in the parked note. No old environment, namespace, logs, outputs or builds are required. No execution occurred during retention preparation.

### PATH trace / C11: minimum parked diagnostic delta

- Base: `0b04d815a7f0315fb32ca1bff0746066ac06565b`; local branch `chore/c4-path-step-trace`.
- Preservation commit: **ebdd0e75fda5e254def826a39932200edd0c21a9**.
- Retain six source/test files: `packaging/inno/SetupAssistant.isi`, `packaging/inno/yasb-limitora.iss`, `src/yasb_limitora/setup_assist.py`, `src/yasb_limitora/_path_step_trace.py`, `tests/test_inno_script.py`, `tests/test_installer_path_trace.py`, plus `docs/retained-work/path-trace.md`.
- Original full-file source/test payload: 167,821 working-copy bytes; note 5,718; total 173,539 before Git EOL normalization. Canonical Git blobs total **170,322 bytes**, of which **164,604** are source/tests and **5,718** the note. The Git delta is smaller than the full-file payload and does not duplicate an entire worktree/environment. One original incidental indentation-only hunk was retained for source fidelity; it is not a functional enhancement.
- Contract: opt-in/default-off bounded private diagnostics, exclusive creation and sanitized PATH/marker projections, no diagnostic machine-readable stream pollution. The note preserves gate/layout/schema, event/privacy/cap constraints and all required seams.
- Historical focused checks do not establish present runtime acceptance. P3 was blocked by a native-helper full-suite failure without demonstrated candidate/base causality.
- New static observation, not repaired: `YasbPathTraceEnabled` never assigns a true result, so the retained Inno logger remains disabled. This is an intentionally parked prototype, not a promoted fix. Review the design and this defect under fresh authorization before resumption.
- No nonregenerable fixture/environment is required. Reconstruct the pinned base plus the retained delta; agree isolated tests and any native scope separately. Do not reuse consumed VM/registry/installer grants.

For both units, minimal source/test bytes are the continuation record. Both original physical worktrees have been removed. Combined canonical payload is **196,225 bytes across ten files**: **184,299 source/test bytes** and **11,926 note bytes**. This is logical file content, not compressed Git allocation or space reclaimed. No fixture, log, environment, namespace or build copy is retained for these units. No new reason to preserve historical artifact bytes was found. The disabled C11 logger is a newly documented prototype defect, not an additional artifact-retention requirement.

## Sufficient knowledge: priority delivered units

The exact original paths, HEADs and branches are recorded in the inventory below. Ref identifiers provide provenance; notes do not replay old permission or imply runtime certification.

### pre-mapping ProviderError slice

- Conclusion/context: the narrow optional observer records allowlisted provider error type/stage before safe mapping. This does not establish cross-process causality or close historical C6.
- Refs: source `f9505932be7ed3a6a67e0609b399a48706a554c3`, PR #369 / issue #368, merge `6ab4cd0cc17ad419e6201d60df21e3b04cbe7417`.
- Inputs/recipe: use the versioned optional diagnostic contract and focused tests from that source commit; observation is off without its gate. Existing refs/PR plus the code suffice for future authorized reproduction.
- Limits/disposition: no original IPC-cause claim. Publish scripts, issue/PR bodies, RED/GREEN logs and merge-ledger copies need not survive physically. KNOWLEDGE_ONLY, then SAFE_DELETE checkout.

### C7 artifact scanner

- Conclusion/context: scanning must distinguish regular files from directories/unsafe types rather than blindly calling `read_bytes`; local test artifacts can include directories.
- Refs: `f334b27488e772d3f54b884f738a082facd3881b`, PR #357; delivered scanner/tests/docs are in main.
- Inputs/recipe: versioned synthetic scanner cases covering regular files, directory/type handling and read failures; use declared tooling from the chosen ref, not a donor environment.
- Limits/disposition: scanner acceptance is not native IPC causal proof. Preserve the C7->C5->C8 dependency/stop rationale here, not the original full delivery tracker or tmp/build outputs. KNOWLEDGE_ONLY, then SAFE_DELETE checkout.

### C8 bootstrap import evidence

- Conclusion/context: absence of the observer journal cannot prove the helper never started; bootstrap/import failures need a bounded independent breadcrumb. Exception preservation, diagnostic enrichment and native acceptance are separate questions.
- Refs: `386a0542d25c494c8a245188aa0f06fc432c7a7f`, PR #361 / issue #360, merge `539566ad361bad58c39606189c09c95a230f77b7`; canonical implementation/tests are in main.
- Inputs/recipe: use committed bootstrap failure fixtures and stderr/stream contract; independently bind interpreter/import origin if reproducing under authorization.
- Limits/disposition: v2 enrichment was not demonstrated necessary for the minimal exception-fidelity contract. No native propagation/causality claim. Reconciliation conclusion replaces the working tracker and run outputs. KNOWLEDGE_ONLY, then SAFE_DELETE checkout.

### C9 approved-source preflight and C6 re-derivation

- Conclusion/context: approval must be independently anchored, not self-declared by an input manifest. Temporal proximity of events does not by itself prove provider/helper cross-process causal identity.
- Refs: `aec3c0283b85c75da88ae7262bef73c2ea932041`, PR #367; versioned `approved_source_preflight.py` / `approved_source_anchor.py` are the current implementation.
- Inputs/recipe: known immutable approved tree, declared module allowlist and controlled positive/negative identity fixtures. Reproduce using the committed contract, not the earlier hardcoded donor's environment.
- Limits/disposition: retain the negative C6 reasoning and its unresolved causal identity, not the old clock-run outputs or full re-derivation transcript. KNOWLEDGE_ONLY, then SAFE_DELETE checkout.

### Exception fidelity and phase closure

- Conclusion/context: A1/A2 preserved exception identity across the intended boundary; local proof/delivery did not establish the historical IPC cause, a successful native C4, or installer end-to-end acceptance. A lifecycle interface with a manifest consumer but no tracked producer was a separate limitation, not a reason to silently publish private harnesses.
- Refs: `95ea16018c3286e59091191d162abebfe72d82e4`, A1/A2 PRs #363/#365; delivered code and its public tests remain in main.
- Inputs/recipe: use the versioned exception-boundary fixtures and exact candidate ref; distinguish local fake-callback proof from production callback/native execution.
- Limits/disposition: original IPC cause remains UNKNOWN. The compact distinction and public refs replace the nine-PR working ledger and full trackers. KNOWLEDGE_ONLY, then SAFE_DELETE checkout.

## Internal candidate views: technical value versus controller lifecycle

All eleven are detached views whose HEAD commits are ancestors of main. Seven indexes contain old blobs not reachable from refs, but no selected continuation or concrete non-reproducible claim requires those historical bytes. Uniqueness is not a MUST_PRESERVE_BYTES argument.

- `1e8bbe8f-c0f8-46b5-8989-402816d157f0`: old G1/Inno `pre-install-evacuation`, smoke and specification pairing; eight unreachable index blobs. Preserve the historical design/state conclusion only.
- `3e0b3082-8fb4-40d2-9128-ee40c907a4ad`, `65864db3-6edc-4845-8100-cea6bad7649f`, `e6572f98-5b2a-4351-bd26-e02783b83443`: identical staged discovery/S04a snapshots with `FsView.kind`, a space-path spike and scoped verification text; eight blobs per view but one shared content set. Main evolved this area. No copy is retained by default merely to have one old copy.
- `b01d1df5-22eb-4f94-b852-1dcb09e1aeb2`: later staged Guard/deadline config-lock variant, two unreachable blobs. Main has a later lock/fallback implementation; no necessary missing capability was demonstrated.
- `ec0f02df-905a-4816-b99f-6ced807c5b45`: initial small Guard/deadline lock design, two unreachable blobs; preserve its conceptual contract, not a physical early-version checkout.
- `fecc0b18-e732-4325-b126-d6c81a8e56b1`: smoke/G1-fallback snapshot with G1 not yet closed; six unreachable blobs, partial overlap with the Inno snapshot. Do not attribute later acceptance retrospectively to that state.
- `039fcc5b-a08d-4a82-8bcb-e967cede2447`, `25dfd475-ca6e-48c0-8353-ebbe0b2a2d78`, `357c4513-44cb-45ba-b5ec-1a404e043be7`, `df645544-445e-44aa-b35b-0fcc5598954d`: no unreachable index blobs in the bounded prior comparison; no technical physical-retention need identified.

Inputs/recipe: reconstruct current behavior from versioned main tests/specifications. No historical candidate replay is selected. Old HEADs have local provenance (including PR #198/#199/#328 ancestry), not proof that a particular staged view was a merged candidate.

**Disposal restriction:** six owner sidecars identify token/PID-owned candidate roots; the remaining legacy views have no corresponding sidecar. Retained metadata did not establish a per-view terminal lifecycle/release binding. The installed ordinary-review CLI/facade exposes no verified generic candidate-view release/dispose operation. A root facade inspect was unrelated current-changes/untracked selection, not disposal permission. No START, reset, recover, abandonment, token editing, force-unlock or direct recursive deletion is authorized by this record.

These views are **DELETE_BLOCKED_BY_LIFECYCLE**, not technically valuable physical evidence to retain. The blocker is an unavailable validated disposal route/ownership clearance, not a claim that the old bytes are irreplaceable. Do not convert the blocker back into generic retention.

## Other historical work: sufficient knowledge only

### Approved-import donor

The donor checked module origins against a fixed historical approved tree and prepared an offline environment. Its hardcoded `ce3d452bf3e10bfd34c8c0f5054d72b2ea9f6f29` anchor and allowlist are historical, not current independent approval. Current C9 code is canonical. Inputs are an independently approved Git tree, interpreter/module origin constraints and declared dependency pins; use main's anchored preflight instead of reviving the donor. No selected continuation needs its untracked scripts/tests, old environments or proof outputs. KNOWLEDGE_ONLY.

### Reusable VM harness (#304)

Source `8d8f157fccae0fd7b8d8bab6be8c44b6009ca474` is in main. The harness attempts included failed/restored runs and input/evidence disk copies; presence of those artifacts is not native acceptance. Reproduction means a new explicitly authorized disposable-VM scenario from the versioned harness, declared inputs and fresh readiness/ownership checks. No exact historical disk state is selected for continued investigation here. No old VM/checkpoint permission is reused. Conclude failure/limits from the record; discard historical run payloads/media instead of preserving them as a second product. KNOWLEDGE_ONLY.

### C4 correction and private enrichment

Source base `0b04d815a7f0315fb32ca1bff0746066ac06565b` already contains the public runner delivery (PR #347). A secondary `CreateNew` diagnostic destination collision was distinct from the initiating after-setup error. The later minimal controlled collision/exception-fidelity fixes are represented in main. Private v2 exception-chain/64-KiB enrichment was not selected for continuation. Native failed dispatch permissions were consumed; no successful installation, original-cause attribution or accepted C4 follows from local tests. To reproduce a public regression, use committed boundary tests and synthetic writer fixtures; a fresh native experiment requires its own scope/inputs/authorization. Private runner variants, exact logs and packaging copies are unnecessary. KNOWLEDGE_ONLY.

### Updated C4 candidate and frozen verification

`proof/c4-updated-candidate` was based at `f5bd66fa17480fb71c5502e590ea89df329c8e01`; a prepared installer had a byte-identical copy in the correction checkout. Its existence was not unique evidence. Preparation/run records and packaging observations did not certify native acceptance. The frozen verification ref `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` remains reachable through retained non-main branches; its out-of-main history is not unique to a physical checkout. Adapter exception-gap observations and local tests must not be transferred as proof for another candidate. Use relevant committed tests at a chosen ref for authorized reproduction; exact old installer/log bytes are not needed for this conclusion. KNOWLEDGE_ONLY for both checkouts.

### Cache publication and accidental index state

The staged mass-deletion state did not represent 201 absent source files: files remained on disk and 192 of the compared paths matched main bytes. The product publication code inspected was already represented in main. The useful finding was a controlled environment-local temporary-path failure band; it did not establish a universal MAX_PATH threshold or resolve a separate C4 failure. The local acceptance was partial. Reproduce from versioned cache/marker tests with synthetic owned paths and explicit controls; no host-wide conclusion is licensed. Do not retain an accidental index layout, local logs, old test variants or marker scratch by inertia. KNOWLEDGE_ONLY.

### IPC observability, infrastructure and persistence donors

All three donors started from `0b04d815a7f0315fb32ca1bff0746066ac06565b`. C5/C7/C8 and the narrow pre-mapping slice are delivered in main. The basic observer framework and allowlisted ProviderError-before-mapping hook are not exclusive donor capabilities. Remaining experiments passed a richer exception object and added fixture persistence/termination checkpoints; `SystemExit` intent is not proof of actual OS exit, and observation order/timestamps do not establish provider-to-helper causality. Native propagation/causal identity stayed UNKNOWN. No richer donor variant was chosen for continuation in this phase. Reproduce committed synthetic observer/scanner/bootstrap tests from the relevant delivered ref; any new native causal study needs fresh inputs and authority. The conclusion and limitation replace three donor worktrees, native logs and staged copies. KNOWLEDGE_ONLY for each donor; historical C6's missing causal proof is not silently marked solved.

### S11 residual, PATH and consent history

Ref `4705748e7a64af34a47528f4fa73f02f8f391f5e` remains on non-main branches. Previous PATH/consent native attempts failed and did not reach the expected Off/completion state within their budget. Diagnostic runner design had qualified NO-GO limitations including unbounded `capture_output=True`; preparation or collection success was not product acceptance. Do not replay consumed grants or call a checkbox/consent observation a causal fix. A future authorized experiment must choose current versioned harness inputs and bounded execution/ownership controls; exact old logs/media or `nul` copies are not required to preserve this conclusion. KNOWLEDGE_ONLY.

### Ten formerly pending evidence holders

| Original worktree suffix | Conclusion/context and ref/input anchor | Future reproduction and limits |
|---|---|---|
| `c1-c4-integration` | Composition candidate `298228a46bec452c483202c8518a332e78bd8c49` was not a delivered canonical base; four commits remain outside main. Preserve its ref, not tmp/venv/composition logs. | Choose the retained commit and versioned scenarios for a fresh composition check; old result is not current acceptance. |
| `c1-cache-paths-candidate` | Fixture/path correction `c7d80b0db2afa15b7982ad758770b7cfcd596ffa` is reachable from main; local consolidated-base/manifests are preparation records. | Use committed synthetic fixture/path tests with declared pins; exact old stdout/manifests not required. |
| `c2-diagnostic-paths-candidate` | Detached candidate `9a4187b8b0160619117a8769293fee46336726e5` is reachable from main; two c4n namespaces were diagnostic runs. | Recover source by commit, create fresh owned synthetic paths; no exact old namespace/media required. |
| `c5-consolidated-candidate` | `c5bea4c9ddf0642cf06b360f19e7da406e2e2625` is reachable; C5 observational evidence did not solve historical IPC cause. | Use main's committed observer/fixture tests; independent receipts and baseline patch outputs are not required bytes. |
| `c5-ipc-observability-candidate` | Local test equals main after EOL normalization; the unique 1,015-byte RED log records a collection-stage failure, not an indispensable runtime observation. | Record that initial failure and reproduce only an agreed current case; do not retain old log/test copies. |
| `docs` | `203fe27190e1863df2711b6afd3fec7fbd1b3798` is outside main and remains referenced; native-proof outputs did not establish complete product/native acceptance. | Use the retained ref and declared workflow for a new run; historical JSON/XML/raw logs are unnecessary. |
| `path-feature` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` remains on retained refs and supplies original A for I1. Its 17 commits need no live checkout. | Immutable Git export is sufficient for I1; discard old installer/build/special-name scratch after knowledge consolidation. |
| `s11a-setup-assist` | `5cc45b29abe4c7a393327f0af76bddf1a49ebed4` is delivered; public PR #302 and code preserve implementation identity. Old lifecycle/media copies are not selected investigation inputs. | Rebuild functionally from versioned sources/pins when authorized; do not promise bit-identical historical installer bytes. |
| `s11b-299` | `364d4bffc00d48b62ba31339b4eb5c39c1778c6f` is delivered; rebuild media duplicated another pending checkout. | Use committed build/scenario definitions for fresh proof; no need to keep either historical media copy by default. |
| `s11b-reconciled` | `d5a05069169892c3b567922077aea0226e25a6a7` is delivered; custody/validator outputs belonged to a bounded historical lifecycle attempt. | Record scope/result limitations, then recreate only a new authorized scenario. Old validator logs/manifests are not required. |

A functional rebuild need not have the same historical binary hash. No bit-identical artifact is required merely to restate a known conclusion. Where old exact native inputs are unavailable, this note does not invent a complete replay recipe: any future execution is a newly scoped experiment, not recreation of the original run.

## Primary checkout and six former local historical records

The primary checkout owns the shared Git store and remains operational. Its versioned main tree is reconstructible, but shared refs/objects/index administration must not be discarded as run output.

The five original untracked task records have been reduced to the conclusions in this document:

- `agent-guide-policy-clarification.md`: policy delivery PR #345 / issue #344 and `f5bd66fa17480fb71c5502e590ea89df329c8e01`; cleanup requires scoped authorization, tests must not be weakened to fit an implementation, navigation tools do not grant product scope.
- `c4-diagnostic-native-cycle.md`: native attempts failed, permissions consumed, secondary diagnostic collision did not identify initiating cause; no VM-state mutation or replay is licensed.
- `c4-diagnostic-persistence.md`: preserve error identity and no-overwrite semantics; an existing destination is not proof that this run persisted a diagnostic. Public synthetic boundary tests are canonical, not private logs.
- `c4-runner-ruff-delivery.md`: PR #347 / issue #346 integrated the literal runner/test/tooling slice at `0b04d815a7f0315fb32ca1bff0746066ac06565b`; local/CI success was not native installer acceptance.
- `merged-delivery-hygiene.md`: previous bounded cleanup removed only explicitly authorized targets after Git guards; special-name filesystem failures were not permission for broad repair. Past KEEP/discard decisions were scope-specific, not eternal artifact requirements.

Their full transcripts, old custody hashes and historical operator logs need not remain physical files. The zero-byte `8` has no identified knowledge content. All six were removed after exact pre-disposal content/type guards and this note's consolidation. Root `build/`, pytest/Ruff caches and project Python bytecode caches were also removed when confirmed untracked. Active project configuration, the shared Git store and controller directories were not treated as historical run output. No raw secrets, provider payloads, VM/checkpoint identifiers or logs are copied here.

## Physical reduction ledger

The parked commits passed writer, parent and independent structural checks before physical retirement. Knowledge was consolidated before donor disposal. No runtime test, product import, native probe, installer or VM action was executed; no runtime acceptance or native review approval is claimed. Native assessments could not assess undeclared remaining untracked files; both units followed the conservative independent-verification path and passed.

| Item | Observed outcome |
|---|---|
| Original registrations | 39 -> 12 after ordinary sibling retirement; primary checkout plus 11 controller views remain. |
| Temporary control checkout | Additional while writing/verifying; retire after the local documentation commit. |
| Original physical sibling roots | 26 removed, one empty unregistered S11 directory process-locked. |
| Local branches | 56 + one documentation branch - 20 exact ancestor refs = 37. |
| I1/C11 | Two local commits, ten files, 196,225 canonical bytes; both physical worktrees removed. |
| Main local ref | Unchanged bc10800209e394015287397f2d7e197ad806e6ef; neither prototype merged into main. |
| Remote delivery | None: no push, PR, fetch, remote deletion or merge in this phase. |

The primary checkout may select `chore/minimal-retention` for local review without merging it into main. The final documentation commit postdates this snapshot; inspect that branch for its own commit identity rather than embedding a self-referential hash.

### Filesystem incident and remaining process lock

The initial Git retirement pass reported six Windows long-path/directory errors and four successful metadata removals leaving physical residues. It continued per item and exited nonzero; failures were not relabeled success. A separate diagnosis confirmed all ten leftovers were unregistered, without `.git` pointers or root reparse points. Exact authorized residues were then addressed through the Windows extended literal namespace, without changing ACLs/readonly flags, Git authority or ownership controls. Nine were removed.

`F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11-residual-proof` remains an **empty directory** because Windows returned WinError 32 (another process holds it). Its registration is gone; no source, log or evidence bytes remain inside. Category: **DELETE_BLOCKED_BY_LIFECYCLE**. Close/release the owning process working directory under separate authorization; do not force termination or call this a technical retention need. No blind retry was performed.

### Exact local branches deleted

Each tip was confirmed an ancestor of main and not checked out after retirement. The old `feat/s11b-transaction-closeout-v2` alias had no remaining byte-retention role; its commit is reachable from main and provenance exists in committed documentation.

- `feat/pre-mapping-provider-error-observability`
- `fix/c7-native-artifact-scanner`
- `fix/c8-helper-import-evidence`
- `chore/approved-source-preflight`
- `fix/c4-diagnostic-persistence`
- `fix/c5-observability-consolidated`
- `fix/c5-ipc-observability`
- `feat/s11a-installer-hardening`
- `feat/s11b-issue-299-closeout`
- `build/c5-reproof`
- `feat/issue-304-reusable-vm-harness`
- `chore/ipc-fixture-observability`
- `chore/ipc-observability-infrastructure`
- `chore/ipc-persistence-observability`
- `feat/s11b-transaction-closeout-v2`
- `fix/exception-fidelity-a1`
- `proof/c4-updated-candidate`
- `fix/c1-temp-fixture`
- `fix/cache-marker-publication`
- `chore/approved-import-proof`

Other original refs remain, except the two deliberately advanced parked branches. Branch deletion was local only. No force-push, rebase, reset, squash, physical backup or archive was used.

## Exact original identities

The table records original paths, branches and full commit IDs as provenance. Every ordinary sibling was deregistered; its physical root is absent except the empty S11 process-lock residue. Historical material is KNOWLEDGE_ONLY; physical disposition is SAFE_DELETE/completed unless blocked. I1/C11 continuation bytes are LIVE_WORK_REQUIRED on parked refs, not in live worktrees.

| Original path | Original HEAD | Original branch | Retention after sufficient knowledge |
|---|---|---|---|
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora` | `6ab4cd0cc17ad419e6201d60df21e3b04cbe7417` | `main` | LIVE_WORK_REQUIRED: active shared Git control |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/039fcc5b-a08d-4a82-8bcb-e967cede2447` | `de76b29346fa465872f10b2b68bef8ea3a202417` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/1e8bbe8f-c0f8-46b5-8989-402816d157f0` | `528313c972e14ef72f784ada0284ac7fdf5a5d82` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/25dfd475-ca6e-48c0-8353-ebbe0b2a2d78` | `5490a506e4236fd689f0e9b49c83bb8267dc6344` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/357c4513-44cb-45ba-b5ec-1a404e043be7` | `c04be6ebf4caf557a50f4fdc9771d2f9e65964ae` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/3e0b3082-8fb4-40d2-9128-ee40c907a4ad` | `528313c972e14ef72f784ada0284ac7fdf5a5d82` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/65864db3-6edc-4845-8100-cea6bad7649f` | `528313c972e14ef72f784ada0284ac7fdf5a5d82` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/b01d1df5-22eb-4f94-b852-1dcb09e1aeb2` | `7a2ea0eacf19de8c6b3f0f45e6997a9e8d631ae9` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/df645544-445e-44aa-b35b-0fcc5598954d` | `3019d7f8a2aff05511161d583b46b26b91c4cf21` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/e6572f98-5b2a-4351-bd26-e02783b83443` | `528313c972e14ef72f784ada0284ac7fdf5a5d82` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/ec0f02df-905a-4816-b99f-6ced807c5b45` | `584e5b25bf6e97fbc68898850a00d4e4bf8b428d` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/fecc0b18-e732-4325-b126-d6c81a8e56b1` | `528313c972e14ef72f784ada0284ac7fdf5a5d82` | `DETACHED` | DELETE_BLOCKED_BY_LIFECYCLE: no validated controller disposal route |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-304` | `8d8f157fccae0fd7b8d8bab6be8c44b6009ca474` | `feat/issue-304-reusable-vm-harness` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-approved-import-proof` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `chore/approved-import-proof` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c1-c4-integration` | `298228a46bec452c483202c8518a332e78bd8c49` | `test/c1-c4-composition` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c1-cache-paths-candidate` | `c7d80b0db2afa15b7982ad758770b7cfcd596ffa` | `fix/c1-temp-fixture` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c2-diagnostic-paths-candidate` | `9a4187b8b0160619117a8769293fee46336726e5` | `DETACHED` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-correction` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `fix/c4-diagnostic-persistence` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-updated-candidate` | `f5bd66fa17480fb71c5502e590ea89df329c8e01` | `proof/c4-updated-candidate` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-verification` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` | `proof/c4-baseline-verification` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c5-consolidated-candidate` | `c5bea4c9ddf0642cf06b360f19e7da406e2e2625` | `fix/c5-observability-consolidated` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c5-ipc-observability-candidate` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `fix/c5-ipc-observability` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c6-premapping` | `f9505932be7ed3a6a67e0609b399a48706a554c3` | `feat/pre-mapping-provider-error-observability` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c7-artifact-scanner-candidate` | `f334b27488e772d3f54b884f738a082facd3881b` | `fix/c7-native-artifact-scanner` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c8-import-evidence-candidate` | `386a0542d25c494c8a245188aa0f06fc432c7a7f` | `fix/c8-helper-import-evidence` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c9-preflight` | `aec3c0283b85c75da88ae7262bef73c2ea932041` | `chore/approved-source-preflight` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-cache-marker-fix` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `fix/cache-marker-publication` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-docs` | `203fe27190e1863df2711b6afd3fec7fbd1b3798` | `docs/installation-guide-coherence` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-exception-fidelity` | `95ea16018c3286e59091191d162abebfe72d82e4` | `fix/exception-fidelity-a1` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-i1-hermetic-ab` | `f5bd66fa17480fb71c5502e590ea89df329c8e01` | `test/i1-hermetic-ab` | SAFE_DELETE: checkout removed; LIVE_WORK_REQUIRED bytes on parked ref |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-observability` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `chore/ipc-fixture-observability` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-observability-infrastructure` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `chore/ipc-observability-infrastructure` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-persistence-observability` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `chore/ipc-persistence-observability` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-path-feature` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` | `feat/path-installer-management` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-path-step-trace` | `0b04d815a7f0315fb32ca1bff0746066ac06565b` | `chore/c4-path-step-trace` | SAFE_DELETE: checkout removed; LIVE_WORK_REQUIRED bytes on parked ref |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11-residual-proof` | `4705748e7a64af34a47528f4fa73f02f8f391f5e` | `fix/s11-consented-cleanup` | DELETE_BLOCKED_BY_LIFECYCLE: empty unregistered directory held by a process |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11a-setup-assist` | `5cc45b29abe4c7a393327f0af76bddf1a49ebed4` | `feat/s11a-installer-hardening` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11b-299` | `364d4bffc00d48b62ba31339b4eb5c39c1778c6f` | `feat/s11b-issue-299-closeout` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |
| `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11b-reconciled` | `d5a05069169892c3b567922077aea0226e25a6a7` | `build/c5-reproof` | KNOWLEDGE_ONLY: note consolidated; SAFE_DELETE physical checkout removed |

## Remaining local refs after cleanup

This is the pre-documentation-commit ref snapshot. The documentation branch advances for its own final commit; its base below is not presented as its eventual tip. No out-of-main branch was deleted merely by patch-equivalence.

| Ref | Tip before final documentation commit | Role |
|---|---|---|
| `chore/c4-path-step-trace` | `ebdd0e75fda5e254def826a39932200edd0c21a9` | selected parked C11 source |
| `chore/issue-311-ruff-baseline` | `0aacfd982d762a1a05233258db1be857b1be414e` | retained out-of-main history/provenance |
| `chore/issue-311-ruff-e701-source` | `69039839c5d1d80ab6b53bf56baabf8ea44ca6ec` | retained out-of-main history/provenance |
| `chore/issue-311-ruff-e701-tests` | `f2c5d0be85ffb50acf4133f2fde9062bfc4bb26e` | retained out-of-main history/provenance |
| `chore/issue-311-ruff-e702` | `38f38f2adf787ae07cfa13487c972f91b176602c` | retained out-of-main history/provenance |
| `chore/issue-311-ruff-e731` | `54ae9f0fd300cefc032185c799e3d956a97c04f2` | retained out-of-main history/provenance |
| `chore/minimal-retention` | `bc10800209e394015287397f2d7e197ad806e6ef` | local documentation branch; final commit follows |
| `docs/installation-guide-coherence` | `203fe27190e1863df2711b6afd3fec7fbd1b3798` | retained out-of-main history/provenance |
| `docs/issue-311-e7-closeout` | `bc173ee8096c445dc3a13126cd0bcb16ea10f1ce` | retained out-of-main history/provenance |
| `docs/repository-agent-guide` | `671049f08b525b2e7329e91e4faffde2c380a72d` | retained out-of-main history/provenance |
| `feat/path-installer-management` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` | retained out-of-main history/provenance |
| `feat/path-owned-cleanup-02-updates` | `413974c7524d5ce389bcfeeffd14f0569b55b3f7` | retained out-of-main history/provenance |
| `feat/path-owned-cleanup-03-uninstall-consent` | `2cff78514ab4a5dd9e6c5443e6f62063aaea3250` | retained out-of-main history/provenance |
| `feat/r11-bounded-config-read` | `6b3a1e07af98f886be9bd8a4934d37844b34b1c7` | retained out-of-main history/provenance |
| `feat/r11-bounded-io-call` | `b10b2de8c7b7241e8d95256f63b6fb3fd19b444f` | retained out-of-main history/provenance |
| `feat/r11-cache-coordination` | `0498684ee2b67f8a7f288dc91fe1c6bc545c7325` | retained out-of-main history/provenance |
| `feat/r11-foundations` | `23e6f38b2e66c648a223b2310f8d95fc0ddd9b79` | retained out-of-main history/provenance |
| `feat/r11-foundations-v2` | `23e6f38b2e66c648a223b2310f8d95fc0ddd9b79` | retained out-of-main history/provenance |
| `feat/r11-public-contract` | `0e9467917091e94ed29fdefd7fab7e513cbe0b39` | retained out-of-main history/provenance |
| `feat/r11-runtime-lifecycle` | `0e9467917091e94ed29fdefd7fab7e513cbe0b39` | retained out-of-main history/provenance |
| `feat/s11b-transaction-closeout-reconciled` | `84ddcb3d9854806c8c56af9b3fb7aa9441a6b6c3` | retained out-of-main history/provenance |
| `feature/137-json-projection` | `13f63d6036650cea38915ce13b9413663efbccc2` | retained out-of-main history/provenance |
| `fix/g1-rollback-consent-gate` | `49d43a02944484549b47ee4849db79b95aa86c2d` | retained out-of-main history/provenance |
| `fix/path-add-error-boundary` | `5a5687321bc754c43c910133cde0ffe304520d77` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-01-ownership` | `4705748e7a64af34a47528f4fa73f02f8f391f5e` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-04-exact-ownership` | `bd8302d1cf90489d4bc131e610dfcced20f45302` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-05-inno-compat` | `74a4dcce6e487a48cb554d20e6260189458369ad` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-06-preview` | `eca023420c7d0d56f653624480813448599fe069` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-07-consent-arguments` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-08-registry-io` | `accae6dd1ce3df211d0cf83d6b6dd18347836a36` | retained out-of-main history/provenance |
| `fix/path-owned-cleanup-09-pytest-temp` | `5a5687321bc754c43c910133cde0ffe304520d77` | retained out-of-main history/provenance |
| `fix/s11-consented-cleanup` | `4705748e7a64af34a47528f4fa73f02f8f391f5e` | retained out-of-main history/provenance |
| `fix/s11a-protocol-closeout` | `a50335c3309d4d520ae18571f0830a7eeeea5081` | retained out-of-main history/provenance |
| `main` | `bc10800209e394015287397f2d7e197ad806e6ef` | unchanged main |
| `proof/c4-baseline-verification` | `8f2793246d39d3a09cf7bd39c7853db220f7e0cd` | retained out-of-main history/provenance |
| `test/c1-c4-composition` | `298228a46bec452c483202c8518a332e78bd8c49` | retained out-of-main history/provenance |
| `test/i1-hermetic-ab` | `1845246b0e6bfb588eec02c274446e2a5d0adcd9` | selected parked I1 source |
