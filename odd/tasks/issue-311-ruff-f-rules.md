# Issue #311 — Expand Ruff F rules by bounded work units

Objective: Remediate latent Ruff F findings safely, then enable each rule only when clean. Keep each PR slice below 400 authored changed lines; no push/PR without delivery decision. Continue branch chore/issue-311-ruff-baseline after reviewed f07f5ce.

Census on f07f5ce: 25 F401 (5 ordinary imports, 20 isolation facade re-exports) and 2 F841 (side-effecting validation calls). No bulk autofix. Existing configured E9/F821/F822/F823 must remain green.

Route: multi-file writer for T1; dedicated work-unit commit per task. Test-first does not apply to import-only removal (no meaningful behavioral RED); verify scoped lint and tests. Changes to protocol validation require behavior tests first if applicable.

Tasks:
- [x] F1: Removed five ordinary unused imports from codex_process_resources.py, codex_supervisor.py, test_guard.py, test_windows_job.py. Writer and independent verifier: scoped F401 and configured Ruff pass; full pytest 1039 passed, 21 skipped; diff check clean. Import surfaces and ctypes callee checked. Commit: pending in this work-unit closure.
- [ ] F2: Preserve isolation public re-exports explicitly and resolve 20 facade F401 without API regression; check public imports/tests; commit.
- [ ] F3: Enable F401 in project lint once all findings are resolved; check CI command and full suite; commit.
- [ ] F4: Retain both validation calls while dropping F841 bindings, add/confirm focused regression tests, then enable F841; check full suite; commit.

Current: F1 verified; F2 next. Remote CI remains pending until PR. Forecast <150 authored changed lines across all tasks; revisit if projected PR slice crosses 400.
