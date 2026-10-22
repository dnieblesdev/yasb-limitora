# Bilingual architecture atlas
Deliver the existing atlas and four responsibility-focused additions on `main`; direct-push delivery explicitly authorized by the maintainer.
Checks: `.venv/Scripts/python.exe -m pytest -q --strict-markers tests/test_diagrams.py`, full pytest, Ruff, and Ego browser. One foundation commit, eight diagram commits, four increment commits.

## Specs

- S1: "vamos a cambiar la ubicacion y colocar todos los diagramas en docs/diagramas/"
- S2: "cada diagrama le haces un commit, cuando lleguemos al incremento a cada punto del incremento una vez terminado le haces un commit, verificamos que todo este bien y hacemos push."
- S3: "tienes mi autorizacion para usar gh, no me vuelvas a pedir autorizacion si son cambios reversibles."
- S4: "yo creo que puedes trabajar directamente sobre main porque solo estamos haciendo esto asi que no abra conflictos y main esta sincronizado con el origin. entonces, solo commits, sin ramas, por cierto que haremos con los test ? donde meterlos ?" Approved plan: "vamos con ese plan." Tests reside in `tests/test_diagrams.py` as proposed and approved; no new branches, PR, force-push, or merge.
- S5: "Prioridad alta: máquina de estados del instalador\nLos diagramas actuales muestran la transacción principal, pero yo añadiría uno que enumere estados persistentes, condiciones de transición, interrupciones y recuperación. Es la parte más sensible a fallos parciales."
- S6: "Prioridad alta: matriz de propiedad de recursos\nIdentificar quién crea, modifica, conserva y elimina cada recurso: directorios de instalación, PATH, claves de registro, configuración, discos de prueba y checkpoints. Debería indicar también quién tiene autoridad para recuperarlos."
- S7: "Prioridad alta: vincular afirmaciones con pruebas\nCada invariante importante debería enlazarse con su implementación y una prueba verificable. Cuando no exista prueba, debe declararse como pendiente en vez de asumir cobertura."
- S8: "Prioridad media: fallos del harness\nAñadir un diagrama específico para timeout, guest sin apagado, fallo de extracción, evidencia incompleta y diferencias entre un fallo del escenario y uno de la infraestructura de prueba."
- S9: "La arquitectura no debería explicarnos solamente cómo funciona el sistema cuando todo sale bien, sino también quién conserva la responsabilidad cuando algo sale mal."
- S10: "que te parece si me permites tambien verlo en español osea que tenga una opcion que al darle se ponga el texto en español y otro para el ingles." Preserve the approved bilingual navigation, visual fixes and offline standalone documents; no runtime implementation changes or native proof claims.
- S11: "porque actualmente como referencia si le das clic no va, entonces si colocas el enlace de el documento pero del repositorio en github se puede ver y solventamos un poco este problema." Source references use existing published GitHub documents pinned to the implementation revision; atlas navigation stays local and rendering stays dependency-free.

## Tasks

- T0 [S1-S4,S10] delegated/parent done — foundation and progressive pytest migration; RED 5 missing-index failures, GREEN 7 passed / 4 explicitly empty future-page parametrizations; commit eecf66a (540 authored lines including tracking); native assessment unavailable due to unrelated untracked paths, ordinary structural checks passed.
- T1 [S1-S4,S10] delegated/parent done — purpose migrated, 15 passed / 1 not-yet-applicable proof parametrization; commit da43256; assessment unavailable (untracked paths).
- T2 [S1-S4,S10] delegated/parent done — structure migrated, 22 passed / 1 future proof parametrization; commit ece6928; assessment unavailable (untracked paths).
- T3 [S1-S4,S10] delegated/parent done — data journey migrated, 30 passed / 1 future proof parametrization; commit e6aec20; assessment unavailable (untracked paths).
- T4 [S1-S4,S10] delegated/parent done — installer transaction migrated, 37 passed / 1 future proof parametrization; commit b518e82; assessment unavailable (untracked paths).
- T5 [S1-S4,S10] delegated/parent done — setup assistance migrated, 44 passed / 1 future proof parametrization; commit 5478a7a; assessment unavailable (untracked paths).
- T6 [S1-S4,S10] delegated/parent done — harness migrated, 52 passed / no skips; commit a7a6eee; assessment unavailable (untracked paths).
- T7 [S1-S4,S10] delegated/parent done — proof boundaries migrated, 60 passed; commit bfb85fe; assessment unavailable (untracked paths).
- T8 [S1-S4,S10] delegated/parent done — combined diagram migrated, 68 passed / no ignored-worktree test dependency; commit a6a97e5; assessment unavailable (untracked paths).
- T9 [S5,S9,S10] delegated/parent done — persistent states and interruption, correct early Exit branch and pending native recovery; 75 passed; commit 13b5957; assessment unavailable (untracked paths).
- T10 [S6,S9,S10] delegated/parent done — 13-resource ownership/retention/recovery matrix, 82 passed; commit 3b70204; assessment unavailable (untracked paths).
- T11 [S7,S9,S10] delegated/parent done — 19 invariants, 14 AST-validated test node references, 5 explicit gaps and no embedded execution claims; 90 passed; commit 2fb5963; assessment unavailable (untracked paths).
- T12 [S8,S9,S10] delegated/parent done — failure/responsibility matrix, independent guest/host budgets and pending diagnostics; 97 passed; commit dcce156; assessment unavailable (untracked paths).
- T13 [S2-S4,S9-S10] parent blocked — maintainer decision required before push: final suite 1 failed / 1429 passed / 22 skipped; native helper fixture did not reach post-READY boundary. Atlas 101 tests, Ruff and Ego passed. Accessibility/verification commit records the exact result; push not performed.

