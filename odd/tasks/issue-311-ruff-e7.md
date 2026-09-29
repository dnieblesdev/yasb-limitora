# Issue #311 — Adopt Ruff E7 in green PR slices

Objective: Remove pre-existing E7 findings without behavior changes; enable each rule only once its whole-tree count reaches zero. PRs merge independently into main and each stays below 400 authored diff lines. The issue stays open until all rules are gated and CI green.

Baseline: synced main 1c9a0a4, Ruff 0.16.9. `--isolated --select E7`: E701=151, E702=93 (65 distinct rows), E731=3; E704=0. Seven rows overlap E701/E702. Existing E9/F401/F821/F822/F823/F841 gate green. No unsafe autofix.

Delivery: sequential stacked-to-main PRs, no PR merges a red lint gate; Refs #311 until final closing PR. Forecast: E731 <60 changed lines, E702 <350, E701 tests <250, E701 source may approach 400; split source by subsystem if exact count exceeds 400. Count additions+deletions in each PR before publishing. Always resync from merged main before next slice.

Tasks:
- [x] E731: Three assigned lambdas replaced with two named functions; E731 gated. Commit 54ae9f0, native review approved/acknowledged, PR #323 merged as 49cb059 with ruff/native-proof green; main synced. Focused 16 and full pytest 1044 passed/21 skipped.
- [ ] E702: Split all 93 semicolon findings in tests and windows-job source, preserving ordering/control flow; enabled E702 at zero. Independent verifier: configured/E702 lint clean, full pytest 1044 passed/21 skipped, diff check clean, statement-level audit passed. Candidate 256 changed lines including this doc (<400). Commit/review/PR/CI/merge/sync pending.
- [ ] E701 tests: Expand same-line suites in tests, keep E701 off until remaining source is clean. Focused/full tests, commit, review, PR, CI, merge, sync.
- [ ] E701 source: Expand same-line suites in source, protect Windows job ownership/control flow; add E701 at zero, full checks. Split into PRs if >400; final PR uses Closes #311 after CI, merge and sync.

Current: E731 delivered; E702 implementation locally verified on chore/issue-311-ruff-e702 from main 49cb059. Delivery pending; E701 census must be refreshed after E702 merge.
