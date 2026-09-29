# Issue #311 — Adopt Ruff E7 in green PR slices

Objective: Remove pre-existing E7 findings without behavior changes; enable each rule only once its whole-tree count reaches zero. PRs merge independently into main and each stays below 400 authored diff lines. The issue stays open until all rules are gated and CI green.

Baseline: synced main 1c9a0a4, Ruff 0.16.9. `--isolated --select E7`: E701=151, E702=93 (65 distinct rows), E731=3; E704=0. Seven rows overlap E701/E702. Existing E9/F401/F821/F822/F823/F841 gate green. No unsafe autofix.

Delivery: sequential stacked-to-main PRs, no PR merges a red lint gate; Refs #311 until final closing PR. Forecast: E731 <60 changed lines, E702 <350, E701 tests <250, E701 source may approach 400; split source by subsystem if exact count exceeds 400. Count additions+deletions in each PR before publishing. Always resync from merged main before next slice.

Tasks:
- [x] E731: Three assigned lambdas replaced with two named functions; E731 gated. Commit 54ae9f0, native review approved/acknowledged, PR #323 merged as 49cb059 with ruff/native-proof green; main synced. Focused 16 and full pytest 1044 passed/21 skipped.
- [x] E702: Split 93 semicolon findings, preserving statement order; E702 gated. Commit 38f38f2, native review approved/acknowledged, PR #324 merged as 3375f92 with ruff/native-proof green; main synced. Full pytest 1044 passed/21 skipped, 258 changed lines (<400).
- [ ] E701 tests: Expanded all 52 same-line suites in five test files; E701 remains disabled while 92 source findings remain. Independent verifier: test-scope E701 and configured Ruff clean, full pytest 1044 passed/21 skipped, diff check and line-by-line pairing clean. Candidate <400 changed lines. Commit/review/PR/CI/merge/sync pending.
- [ ] E701 source: Expand same-line suites in source, protect Windows job ownership/control flow; add E701 at zero, full checks. Split into PRs if >400; final PR uses Closes #311 after CI, merge and sync.

Current: E731 and E702 delivered. E701 tests locally verified on chore/issue-311-ruff-e701-tests from main 3375f92; delivery pending. Keep E701 disabled until 92 remaining source findings are resolved.