- T14 [S7,S10-S11] delegated/parent done — 128 source anchors / 35 published repository files, full revision and line ranges preserved; RED 1 failed / 118 passed, GREEN 126 passed, Ruff and real Ego source click passed; this commit records outcome. Push decision remains blocked by T13.

## Log

L1 — Maintainer request: "antes de hacer el incremento del atlas nos tenemos que preparar para los commits y subir los cambios, vamos a cambiar la ubicacion y colocar todos los diagramas en docs/diagramas/, cada diagrama le haces un commit, cuando lleguemos al incremento a cada punto del incremento una vez terminado le haces un commit, verificamos que todo este bien y hacemos push. tienes mi autorizacion para usar gh, no me vuelvas a pedir autorizacion si son cambios reversibles. dime el plan a ejecutar."

L2 — Branch correction: "yo creo que puedes trabajar directamente sobre main porque solo estamos haciendo esto asi que no abra conflictos y main esta sincronizado con el origin. entonces, solo commits, sin ramas, por cierto que haremos con los test ? donde meterlos ?" Final approval: "vamos con ese plan."

L3 — Preparation: main at 8e4bd60; authorized fetch confirms main...origin/main = 0/0, origin https://github.com/dnieblesdev/yasb-limitora.git; gh authenticated as dnieblesdev. Preserve existing untracked .build-worktrees/ and .playwright-mcp/. Use existing .venv Python (imports from this checkout, pytest8.4.2, Ruff0.17.0); default shell Python lacks editable package and will not be used.

L4 — Existing authored atlas was untracked in .build-worktrees/product-diagrams/docs/diagrams/product. Source custody was preserved until destination verification. Forecast approximately 2500-3500 authored changed lines across 13 coherent commits; user explicitly selected direct main commits and normal push, not PR delivery. No line-budget compression. Native review assessment was unavailable at each committed candidate because of unrelated untracked paths; the returned plan required ordinary self-verification and no independent verifier. Historical runtime/proof evidence remains immutable.

L5 — Canonical atlas has 12 delivered views, 13 HTML files, and tests/test_diagrams.py. Ego task space 4 inspected real screenshots, ES/EN, all 12 card/previous/next routes, desktop/mobile widths down to 320px, no clipped node text, 279 existing local links and 14 AST-aligned test node IDs. No installer/VM/provider execution. HTTP preview is http://127.0.0.1:8767/index.html; source links intentionally require the surrounding checkout.

L6 — Ego's final advisory found one unnamed table region. A focused regression produced RED 1 failed / 3 passed; adding a translated region name, keyboard focus and role yielded GREEN 101 atlas tests and global Ruff pass. Ego task space 5 confirmed the Spanish accessible region name and tabindex=0. Final full-suite result: 1 failed / 1429 passed / 22 skipped. Failure: tests/test_windows_native_proof.py::test_native_helper_adapter_ipc_and_complete_job_tree_cleanup, timeout fixture did not reach the post-READY protocol boundary. No implementation failure diagnosis or flaky classification is claimed; the earlier run passed, but that does not explain this failure. No retries or weakened assertions. Skips: three non-Windows subprocess cases; missing S11a lifecycle harness; seventeen C5 cases lacking rebuilt setup fixture; one reparse case lacking Windows privilege. After successful destination verification, exactly the ten migrated source files were removed from the old worktree; existing __pycache__, build artifacts and unrelated worktrees remain untouched. No branch/worktree deletion.

L7 — Delivery held: origin/main unchanged since 8e4bd60 (fetch verified); thirteen planned local commits are present. Final accessibility/verification commit is authorized, but push awaits a maintainer decision: accept documentation delivery with the native failure explicitly disclosed, or separately authorize diagnosis before delivery. No push, PR, merge, review-switch changes or runtime fixes have occurred.

L8 — Maintainer: "que paso con el fallo ? por cierto ademas vi que colocas enlaces a fuentes, para estos enlaces si existen en github puedes colocarlos como fuente. porque actualmente como referencia si le das clic no va, entonces si colocas el enlace de el documento pero del repositorio en github se puede ver y solventamos un poco este problema." Failure remains undiagnosed; no new native retry authorized or performed. Source-link correction is separately authorized and does not resolve the push decision. Published reference baseline: 8e4bd6016ca99b4ef20e7eb3555b79525bba3a00.

L9 — Source-only references now open GitHub in a new tab at the published baseline and exact line range; diagram navigation stays local and loaded assets remain local. Authorized policy change updates source URL/range/AST validation without permitting remote fonts, scripts, images or embedded pages. GitHub tree API confirmed all 35 source paths and no source drift from the published revision. Ego space 6 clicked the installer-state source and opened the actual yasb-limitora.iss file/range on GitHub. Final atlas suite 126 passed; global Ruff passed. The native failure was not retried or diagnosed, and the full suite was not rerun for this separate documentation-only correction.
