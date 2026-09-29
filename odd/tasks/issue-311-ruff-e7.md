# Issue #311 — Adopt Ruff E7 in green PR slices

Objective: Remove pre-existing E7 findings without behavior changes; enable each rule only once its whole-tree count reaches zero. PRs merge independently into main and each stays below 400 authored diff lines. The issue stays open until all rules are gated and CI green.

Baseline: synced main 1c9a0a4, Ruff 0.16.9. `--isolated --select E7`: E701=151, E702=93 (65 distinct rows), E731=3; E704=0. Seven rows overlap E701/E702. Existing E9/F401/F821/F822/F823/F841 gate green. No unsafe autofix.

Delivery: sequential stacked-to-main PRs, no PR merges a red lint gate; Refs #311 until final closing PR. Forecast: E731 <60 changed lines, E702 <350, E701 tests <250, E701 source may approach 400; split source by subsystem if exact count exceeds 400. Count additions+deletions in each PR before publishing. Always resync from merged main before next slice.

Tasks:
- [ ] E731: Rewrote three assigned lambdas into two named functions with equivalent lazy invocation/callback semantics; enabled E731 after zero census. Writer and independent verifier: file-read 16 passed, full pytest 1044 passed/21 skipped, configured/E731 lint clean, diff check clean. Commit/review/PR/CI/merge/sync pending.
- [ ] E702: Split semicolon-separated statements in tests and windows-job source; preserve ordering/control flow, test affected paths. Add E702 only at zero. Commit, review, PR, CI, merge, sync; split if >400.
- [ ] E701 tests: Expand same-line suites in tests, keep E701 off until remaining source is clean. Focused/full tests, commit, review, PR, CI, merge, sync.
- [ ] E701 source: Expand same-line suites in source, protect Windows job ownership/control flow; add E701 at zero, full checks. Split into PRs if >400; final PR uses Closes #311 after CI, merge and sync.

Current: E731 implementation and local checks verified on chore/issue-311-ruff-e731; delivery pending. No push/PR yet.
