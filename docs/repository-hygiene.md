# Repository hygiene: final safe-cleanup state

## Decision

The bounded cleanup found **no eligible historical worktree or branch deletions**. The original **39 worktrees / 56 local branches** remain in place: **25 KEEP, 10 ARCHIVE_PENDING and 4 AMBIGUOUS**. Seven internal views were reclassified from AMBIGUOUS to KEEP because their indexes contain blobs unreachable from any ref. No archives, copies or moves were created. Unresolved per-item retention did not prevent consolidation and documentation delivery. This record is not standing authorization for further cleanup or technical investigation.

The baseline is local `main` at `6ab4cd0cc17ad419e6201d60df21e3b04cbe7417`, matching the last fetched `origin/main`. This is not a fresh remote assertion. The original 39 consist of the primary checkout, 27 ordinary siblings and 11 detached internal candidate views. There are 27 attached branches and 29 branch-only references among the original 56 branches.

**Documentation isolation:** the maintainer explicitly selected a separate worktree for this document: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-hygiene-doc`, branch `docs/repository-hygiene-inventory`, created from the baseline commit. Operational totals are **40 worktrees / 57 branches** while it exists. It is not one of the original 39; no original checkout was moved or replaced. Its only intended local change is this document. The maintainer authorized one commit, `docs: record repository hygiene state`, and a PR against main using nonclosing `Refs #370`. Retirement of this temporary worktree and its local branch is authorized only after CI-green, conflict-free merge and fast-forward synchronization of main. The recorded long-lived state is 39/56; 40/57 is the temporary pre-delivery operational state, not an additional historical retention decision.

## Classification

| Classification | Original worktrees | Meaning |
|---|---:|---|
| KEEP | 25 | Original 18 protected checkouts plus seven internal views with unique staged blobs. |
| ARCHIVE_PENDING | 10 | The worktree no longer participates in active development, but is temporarily retained because it contains evidence/local state whose preservation or supersession has not yet been demonstrated. |
| AMBIGUOUS | 4 | Internal views without demonstrated terminal lifecycle/disposal authority, despite having no index blobs unreachable from refs. |

**ARCHIVE_PENDING is a retention status, not an action.** Every entry in that category remains at its existing path. It is not permission to create an archive or move anything into `odd/`. These ten are candidates for a future disposition, not approved deletions. Zero additional worktrees or branches have been certified safe to delete by this assessment.

Read the retention decision below together with the Git-state inventory at the end. Each inventory entry gives its name, exact path, HEAD, branch, commits outside main, and relevant staged/unstaged/untracked/ignored state. Representative evidence groups are not an exhaustive deletion scope.

## Protected context

- **Historical C6 remains retained/blocked on native causal proof.** Protect its persistence donors, decision records and run evidence. The narrow pre-mapping ProviderError slice already delivered to main does not close historical C6 cross-process causal-proof obligations.
- **C10 / I1 and C11 / PATH trace remain retained for resumability.** The C-number-to-path correspondence comes from recovered historical memory (observation 11062); repository parking records do not explicitly bind those labels to paths. Their identifiable local state is described below. No equivalent implementation merged under another form, or smaller lossless resumption set, has been demonstrated.
- **All 11 internal views remain retained: seven KEEP and four AMBIGUOUS.** All HEADs are ancestors of main, but seven indexes contain blobs unreachable from any ref. The follow-up bounded metadata audit recovered no owner-to-UUID lifecycle binding for any view. Terminal consumption/release and canonical frozen-evidence supersession remain unproven. No authority repair or candidate removal was performed.
- **The six historical main untracked files remain unattributed:**
  - `8`
  - `odd/tasks/agent-guide-policy-clarification.md`
  - `odd/tasks/c4-diagnostic-native-cycle.md`
  - `odd/tasks/c4-diagnostic-persistence.md`
  - `odd/tasks/c4-runner-ruff-delivery.md`
  - `odd/tasks/merged-delivery-hygiene.md`

The new hygiene document is separate from those six files. Their continued presence is not an attribution or a lossless preservation certification.

## Retention decisions: primary checkout and ordinary siblings

Names below match the final Git-state inventory. Paths, HEADs and state must be revalidated before any future authorized operation.

### Primary checkout — KEEP

`yasb-limitora` is the main working checkout. It contains the six unattributed historical untracked files above and ignored local tooling/build evidence. It is not a cleanup candidate. Any disposition of those files requires separate attribution and maintainer authorization.

### KEEP: source, decisions, proof obligations and resumability

All names in the following table have the prefix `yasb-limitora-`. None is approved for removal.

