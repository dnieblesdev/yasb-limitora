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
- T11 [S7,S9,S10] delegated/parent done — 19 invariants, 14 AST-validated test node references, 5 explicit gaps and no embedded execution claims; 90 passed; this commit records outcome.
- T12 [S8,S9,S10] delegated/parent in_progress — harness failure/responsibility diagram; commit pending.
- T13 [S2-S4,S9-S10] parent pending — complete focused/full/lint/Ego verification, source tree custody and normal push to origin/main.

## Log

L1 — Maintainer request: "antes de hacer el incremento del atlas nos tenemos que preparar para los commits y subir los cambios, vamos a cambiar la ubicacion y colocar todos los diagramas en docs/diagramas/, cada diagrama le haces un commit, cuando lleguemos al incremento a cada punto del incremento una vez terminado le haces un commit, verificamos que todo este bien y hacemos push. tienes mi autorizacion para usar gh, no me vuelvas a pedir autorizacion si son cambios reversibles. dime el plan a ejecutar."

L2 — Branch correction: "yo creo que puedes trabajar directamente sobre main porque solo estamos haciendo esto asi que no abra conflictos y main esta sincronizado con el origin. entonces, solo commits, sin ramas, por cierto que haremos con los test ? donde meterlos ?" Final approval: "vamos con ese plan."

L3 — Preparation: main at 8e4bd60; authorized fetch confirms main...origin/main = 0/0, origin https://github.com/dnieblesdev/yasb-limitora.git; gh authenticated as dnieblesdev. Preserve existing untracked .build-worktrees/ and .playwright-mcp/. Use existing .venv Python (imports from this checkout, pytest8.4.2, Ruff0.17.0); default shell Python lacks editable package and will not be used.

L4 — Existing authored atlas is untracked in .build-worktrees/product-diagrams/docs/diagrams/product. Read-only source custody preserved until destination verification. Forecast approximately 2500-3500 authored changed lines across 13 coherent commits; user explicitly selected direct main commits and normal push, not PR delivery. No line-budget compression. Native review assessed at each committed candidate if enabled; historical runtime/proof evidence remains immutable.
