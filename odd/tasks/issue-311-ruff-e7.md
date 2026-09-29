# Issue #311 — Adopt Ruff E7 in green PR slices

Objective: Remove pre-existing E7 findings without behavior changes; enable each rule only once its whole-tree count reaches zero. PRs merge independently into main and each stays below 400 authored diff lines. The issue stays open until all rules are gated and CI green.

Baseline: synced main 1c9a0a4, Ruff 0.16.9. `--isolated --select E7`: E701=151, E702=93 (65 distinct rows), E731=3; E704=0. Seven rows overlap E701/E702. Existing E9/F401/F821/F822/F823/F841 gate green. No unsafe autofix.

Delivery: sequential stacked-to-main PRs, no PR merges a red lint gate; Refs #311 until final closing PR. Forecast: E731 <60 changed lines, E702 <350, E701 tests <250, E701 source may approach 400; split source by subsystem if exact count exceeds 400. Count additions+deletions in each PR before publishing. Always resync from merged main before next slice.

Tasks:
- [x] E731: Three assigned lambdas replaced with two named functions; E731 gated. Commit 54ae9f0, native review approved/acknowledged, PR #323 merged as 49cb059 with ruff/native-proof green; main synced. Focused 16 and full pytest 1044 passed/21 skipped.
- [x] E702: Split 93 semicolon findings, preserving statement order; E702 gated. Commit 38f38f2, native review approved/acknowledged, PR #324 merged as 3375f92 with ruff/native-proof green; main synced. Full pytest 1044 passed/21 skipped, 258 changed lines (<400).
- [x] E701 tests: Expanded 52 same-line suites across five test files; E701 remains disabled. Commit f2c5d0b, native review approved/acknowledged, PR #325 merged as 0f677d1 with ruff/native-proof green; main synced. Full pytest 1044 passed/21 skipped, 162 changed lines (<400).
- [x] E701 source: Expanded 92 source findings; E701 gated after whole-tree zero. Commit 6903983, native review approved/acknowledged, PR #326 merged as 5caf9bd with ruff/native-proof green; main synced, #311 closed. Full pytest 1044 passed/21 skipped; 330 changed lines (<400).

Current: All four slices delivered and merged. Issue #311 closed by PR #326; main synced to 5caf9bd. Two nonblocking native review advisories remain separate follow-ups (codex_supervisor.py:819-821, codex_process_resources.py:123).