| Worktree suffix | Why it remains / evidence or local state | Condition for future removal |
|---|---|---|
| `304` | Local reusable VM proof-harness material, host artifacts and issue-304 run/evidence groups. This checkout is not itself identified as C10. | Identify canonical harness/evidence and explicitly dispose all local host artifacts and run state. |
| `approved-import-proof` | Modified `scripts/README.md`; local preflight/environment-preparation scripts, tests and docs; dedicated proof runs. Later delivered preflight work does not prove these donor files redundant. | Attribute each donor delta and demonstrate canonical preservation or supersession of dedicated proof evidence. |
| `c4-correction` | Uncommitted persistence/exception-fidelity changes, local diagnostic-persistence tests, `c4-exception-fidelity.md` and build evidence. | Resolve runner/test identities against canonical delivery and retain or supersede historical decision/evidence records. |
| `c4-updated-candidate` | Local task records, workflow delta and extensive updated-candidate proof outputs. | Attribute each tracker/workflow delta and demonstrate preservation or supersession of proof evidence. |
| `c4-verification` | Out-of-main commits, local setup-assist path/protocol test changes, task records and build evidence. Partial patch-equivalence reports do not settle the history. | Account for every out-of-main commit and local delta and identify canonical proof provenance. |
| `c6-premapping` | Explicitly retained C6-related checkout and `build/premapping` evidence. The pre-mapping slice is in main, but historical C6 obligations remain blocked. | Explicit maintainer disposition of retained C6 material and demonstrated evidence preservation or supersession; narrow slice delivery is not full C6 closure. |
| `c7-artifact-scanner-candidate` | Sole-copy local `odd/tasks/c7-c5-c8-delivery.md` and scanner/delivery evidence. | Demonstrate canonical retention or supersession of the delivery tracker and referenced evidence. |
| `c8-import-evidence-candidate` | Sole-copy local `odd/tasks/exception-fidelity-reconciliation.md` and helper-import evidence. | Retain or supersede reconciliation decisions and establish canonical import-evidence provenance. |
| `c9-preflight` | Sole-copy local `odd/tasks/c6-rederivation.md` and approved-source preflight runs. | Preserve C6 re-derivation decisions and identify canonical preflight evidence. |
| `cache-marker-fix` | Large staged-deletion/untracked-replacement state, local tests/task records and build evidence. A plain file copy or unstaged diff would not preserve index semantics. | Resolve index/worktree provenance and explicitly preserve or supersede staging as well as unique files; no automatic cleanup. |
| `exception-fidelity` | Sole-copy local `odd/tasks/exception-fidelity-a1-a2.md` and `phase-closure.md`, recent delivery decisions and related build evidence. | Establish canonical retention or supersession of both decision records and their referenced evidence. |
| `i1-hermetic-ab` | C10 historical correspondence: unique local I1 tooling/tests, two trackers, retained A/B namespace and watcher-proof evidence. Details below. | Retain for resumability until explicit disposition and demonstrated preservation or supersession of all unique material. |
| `ipc-observability` | Local helper/supervisor/fixture/native-proof deltas, observer source/docs/tests, task record and IPC run evidence. | Attribute donor deltas against delivered slices; do not assume all cumulative instrumentation shipped. Preserve referenced decisions and evidence. |
| `ipc-observability-infrastructure` | Cumulative observer/scanner/import/persistence donor material, local persistence tests/task record and bootstrap/build evidence. | Attribute remaining deltas and preserve C6-referenced evidence; historical C6 remains retained/blocked. |
| `ipc-persistence-observability` | Historical C6 persistence donor: source/fixture/test deltas, local observer/persistence files and IPC run diagnostics. Native cross-process causality remains unproven. | Explicit disposition of historical C6 plus demonstrated preservation or supersession of its evidence; no silent downgrade of the causal-proof requirement. |
| `path-step-trace` | C11 historical correspondence: four tracked modifications and four new diagnostic/test/doc/tracker files. Details below. | Retain for resumability until explicit disposition and demonstrated preservation or supersession of all local deltas and blocker/provenance records. |
| `s11-residual-proof` | Out-of-main history, `nul`/`nul.json`, two task records and substantial residual-proof evidence. Special names do not establish disposable content. | Attribute unique history, decisions, special-name entries and proof evidence before any disposition. |

### C10 / I1 resumption material

Worktree: `yasb-limitora-i1-hermetic-ab`; branch: `test/i1-hermetic-ab`. There are no commits outside main, but its unique local work is not recoverable from that branch's commits.

Retain all of these, without attempting to reduce the scaffolding in this phase:

- `scripts/i1_hermetic_ab.py`, `scripts/i1_native_registry_probe.py`, `scripts/prepare_i1_watcher_input.py`, `scripts/i1_native_watch_runner.ps1`;
- `tests/test_i1_hermetic_ab.py`, `tests/test_i1_watcher_registry_proof.py`;
- `odd/tasks/i1-hermetic-ab.md`, `odd/tasks/i1-watcher-registry-proof.md`;
- retained `.h2-i1-ab-20260625-6d4c1f/`, local temporary namespace and `build/i1-watcher-proof` evidence.

The controlled A/B was executed historically. The later native registry case was explicitly **NOT EXECUTED**; resumption requires fresh authorization. This is tooling/probes/evidence rather than product implementation. Original file paths being absent from main does not prove that no equivalent exists under a different form; equivalence remains unproven.

### C11 / PATH trace resumption material

Worktree: `yasb-limitora-path-step-trace`; branch: `chore/c4-path-step-trace`. There are no commits outside main, but its local deltas are not committed.

Retain the modified `packaging/inno/SetupAssistant.isi`, `packaging/inno/yasb-limitora.iss`, `src/yasb_limitora/setup_assist.py` and `tests/test_inno_script.py`, plus new `src/yasb_limitora/_path_step_trace.py`, `tests/test_installer_path_trace.py`, `docs/installer-path-step-trace.md` and `odd/tasks/installer-path-step-trace.md`.

The work is mixed product-source diagnostics and tooling, not merely scratch. Historical P3 was blocked by a full-suite failure without demonstrated candidate/base causality. No work-unit commit or equivalent merged implementation has been demonstrated. Preserve all listed material and the historical blocker; do not reopen testing or investigate runtime behavior under this document.

### ARCHIVE_PENDING: ten inactive worktrees retained in place

**For every row:** the worktree no longer participates in active development, but is temporarily retained because it contains evidence/local state whose preservation or supersession has not yet been demonstrated. No archive exists by implication and no copy, move or deletion is authorized.

All names have the prefix `yasb-limitora-`.

