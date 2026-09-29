# Issue #311 — Introduce a scoped Ruff baseline

Objective: Add a reproducible, project-owned Ruff check that starts green and prevents newly introduced violations, without bulk cleanup or formatting.

Scope: Ruff version pin and rules in pyproject.toml, isolated CI lint workflow, local invocation documentation, and cache ignore. No source behavior changes or autofixes. Branch: chore/issue-311-ruff-baseline from main abe5e7d.

Constraints: Windows-only runtime dependency need not install in lint CI; baseline rules must pass across src and tests. No commit/push/PR without an explicit delivery decision. Config-only change has no meaningful RED; use a pre-change rule census and post-change checks.

Forecast: approximately 70 authored changed lines; one delivery slice. Route: delegated writer (multiple non-trivial config/CI/doc files); independent verification as appropriate.

Tasks:
- [x] T1: Pin Ruff and configure a clean correctness-focused rule subset. Pin 0.16.9; E9/F821/F822/F823 selected. Pre-change census: selected rules clean; full F had 27 findings. Writer observed `python -m ruff check .` passing.
- [x] T2: Add independent lint CI job, local invocation documentation and cache ignore. Writer added Ubuntu job with exact pin, README command and `.ruff_cache/` ignore; `git diff --check` passed. Parent inspected diff.
- [ ] T3: Verify full applicable test suite and inspect final diff/status. Independent verifier confirmed Ruff pass, pytest 1039 passed/21 skipped, diff check pass and intended five-file scope. Native review lineage `review-35b7e2f25802d0fd` remains in reviewer collection (not approved or acknowledged); remote CI unrun. Task remains open pending review closure and delivery decision.

Current: local checks green; native review pending, no commit recorded. Remote CI remains pending until a PR runs.
