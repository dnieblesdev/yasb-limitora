# Issue #311 — Expand Ruff F rules by bounded work units

Objective: Remediate latent Ruff F findings safely, then enable each rule only when clean. Keep each PR slice below 400 authored changed lines; no push/PR without delivery decision. Continue branch chore/issue-311-ruff-baseline after reviewed f07f5ce.

Census on f07f5ce: 25 F401 (5 ordinary imports, 20 isolation facade re-exports) and 2 F841 (side-effecting validation calls). No bulk autofix. Existing configured E9/F821/F822/F823 must remain green.

Route: multi-file writer for T1; dedicated work-unit commit per task. Test-first does not apply to import-only removal (no meaningful behavioral RED); verify scoped lint and tests. Changes to protocol validation require behavior tests first if applicable.

Tasks:
- [x] F1: Removed five ordinary unused imports from codex_process_resources.py, codex_supervisor.py, test_guard.py, test_windows_job.py. Writer and independent verifier: scoped F401 and configured Ruff pass; full pytest 1039 passed, 21 skipped; diff check clean. Import surfaces and ctypes callee checked. Commit: aae840b. Native review review-007cb645e02906b7 approved and acknowledged.
- [x] F2: Preserved all 20 facade re-exports through explicit `__all__`, with exact membership and identity regression test. Focused protocol tests: 21 passed; scoped F401/configured Ruff pass; full pytest 1040 passed, 21 skipped; independent verification and diff check passed. Commit: 02ab35b. Native review review-ed7179e3fc138455 approved and acknowledged.
- [x] F3: Enabled F401 for the entire tree with no exclusions. Independent check: configured Ruff and isolated F401 both pass; full pytest 1040 passed, 21 skipped; diff check passed. Commit: cf6ed58. Native review review-d665878e35db5c99 approved and acknowledged.
- [x] F4: Retained nonce/provider validation calls while removing unused bindings; added three rejection cases and enabled F841 without exclusions. Writer and independent verifier: protocol 24 passed; full suite 1043 passed, 21 skipped; F841-only and configured Ruff pass; diff check passes. Commit: 1193fb4. Native review review-e52934a7d1f4c065 approved and acknowledged.

Current: all four work units committed and locally verified. Native reviews approved and acknowledged. Full F scan passes; remote CI remains pending until PR. Forecast <150 authored changed lines across all tasks; revisit if projected PR slice crosses 400.