| Worktree suffix | Evidence / local state preventing removal | Condition for future removal |
|---|---|---|
| `c1-c4-integration` | Historical composition evidence, `build/integration-composition`, temporary outputs and environment; commits outside main. | Demonstrate evidence preservation or supersession and account for every out-of-main commit. Patch-equivalence is not ancestry or complete reconstruction proof. |
| `c1-cache-paths-candidate` | `build/c1-fixture-fix` evidence; ancestor HEAD does not preserve ignored outputs. | Demonstrate fixture-evidence preservation or supersession and revalidate current local state. |
| `c2-diagnostic-paths-candidate` | `build/c4n` diagnostic evidence and detached candidate identity. HEAD is already reachable from main; detached status alone is not unique-commit loss. | Demonstrate evidence preservation or supersession and retain exact candidate/commit provenance. |
| `c5-consolidated-candidate` | `build/c5-delivery`, independent-verification and pytest outputs. | Establish canonical delivery/verification evidence or demonstrated supersession. |
| `c5-ipc-observability-candidate` | Local `tests/test_native_proof_observability.py` and ignored build outputs. The path also exists in main, but that alone does not prove identical bytes. | Prove canonical equivalence of the local test and establish the disposition of ignored outputs. |
| `docs` | `native-proof.json`/`native-proof.xml`, ignored raw logs/environment artifacts and out-of-main commit identity. | Establish canonical proof/log provenance and account for the commit; do not infer evidence equivalence from a patch match. |
| `path-feature` | Out-of-main installer history, ignored build evidence and untracked `NUL`. | Account for history, evidence and the special-name entry; no name-based discard, reset or forced branch deletion follows. |
| `s11a-setup-assist` | `build/s11a-lifecycle` and local environments/caches. Cache status does not make lifecycle evidence disposable. | Demonstrate lifecycle-evidence preservation or supersession and retain cited delivery provenance. |
| `s11b-299` | `build/frozen`, `build/c5-rebuild` and proof-harness artifacts. | Demonstrate frozen/rebuild evidence preservation or supersession and retain delivery provenance. |
| `s11b-reconciled` | `build/s11b-lifecycle` reproof evidence. | Demonstrate lifecycle/reproof evidence preservation or supersession and retain cited delivery provenance. |

## Internal candidate views — seven KEEP, four AMBIGUOUS

All eleven exact identities, paths and local states appear in the inventory below. They are controller-owned detached views, not ordinary disposable checkouts. A bounded follow-up scan of 44 transaction directories and relevant shallow metadata stores found no per-view UUID lifecycle linkage. Owner-file presence alone does not prove terminal disposition. Seven content-bearing views are KEEP; four others remain AMBIGUOUS. Neither category is asserted inactive or superseded.

Future removal requires attribution of terminal lifecycle/ownership, a permitted disposal route and evidence supersession through the owning controller, followed by explicit maintainer authorization. Neither shared HEADs nor clean status establishes supersession. No raw metadata repair, recursive fallback or ordinary worktree cleanup is authorized here.

## Branch references and safeguards

The original 29 branch-only references are not automatically disposable. Retain the explicitly historical `feat/s11b-transaction-closeout-v2` reference. Across all original branches, 33 have commits outside main; earlier patch-equivalence observations do not change ancestry or establish permission to discard historical identities. Worktree and branch retirement are separate decisions.

A future authorized operation must revalidate exact Git identities and local state. Preservation or supersession must cover relevant unique files, staged index state, uncommitted changes, historical commits, manifests and referenced run evidence. Special-name files and unknown links require explicit handling; do not use recursive cleanup as a fallback. This document mandates neither an archive mechanism nor an archive location.

## Provenance and limitations

This document consolidates the earlier local metadata inventory (`build/repository-hygiene-6ab4cd0.json`, ignored and local-only) and bounded attribution handoffs. That local JSON is not a tracked documentation dependency: necessary identities, reasons and conditions are repeated here for future agents.

File-state groups are metadata, not a payload audit or lossless preservation certificate. No local functional tests, builds or VM/registry probes were run for this documentation-only change. Authorized GitHub metadata reads established the delivery target and approved issue #370. The repository ruff and native-proof workflows gate the PR; their candidate outcomes must be verified before merge, not pre-certified here. Historical run outcomes are provenance, not present runtime proof.

Earlier attribution tooling reported scratch `/tmp/hyg-yPNYwZ`. Its contents/location were not attributed or inspected here; this document grants no external cleanup authority.

Update this document after an explicitly authorized disposition. Do not silently reinterpret ARCHIVE_PENDING as permission to copy evidence, create archives, move worktrees into `odd/` or delete branches.

## Completed cleanup assessment

### Outcomes and removals

Historical worktrees removed in this continuation: **none**. Historical local branches removed: **none**. The earlier first hygiene pass removed two ordinary worktrees and 104 local branches before this 39/56 baseline; those are not removals from this continuation. The only additional retirement authorized here concerns the temporary documentation checkout/ref after verified delivery.

### Ten ARCHIVE_PENDING decisions

| Worktree suffix | New bounded evidence / remaining blocker |
|---|---|
| `c1-c4-integration` | Four commits outside main; composition and diagnostic runs lack demonstrated canonical preservation. |
| `c1-cache-paths-candidate` | Fixture manifests, consolidated-base and independent evidence remain local; ancestry does not retain ignored runs. |
| `c2-diagnostic-paths-candidate` | HEAD is reachable from main, but two c4n diagnostic namespaces lack demonstrated canonical evidence preservation. |
| `c5-consolidated-candidate` | Delivery/independent-acceptance receipts and baseline delta evidence lack demonstrated canonical supersession. |
| `c5-ipc-observability-candidate` | The local test matches main after CRLF normalization, but the 1,015-byte RED log lacks a demonstrated canonical copy. Partial supersession does not clear the checkout. |
| `docs` | One out-of-main commit and native-proof JSON/XML/raw logs; canonical preservation not demonstrated. |
| `path-feature` | Seventeen commits outside main, ignored build evidence and untracked NUL. Another ref to the same HEAD does not establish delivery. |
| `s11a-setup-assist` | Custody/lifecycle evidence and installer media remain local; canonical retained media not demonstrated. |
| `s11b-299` | Some payloads/media duplicate another pending checkout, but neither copy was demonstrated to be canonical retained evidence. |
| `s11b-reconciled` | Lifecycle manifest/custody and validator-capture evidence remain; canonical supersession unproven. |

Comparisons were bounded, not exhaustive proofs of global uniqueness. Inability to demonstrate preservation or supersession is enough to retain each item. No native proof was rerun to force a cleanup decision.

### Eleven internal origins and exclusive index states

All views are detached, have zero commits outside main and have no untracked files. Exact full HEADs and paths are in the inventory. HEAD `528313c` is the PR #198 merge, `584e5b2` the PR #199 merge and `3019d7f` the PR #328 merge; other feature/doc HEADs are reachable from main. These are local HEAD provenance facts, not proof that staged candidate content was merged. No owner-to-review UUID binding or canonical frozen-evidence hash was recovered.

