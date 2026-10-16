# Native proof IPC observability

The Windows native IPC proof supplies an explicit diagnostics root from its
test-owned scratch directory. The private API validates that it is absolute and
existing, but does not prove ownership; callers must not supply arbitrary existing
directories. Production CLI and JSON output are unchanged. With no root
configured, observers do not import the recorder, write sidecars, or add cleanup
work. Inherited copies of the sink environment variable are removed unless the
test explicitly opts in.

Each producer owns a fixed role file (`executor.jsonl`, `supervisor.jsonl`,
`helper.jsonl`, or `fixture.jsonl`). Records contain an allowlisted event,
monotonic timestamp, and available safe facts such as PID, exit code, failure
stage, outcome, and observed byte counts for known fixture streams. Each role
file is capped at 16 KiB and 64 lines (at most 63 observations plus an explicit
capacity marker). Snapshot output aggregates last-known per-role facts, reports
truncation, and leaves unavailable current process status as `unknown`. No
arguments, environment values, provider messages, raw stream bytes, exception
messages, or payload digests are recorded. Missing events mean unknown, not proof that a stage failed or did not
occur. Producer-emitted events remain distinct from parent-observed READY and
executor events.

The helper READY-emitted hook exists in both the isolated non-frozen bootstrap
and frozen internal-helper bootstrap. The supervisor records helper creation
and READY observation. The helper records validated request receipt,
authorization processing, and response emission. The fixture records start,
request receipt, authorization processing, response emission, and byte counts
for its known stdin/stdout/stderr writes. The executor records bounded result,
original exception type and failure stage, and cleanup outcome. Sidecar failures
are best-effort and cannot replace the IPC result or original failure.

When the existing fixture evidence wait reaches its existing failure boundary,
the test reads the existing numeric checkpoint (if configured) and writes
`final-snapshot.json` from already available role records before issuing the same
`pytest.fail`. Snapshot collection performs no wait, join, process probe,
termination, or cleanup. Cleanup lifecycle evidence describes
the helper/supervisor; the fixture's independent process exit code is not
currently observed. Only an exit code already available from the helper's
`Popen.returncode` is recorded. Native Windows IPC execution is required to
validate frozen/non-frozen process propagation; hermetic tests do not establish
that native behavior.

The existing timeout-branch rule is deliberately preserved: any non-empty stdin
line authorizes that branch, independently of normal JSON request IDs. The
numeric CI checkpoints remain the original `1` through `9` byte contract.