| UUID | Index blobs unreachable from refs | Owner file | Final retention / exclusive material |
|---|---:|---|---|
| `039fcc5b-a08d-4a82-8bcb-e967cede2447` | 0 | Present | AMBIGUOUS: lifecycle/disposal unknown. |
| `1e8bbe8f-c0f8-46b5-8989-402816d157f0` | 8 | Absent | KEEP: staged Inno, smoke and specification evidence. |
| `25dfd475-ca6e-48c0-8353-ebbe0b2a2d78` | 0 | Present | AMBIGUOUS: lifecycle/disposal unknown. |
| `357c4513-44cb-45ba-b5ec-1a404e043be7` | 0 | Present | AMBIGUOUS: lifecycle/disposal unknown. |
| `3e0b3082-8fb4-40d2-9128-ee40c907a4ad` | 8 | Absent | KEEP: staged discovery, tests and specifications. |
| `65864db3-6edc-4845-8100-cea6bad7649f` | 8 | Absent | KEEP: staged discovery, tests and specifications. |
| `b01d1df5-22eb-4f94-b852-1dcb09e1aeb2` | 2 | Present | KEEP: staged config-lock source and tests. |
| `df645544-445e-44aa-b35b-0fcc5598954d` | 0 | Present | AMBIGUOUS: lifecycle/disposal unknown. |
| `e6572f98-5b2a-4351-bd26-e02783b83443` | 8 | Absent | KEEP: staged discovery, tests and specifications. |
| `ec0f02df-905a-4816-b99f-6ced807c5b45` | 2 | Present | KEEP: staged config-lock source and tests. |
| `fecc0b18-e732-4325-b126-d6c81a8e56b1` | 6 | Absent | KEEP: staged smoke, Inno evidence and specifications. |

Object reachability is a bounded Git comparison, not universal filesystem uniqueness. Some views share content, but that does not settle either lifecycle. Zero unreachable blobs is not terminal disposal proof. Internal views are not assigned ARCHIVE_PENDING because their live controller ownership/inactivity remains unknown.

### All 29 branch-only references retained

Twenty-eight contain commits outside main. The one ancestor reference has explicit historical/documental value. Consequently no branch passes all deletion conditions. Patch-equivalence does not change these reachability counts.

| Branch | Commits outside main | Retention |
|---|---:|---|
| `chore/issue-311-ruff-baseline` | 7 | Outside-main history |
| `chore/issue-311-ruff-e701-source` | 1 | Outside-main history |
| `chore/issue-311-ruff-e701-tests` | 1 | Outside-main history |
| `chore/issue-311-ruff-e702` | 1 | Outside-main history |
| `chore/issue-311-ruff-e731` | 1 | Outside-main history |
| `docs/issue-311-e7-closeout` | 1 | Outside-main history |
| `docs/repository-agent-guide` | 1 | Outside-main history |
| `feat/path-owned-cleanup-02-updates` | 2 | Outside-main history |
| `feat/path-owned-cleanup-03-uninstall-consent` | 3 | Outside-main history |
| `feat/r11-bounded-config-read` | 3 | Outside-main history |
| `feat/r11-bounded-io-call` | 2 | Outside-main history |
| `feat/r11-cache-coordination` | 4 | Outside-main history |
| `feat/r11-foundations` | 1 | Outside-main history |
| `feat/r11-foundations-v2` | 1 | Outside-main history |
| `feat/r11-public-contract` | 5 | Outside-main history |
| `feat/r11-runtime-lifecycle` | 5 | Outside-main history |
| `feat/s11b-transaction-closeout-reconciled` | 9 | Outside-main history |
| `feat/s11b-transaction-closeout-v2` | 0 | Explicit historical/documental reference |
| `feature/137-json-projection` | 1 | Outside-main history |
| `fix/g1-rollback-consent-gate` | 7 | Outside-main history |
| `fix/path-add-error-boundary` | 19 | Outside-main history |
| `fix/path-owned-cleanup-01-ownership` | 1 | Outside-main history |
| `fix/path-owned-cleanup-04-exact-ownership` | 5 | Outside-main history |
| `fix/path-owned-cleanup-05-inno-compat` | 10 | Outside-main history |
| `fix/path-owned-cleanup-06-preview` | 14 | Outside-main history |
| `fix/path-owned-cleanup-07-consent-arguments` | 17 | Outside-main history |
| `fix/path-owned-cleanup-08-registry-io` | 18 | Outside-main history |
| `fix/path-owned-cleanup-09-pytest-temp` | 19 | Outside-main history |
| `fix/s11a-protocol-closeout` | 3 | Outside-main history |

### Synchronized baseline and delivery boundary

After the bounded cleanup, fetch/prune, worktree prune and fast-forward-only synchronization succeeded. `main == origin/main == 6ab4cd0cc17ad419e6201d60df21e3b04cbe7417`; main had no tracked/staged changes and the six historical untracked files remained present and unattributed. No historical refs or checkouts were removed.

The documentation commit and merge necessarily advance main beyond this cleanup snapshot. Embedding the document's own eventual merge hash would be self-referential: use the PR merge record and `git rev-parse main origin/main` for the post-delivery identity. The temporary documentation checkout/ref is retired only after verified merge and fast-forward synchronization, followed by final prune. This does not change the 39 retained historical worktrees or their 56 local branches.

Remaining human decisions are per-item: preservation/supersession for ten pending evidence holders; retained unique index material for seven internal views; controller disposal authority for four unresolved views; C6 causal proof; C10/C11 resumability; attribution of six historical main files. No broad disposal permission is inferred.

## Git-state inventory: original 39

The following snapshot was read during document preparation. `Index` counts staged paths, `WT` unstaged tracked paths, `U` untracked paths excluding ignored files, and `I` ignored paths. Counts are paths, not changed lines. Examples are partial and never define a deletion scope. Commits outside main are counted by reachability, not patch similarity.

### 01. yasb-limitora — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora`.
- HEAD: `6ab4cd0cc17ad419e6201d60df21e3b04cbe7417`.
- Branch: `main`.
- Commits outside main: **0**; behind main: **0**.
- State: Index **0**, WT **0**, U **6**, I **370**.
- Untracked examples: `8`, `odd/tasks/agent-guide-policy-clarification.md`, `odd/tasks/c4-diagnostic-native-cycle.md`, `odd/tasks/c4-diagnostic-persistence.md`, `odd/tasks/c4-runner-ruff-delivery.md`. Partial list; no disposable inference.
- Ignored groups: `.agents` (6), `.atl` (3), `.codegraph` (3), `.pi` (1), `.pytest_cache` (5), `.ruff_cache` (120), `build` (128), `scripts` (5), `src` (53), `tests` (46). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 02. 039fcc5b-a08d-4a82-8bcb-e967cede2447 — AMBIGUOUS

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/039fcc5b-a08d-4a82-8bcb-e967cede2447`.
- HEAD: `de76b29346fa465872f10b2b68bef8ea3a202417`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **93**.
- State: Index **0**, WT **0**, U **0**, I **0**.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 03. 1e8bbe8f-c0f8-46b5-8989-402816d157f0 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/1e8bbe8f-c0f8-46b5-8989-402816d157f0`.
- HEAD: `528313c972e14ef72f784ada0284ac7fdf5a5d82`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **205**.
- State: Index **28**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  README.md`, `A  docs/release/0.2.0/MIGRATION.md`, `A  docs/release/0.2.0/RELEASE_NOTES.md`, `A  docs/release/0.2.0/evidence/inno-staged-swap-spike.md`, `M  docs/roadmap.md`. Partial list; index/worktree distinctions must survive any future disposition.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 04. 25dfd475-ca6e-48c0-8353-ebbe0b2a2d78 — AMBIGUOUS

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/25dfd475-ca6e-48c0-8353-ebbe0b2a2d78`.
- HEAD: `5490a506e4236fd689f0e9b49c83bb8267dc6344`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **100**.
- State: Index **0**, WT **0**, U **0**, I **0**.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 05. 357c4513-44cb-45ba-b5ec-1a404e043be7 — AMBIGUOUS

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/357c4513-44cb-45ba-b5ec-1a404e043be7`.
- HEAD: `c04be6ebf4caf557a50f4fdc9771d2f9e65964ae`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **99**.
- State: Index **0**, WT **0**, U **0**, I **0**.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 06. 3e0b3082-8fb4-40d2-9128-ee40c907a4ad — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/3e0b3082-8fb4-40d2-9128-ee40c907a4ad`.
- HEAD: `528313c972e14ef72f784ada0284ac7fdf5a5d82`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **205**.
- State: Index **38**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  README.md`, `A  docs/release/0.2.0/MIGRATION.md`, `A  docs/release/0.2.0/RELEASE_NOTES.md`, `A  docs/release/0.2.0/evidence/inno-staged-swap-spike.md`, `A  docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png`. Partial list; index/worktree distinctions must survive any future disposition.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 07. 65864db3-6edc-4845-8100-cea6bad7649f — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/65864db3-6edc-4845-8100-cea6bad7649f`.
- HEAD: `528313c972e14ef72f784ada0284ac7fdf5a5d82`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **205**.
- State: Index **38**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  README.md`, `A  docs/release/0.2.0/MIGRATION.md`, `A  docs/release/0.2.0/RELEASE_NOTES.md`, `A  docs/release/0.2.0/evidence/inno-staged-swap-spike.md`, `A  docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png`. Partial list; index/worktree distinctions must survive any future disposition.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 08. b01d1df5-22eb-4f94-b852-1dcb09e1aeb2 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/b01d1df5-22eb-4f94-b852-1dcb09e1aeb2`.
- HEAD: `7a2ea0eacf19de8c6b3f0f45e6997a9e8d631ae9`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **124**.
- State: Index **4**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  openspec/changes/release-and-smoke-test-0-2-0/apply-progress.md`, `M  openspec/changes/release-and-smoke-test-0-2-0/tasks.md`, `M  src/yasb_limitora/_config_lock.py`, `M  tests/test_config_lock.py`.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 09. df645544-445e-44aa-b35b-0fcc5598954d — AMBIGUOUS

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/df645544-445e-44aa-b35b-0fcc5598954d`.
- HEAD: `3019d7f8a2aff05511161d583b46b26b91c4cf21`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **51**.
- State: Index **1**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `A  AGENTS.md`.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 10. e6572f98-5b2a-4351-bd26-e02783b83443 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/e6572f98-5b2a-4351-bd26-e02783b83443`.
- HEAD: `528313c972e14ef72f784ada0284ac7fdf5a5d82`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **205**.
- State: Index **38**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  README.md`, `A  docs/release/0.2.0/MIGRATION.md`, `A  docs/release/0.2.0/RELEASE_NOTES.md`, `A  docs/release/0.2.0/evidence/inno-staged-swap-spike.md`, `A  docs/release/0.2.0/evidence/spacepath-spike-widget-r3.png`. Partial list; index/worktree distinctions must survive any future disposition.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 11. ec0f02df-905a-4816-b99f-6ced807c5b45 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/ec0f02df-905a-4816-b99f-6ced807c5b45`.
- HEAD: `584e5b25bf6e97fbc68898850a00d4e4bf8b428d`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **133**.
- State: Index **5**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  openspec/changes/release-and-smoke-test-0-2-0/decomposition.md`, `M  openspec/changes/release-and-smoke-test-0-2-0/design.md`, `M  openspec/changes/release-and-smoke-test-0-2-0/tasks.md`, `A  src/yasb_limitora/_config_lock.py`, `A  tests/test_config_lock.py`.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 12. fecc0b18-e732-4325-b126-d6c81a8e56b1 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora/.git/gentle-ai/candidate-views/fecc0b18-e732-4325-b126-d6c81a8e56b1`.
- HEAD: `528313c972e14ef72f784ada0284ac7fdf5a5d82`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **205**.
- State: Index **26**, WT **0**, U **0**, I **0**.
- Tracked-state examples (XY porcelain status): `M  README.md`, `A  docs/release/0.2.0/MIGRATION.md`, `A  docs/release/0.2.0/RELEASE_NOTES.md`, `A  docs/release/0.2.0/evidence/inno-staged-swap-spike.md`, `M  docs/roadmap.md`. Partial list; index/worktree distinctions must survive any future disposition.
- Retention/removal condition: controller-owned candidate state; lifecycle/supersession unassigned. Keep until terminal ownership and a permitted disposal route are demonstrated and the maintainer authorizes removal.

### 13. yasb-limitora-304 — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-304`.
- HEAD: `8d8f157fccae0fd7b8d8bab6be8c44b6009ca474`.
- Branch: `feat/issue-304-reusable-vm-harness`.
- Commits outside main: **0**; behind main: **73**.
- State: Index **0**, WT **0**, U **60**, I **100**.
- Untracked examples: `proof-harness/host/artifacts/inno-task-consent-diagnostic-r1/20261003T112409Z-402a2f9b28e6491b806c348ddde5a0c8-evidence.vhdx`, `proof-harness/host/artifacts/inno-task-consent-diagnostic-r1/20261003T112409Z-402a2f9b28e6491b806c348ddde5a0c8-inputs.vhdx`, `proof-harness/host/artifacts/inno-task-consent-diagnostic-r1/existing-state-read-20261004T010942Z-44701cf03fa54b419e1769e5a4829863/evidence.vhdx`, `proof-harness/host/artifacts/inno-task-consent-diagnostic-r1/existing-state-read-20261004T010942Z-44701cf03fa54b419e1769e5a4829863/final-readback/path-inspection-collected.json`, `proof-harness/host/artifacts/inno-task-consent-diagnostic-r1/existing-state-read-20261004T010942Z-44701cf03fa54b419e1769e5a4829863/final-readback/path-ownership.json`. Partial list; no disposable inference.
- Ignored groups: `.atl` (2), `.codegraph` (3), `.pytest_cache` (5), `.ruff_cache` (8), `build` (66), `proof-harness` (10), `tests` (6). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 14. yasb-limitora-approved-import-proof — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-approved-import-proof`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `chore/approved-import-proof`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **1**, U **6**, I **21966**.
- Tracked-state examples (XY porcelain status): ` M scripts/README.md`.
- Untracked examples: `docs/approved-import-proof.md`, `odd/tasks/approved-import-proof.md`, `scripts/approved_import_preflight.py`, `scripts/prepare_approved_environment.py`, `tests/test_approved_import_preflight.py`. Partial list; no disposable inference.
- Ignored groups: `.codegraph` (2), `.ruff_cache` (7), `build` (21957). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 15. yasb-limitora-c1-c4-integration — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c1-c4-integration`.
- HEAD: `298228a46bec452c483202c8518a332e78bd8c49`.
- Branch: `test/c1-c4-composition`.
- Commits outside main: **4**; behind main: **24**.
- State: Index **0**, WT **0**, U **0**, I **3546**.
- Ignored groups: `.ruff_cache` (7), `.venv` (3010), `build` (304), `tmp` (225). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 16. yasb-limitora-c1-cache-paths-candidate — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c1-cache-paths-candidate`.
- HEAD: `c7d80b0db2afa15b7982ad758770b7cfcd596ffa`.
- Branch: `fix/c1-temp-fixture`.
- Commits outside main: **0**; behind main: **22**.
- State: Index **0**, WT **0**, U **0**, I **267**.
- Ignored groups: `.ruff_cache` (7), `build` (260). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 17. yasb-limitora-c2-diagnostic-paths-candidate — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c2-diagnostic-paths-candidate`.
- HEAD: `9a4187b8b0160619117a8769293fee46336726e5`.
- Branch: `DETACHED (no branch)`.
- Commits outside main: **0**; behind main: **23**.
- State: Index **0**, WT **0**, U **0**, I **157**.
- Ignored groups: `.ruff_cache` (3), `build` (154). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 18. yasb-limitora-c4-correction — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-correction`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `fix/c4-diagnostic-persistence`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **2**, U **3**, I **308**.
- Tracked-state examples (XY porcelain status): ` M proof-harness/README.md`, ` M proof-harness/guest/owned-cleanup/runner.ps1`.
- Untracked examples: `odd/tasks/c4-exception-fidelity.md`, `tests/powershell/test_c4_diagnostic_persistence.ps1`, `tests/test_c4_diagnostic_persistence.py`.
- Ignored groups: `build` (308). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 19. yasb-limitora-c4-updated-candidate — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-updated-candidate`.
- HEAD: `f5bd66fa17480fb71c5502e590ea89df329c8e01`.
- Branch: `proof/c4-updated-candidate`.
- Commits outside main: **0**; behind main: **27**.
- State: Index **0**, WT **3**, U **4**, I **7259**.
- Tracked-state examples (XY porcelain status): ` M .github/workflows/lint.yml`, ` M README.md`, ` M pyproject.toml`.
- Untracked examples: `odd/tasks/c4-diagnostic-native-rerun.md`, `odd/tasks/c4-runner-diagnostic-native-check.md`, `odd/tasks/c4-runner-error-boundary.md`, `odd/tasks/c4-updated-candidate.md`.
- Ignored groups: `build` (7259). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 20. yasb-limitora-c4-verification — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c4-verification`.
- HEAD: `8f2793246d39d3a09cf7bd39c7853db220f7e0cd`.
- Branch: `proof/c4-baseline-verification`.
- Commits outside main: **17**; behind main: **50**.
- State: Index **0**, WT **2**, U **3**, I **878**.
- Tracked-state examples (XY porcelain status): ` M tests/test_setup_assist_path.py`, ` M tests/test_setup_assist_protocol.py`.
- Untracked examples: `odd/tasks/c4-baseline-verification.md`, `odd/tasks/inno-task-consent-diagnostic.md`, `odd/tasks/modern-path-proof-runner.md`.
- Ignored groups: `.ruff_cache` (3), `build` (872), `src` (3). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 21. yasb-limitora-c5-consolidated-candidate — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c5-consolidated-candidate`.
- HEAD: `c5bea4c9ddf0642cf06b360f19e7da406e2e2625`.
- Branch: `fix/c5-observability-consolidated`.
- Commits outside main: **0**; behind main: **12**.
- State: Index **0**, WT **0**, U **0**, I **215**.
- Ignored groups: `.ruff_cache` (7), `build` (46), `tmp` (162). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 22. yasb-limitora-c5-ipc-observability-candidate — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c5-ipc-observability-candidate`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `fix/c5-ipc-observability`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **0**, U **1**, I **2**.
- Untracked examples: `tests/test_native_proof_observability.py`.
- Ignored groups: `build` (2). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 23. yasb-limitora-c6-premapping — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c6-premapping`.
- HEAD: `f9505932be7ed3a6a67e0609b399a48706a554c3`.
- Branch: `feat/pre-mapping-provider-error-observability`.
- Commits outside main: **0**; behind main: **1**.
- State: Index **0**, WT **0**, U **0**, I **24**.
- Ignored groups: `.ruff_cache` (7), `build` (17). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 24. yasb-limitora-c7-artifact-scanner-candidate — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c7-artifact-scanner-candidate`.
- HEAD: `f334b27488e772d3f54b884f738a082facd3881b`.
- Branch: `fix/c7-native-artifact-scanner`.
- Commits outside main: **0**; behind main: **23**.
- State: Index **0**, WT **0**, U **1**, I **70**.
- Untracked examples: `odd/tasks/c7-c5-c8-delivery.md`.
- Ignored groups: `.ruff_cache` (7), `build` (10), `tmp` (53). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 25. yasb-limitora-c8-import-evidence-candidate — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c8-import-evidence-candidate`.
- HEAD: `386a0542d25c494c8a245188aa0f06fc432c7a7f`.
- Branch: `fix/c8-helper-import-evidence`.
- Commits outside main: **0**; behind main: **10**.
- State: Index **0**, WT **0**, U **1**, I **148**.
- Untracked examples: `odd/tasks/exception-fidelity-reconciliation.md`.
- Ignored groups: `.ruff_cache` (7), `build` (72), `tmp` (69). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 26. yasb-limitora-c9-preflight — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-c9-preflight`.
- HEAD: `aec3c0283b85c75da88ae7262bef73c2ea932041`.
- Branch: `chore/approved-source-preflight`.
- Commits outside main: **0**; behind main: **3**.
- State: Index **0**, WT **0**, U **1**, I **1697**.
- Untracked examples: `odd/tasks/c6-rederivation.md`.
- Ignored groups: `.ruff_cache` (7), `build` (1690). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 27. yasb-limitora-cache-marker-fix — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-cache-marker-fix`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `fix/cache-marker-publication`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **201**, WT **0**, U **222**, I **2976**.
- Tracked-state examples (XY porcelain status): `D  .gitattributes`, `D  .github/workflows/lint.yml`, `D  .github/workflows/windows-proof-functions.ps1`, `D  .github/workflows/windows-proof.yml`, `D  .gitignore`. Partial list; index/worktree distinctions must survive any future disposition.
- Untracked examples: `.gitattributes`, `.github/workflows/lint.yml`, `.github/workflows/windows-proof-functions.ps1`, `.github/workflows/windows-proof.yml`, `.gitignore`. Partial list; no disposable inference.
- Ignored groups: `.codegraph` (2), `.pytest_cache` (5), `.ruff_cache` (7), `build` (2873), `packaging` (1), `scripts` (5), `src` (27), `tests` (56). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 28. yasb-limitora-docs — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-docs`.
- HEAD: `203fe27190e1863df2711b6afd3fec7fbd1b3798`.
- Branch: `docs/installation-guide-coherence`.
- Commits outside main: **1**; behind main: **50**.
- State: Index **0**, WT **0**, U **2**, I **1618**.
- Untracked examples: `native-proof.json`, `native-proof.xml`.
- Ignored groups: `.pytest_cache` (5), `.venv` (1526), `full-suite.raw.log` (1), `native-proof.raw.log` (1), `scripts` (5), `src` (32), `tests` (48). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 29. yasb-limitora-exception-fidelity — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-exception-fidelity`.
- HEAD: `95ea16018c3286e59091191d162abebfe72d82e4`.
- Branch: `fix/exception-fidelity-a1`.
- Commits outside main: **0**; behind main: **8**.
- State: Index **0**, WT **0**, U **2**, I **186**.
- Untracked examples: `odd/tasks/exception-fidelity-a1-a2.md`, `odd/tasks/phase-closure.md`.
- Ignored groups: `.ruff_cache` (7), `build` (179). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 30. yasb-limitora-i1-hermetic-ab — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-i1-hermetic-ab`.
- HEAD: `f5bd66fa17480fb71c5502e590ea89df329c8e01`.
- Branch: `test/i1-hermetic-ab`.
- Commits outside main: **0**; behind main: **27**.
- State: Index **0**, WT **0**, U **71**, I **115**.
- Untracked examples: `.h2-i1-ab-20260625-6d4c1f/A/src/yasb_limitora/__init__.py`, `.h2-i1-ab-20260625-6d4c1f/A/src/yasb_limitora/__main__.py`, `.h2-i1-ab-20260625-6d4c1f/A/src/yasb_limitora/_codex_resource_core.py`, `.h2-i1-ab-20260625-6d4c1f/A/src/yasb_limitora/_config_lock.py`, `.h2-i1-ab-20260625-6d4c1f/A/src/yasb_limitora/_env_block.py`. Partial list; no disposable inference.
- Ignored groups: `build` (115). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 31. yasb-limitora-ipc-observability — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-observability`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `chore/ipc-fixture-observability`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **4**, U **4**, I **23**.
- Tracked-state examples (XY porcelain status): ` M src/yasb_limitora/codex_helper.py`, ` M src/yasb_limitora/codex_supervisor.py`, ` M tests/fixtures/windows_descendant.py`, ` M tests/test_windows_native_proof.py`.
- Untracked examples: `docs/native-proof-observability.md`, `odd/tasks/ipc-fixture-observability.md`, `src/yasb_limitora/_native_proof_observability.py`, `tests/test_native_proof_observability.py`.
- Ignored groups: `build` (23). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 32. yasb-limitora-ipc-observability-infrastructure — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-observability-infrastructure`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `chore/ipc-observability-infrastructure`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **5**, U **8**, I **1476**.
- Tracked-state examples (XY porcelain status): ` M src/yasb_limitora/codex_helper.py`, ` M src/yasb_limitora/codex_supervisor.py`, ` M src/yasb_limitora/limitora_api.py`, ` M tests/fixtures/windows_descendant.py`, ` M tests/test_windows_native_proof.py`.
- Untracked examples: `docs/native-artifact-scanner.md`, `docs/native-proof-observability.md`, `odd/tasks/ipc-observability-infrastructure.md`, `src/yasb_limitora/_native_proof_observability.py`, `tests/test_helper_bootstrap_import_evidence.py`. Partial list; no disposable inference.
- Ignored groups: `.ruff_cache` (4), `build` (1472). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 33. yasb-limitora-ipc-persistence-observability — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-ipc-persistence-observability`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `chore/ipc-persistence-observability`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **5**, U **5**, I **1141**.
- Tracked-state examples (XY porcelain status): ` M src/yasb_limitora/codex_helper.py`, ` M src/yasb_limitora/codex_supervisor.py`, ` M src/yasb_limitora/limitora_api.py`, ` M tests/fixtures/windows_descendant.py`, ` M tests/test_windows_native_proof.py`.
- Untracked examples: `docs/native-proof-observability.md`, `odd/tasks/ipc-persistence-boundary.md`, `src/yasb_limitora/_native_proof_observability.py`, `tests/test_ipc_persistence_observability.py`, `tests/test_native_proof_observability.py`.
- Ignored groups: `build` (1141). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 34. yasb-limitora-path-feature — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-path-feature`.
- HEAD: `8f2793246d39d3a09cf7bd39c7853db220f7e0cd`.
- Branch: `feat/path-installer-management`.
- Commits outside main: **17**; behind main: **50**.
- State: Index **0**, WT **0**, U **1**, I **283**.
- Untracked examples: `NUL`.
- Ignored groups: `.atl` (3), `.codegraph` (3), `.pytest_cache` (5), `.ruff_cache` (7), `build` (145), `scripts` (5), `src` (26), `tests` (89). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 35. yasb-limitora-path-step-trace — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-path-step-trace`.
- HEAD: `0b04d815a7f0315fb32ca1bff0746066ac06565b`.
- Branch: `chore/c4-path-step-trace`.
- Commits outside main: **0**; behind main: **24**.
- State: Index **0**, WT **4**, U **4**, I **5**.
- Tracked-state examples (XY porcelain status): ` M packaging/inno/SetupAssistant.isi`, ` M packaging/inno/yasb-limitora.iss`, ` M src/yasb_limitora/setup_assist.py`, ` M tests/test_inno_script.py`.
- Untracked examples: `docs/installer-path-step-trace.md`, `odd/tasks/installer-path-step-trace.md`, `src/yasb_limitora/_path_step_trace.py`, `tests/test_installer_path_trace.py`.
- Ignored groups: `.pytest_cache` (5). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 36. yasb-limitora-s11-residual-proof — KEEP

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11-residual-proof`.
- HEAD: `4705748e7a64af34a47528f4fa73f02f8f391f5e`.
- Branch: `fix/s11-consented-cleanup`.
- Commits outside main: **1**; behind main: **50**.
- State: Index **0**, WT **0**, U **4**, I **13653**.
- Untracked examples: `nul`, `nul.json`, `odd/tasks/inno-task-consent-diagnostic.md`, `odd/tasks/modern-path-proof-runner.md`.
- Ignored groups: `.atl` (3), `.codegraph` (3), `.pytest_cache` (5), `.ruff_cache` (17), `.venv` (1837), `build` (11712), `scripts` (5), `src` (26), `tests` (45). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 37. yasb-limitora-s11a-setup-assist — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11a-setup-assist`.
- HEAD: `5cc45b29abe4c7a393327f0af76bddf1a49ebed4`.
- Branch: `feat/s11a-installer-hardening`.
- Commits outside main: **0**; behind main: **97**.
- State: Index **0**, WT **0**, U **0**, I **3455**.
- Ignored groups: `.atl` (2), `.codegraph` (2), `.pytest_cache` (5), `.ruff_cache` (7), `.venv` (2949), `build` (348), `scripts` (4), `src` (58), `tests` (80). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 38. yasb-limitora-s11b-299 — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11b-299`.
- HEAD: `364d4bffc00d48b62ba31339b4eb5c39c1778c6f`.
- Branch: `feat/s11b-issue-299-closeout`.
- Commits outside main: **0**; behind main: **65**.
- State: Index **0**, WT **0**, U **0**, I **221**.
- Ignored groups: `.atl` (2), `.codegraph` (3), `.pytest_cache` (5), `.ruff_cache` (6), `build` (128), `proof-harness` (1), `scripts` (2), `src` (26), `tests` (48). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.

### 39. yasb-limitora-s11b-reconciled — ARCHIVE_PENDING

- Path: `F:/Vault/20_Desarrollo/20.10_Activos/yasb-limitora-s11b-reconciled`.
- HEAD: `d5a05069169892c3b567922077aea0226e25a6a7`.
- Branch: `build/c5-reproof`.
- Commits outside main: **0**; behind main: **79**.
- State: Index **0**, WT **0**, U **0**, I **467**.
- Ignored groups: `.atl` (2), `.codegraph` (3), `.pytest_cache` (5), `.ruff_cache` (8), `build` (307), `scripts` (10), `src` (52), `tests` (80). Ignored status is not evidence supersession.
- Retention/removal condition: see the named decision entry above; no removal is authorized by this snapshot.
