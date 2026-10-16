"""Private, opt-in, bounded sidecar observations for native proof debugging."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_ENV_ROOT = "_YASB_NATIVE_PROOF_DIAGNOSTICS_ROOT"
_MAX_FILE_BYTES = 16_384
_MAX_LINE_BYTES = 512
_MAX_EVENTS = 64
_ROLES = frozenset(("executor", "supervisor", "helper", "fixture"))
_ERROR_TYPES = frozenset(("TimeoutError", "OSError", "FileNotFoundError", "PermissionError", "BrokenPipeError", "RuntimeError", "TypeError", "ValueError", "EOFError", "KeyError", "AttributeError", "AssertionError", "UnicodeError"))
_STATES = frozenset(("loading", "success", "unavailable", "safe_error", "alive", "exited", "unknown", "complete", "incomplete"))
_OUTCOMES = frozenset(("snapshot", "undetected", "not_run", "execution_error", "unknown"))
_ERROR_CODES = frozenset(("timeout", "provider_error", "internal_error", "configuration_invalid", "invocation_invalid", "invalid_provider_data", "unknown_provider_state", "guard_acquisition_failed", "guard_wait_timeout", "deadline_exhausted", "cleanup_failed", "none", "unknown"))
_EVENTS = frozenset(
    (
        "executor_started", "helper_start_requested", "helper_started", "helper_start_failed",
        "ready_emitted", "ready_observed", "request_emitted", "request_received", "stream_summary",
        "authorization_processed", "response_emitted", "executor_result", "original_exception",
        "cleanup_started", "cleanup_completed", "cleanup_incomplete", "fixture_started", "descendant_started", "helper_exit_observed", "observer_truncated", "supervisor_hooks_unavailable",
    )
)


def _root(value: object) -> Path | None:
    if not isinstance(value, (str, os.PathLike)):
        return None
    try:
        root = Path(value)
        return root if root.is_absolute() and root.is_dir() else None
    except (OSError, TypeError, ValueError):
        return None


def record(root: object, role: str, event: str, **facts: Any) -> None:
    """Fail-silent wrapper around all observer construction and I/O."""
    try:
        _record(root, role, event, **facts)
    except Exception:  # noqa: BLE001 - observer cannot replace its producer
        return


def _record(root: object, role: str, event: str, **facts: Any) -> None:
    """Append one allowlisted event to its role-owned sidecar."""
    if role not in _ROLES or event not in _EVENTS:
        return
    directory = _root(root)
    if directory is None:
        return
    safe: dict[str, object] = {
        "role": role,
        "event": event,
        "monotonic_ns": time.monotonic_ns(),
    }
    for key in ("pid", "child_pid"):
        value = facts.get(key)
        if type(value) is int and 0 <= value < 2**32:
            safe[key] = value
    exit_code = facts.get("exit_code")
    if type(exit_code) is int and -(2**31) <= exit_code <= 0xFFFFFFFF:
        safe["exit_code"] = exit_code
    byte_count = facts.get("byte_count")
    if type(byte_count) is int and 0 <= byte_count <= _MAX_FILE_BYTES:
        safe["byte_count"] = byte_count
    stream = facts.get("stream")
    if stream in ("stdin", "stdout", "stderr"):
        safe["stream"] = stream
    state = facts.get("state")
    if state in _STATES:
        safe["state"] = state
    stage = facts.get("failure_stage")
    if stage in ("startup", "ready", "request", "authorization", "response", "cleanup"):
        safe["failure_stage"] = stage
    if event in ("original_exception", "helper_start_failed", "cleanup_incomplete"):
        error_type = facts.get("error_type")
        safe["error_type"] = error_type if isinstance(error_type, str) and error_type in _ERROR_TYPES else "unknown"
    outcome = facts.get("outcome")
    if outcome in _OUTCOMES:
        safe["outcome"] = outcome
    error_code = facts.get("error_code")
    if event == "executor_result" and error_code is None:
        safe["error_code"] = "none"
    elif isinstance(error_code, str) and error_code in _ERROR_CODES:
        safe["error_code"] = error_code
    try:
        line = (json.dumps(safe, separators=(",", ":")) + "\n").encode("ascii")
        path = directory / f"{role}.jsonl"
        with path.open("a+b") as stream:
            stream.seek(0)
            prior = stream.read()
            count = prior.count(b"\n")
            if any(b'"event":"observer_truncated"' in row for row in prior.splitlines()):
                return
            marker = (json.dumps({"role": role, "event": "observer_truncated", "monotonic_ns": time.monotonic_ns(), "reason": "capacity"}, separators=(",", ":")) + "\n").encode("ascii")
            full = len(line) > _MAX_LINE_BYTES or count >= _MAX_EVENTS - 1 or len(prior) + len(line) + len(marker) > _MAX_FILE_BYTES
            stream.seek(0, os.SEEK_END)
            if full:
                if count < _MAX_EVENTS and len(prior) + len(marker) <= _MAX_FILE_BYTES:
                    stream.write(marker)
                return
            stream.write(line)
    except Exception:  # noqa: BLE001 - observer is deliberately fail-silent
        return


def record_from_environment(role: str, event: str, **facts: Any) -> None:
    """Best-effort child-side observation using only the explicit private root."""
    try:
        record(os.environ.get(_ENV_ROOT), role, event, **facts)
    except Exception:  # noqa: BLE001 - observer is deliberately fail-silent
        return


def _role_snapshot(directory: Path, role: str) -> dict[str, object]:
    path = directory / f"{role}.jsonl"
    rows = events(path)
    facts: dict[str, object] = {}
    stages: list[str] = []
    stream_counts: dict[str, int] = {}
    last_process_observation = None
    result = None
    for row in rows:
        event = row["event"]
        if event not in stages:
            stages.append(event)
        for key in ("pid", "child_pid", "exit_code"):
            if key in row:
                facts[key] = row[key]
        if row.get("stream") in ("stdin", "stdout", "stderr"):
            stream = row["stream"]
            stream_counts[stream] = stream_counts.get(stream, 0) + int(row.get("byte_count", 0))
        if row.get("state") in ("alive", "exited"):
            last_process_observation = {key: row[key] for key in ("event", "state", "pid", "child_pid", "monotonic_ns") if key in row}
        if event == "executor_result":
            result = {key: row[key] for key in ("state", "outcome", "error_code") if key in row}
    truncated = any(row["event"] == "observer_truncated" for row in rows)
    try:
        truncated = truncated or len(path.read_bytes().splitlines()) > _MAX_EVENTS
    except OSError:
        pass
    exited = role == "supervisor" and any(row["event"] == "helper_exit_observed" and type(row.get("exit_code")) is int for row in rows)
    return {
        "observation_status": "unknown" if not rows else "truncated" if truncated else "available",
        "events_observed": stages,
        "last_event": rows[-1] if rows else None,
        "facts": facts,
        "stream_byte_counts": stream_counts,
        "last_process_observation": last_process_observation,
        "process_status": "exited" if exited else "unknown",
        "executor_result": result,
        "truncated": truncated,
    }


def persist_snapshot(root: object, *, checkpoint: str = "unknown") -> Path | None:
    """Persist bounded role summaries and the existing checkpoint observation."""
    directory = _root(root)
    if directory is None:
        return None
    if checkpoint not in {"unknown", *(str(stage) for stage in range(1, 10))}:
        checkpoint = "unknown"
    try:
        snapshot = {
            "checkpoint": checkpoint,
            "roles": {role: _role_snapshot(directory, role) for role in sorted(_ROLES)},
        }
        payload = (json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        if len(payload) > _MAX_FILE_BYTES:
            return None
        target = directory / "final-snapshot.json"
        with target.open("wb") as stream:
            stream.write(payload)
        return target
    except Exception:  # noqa: BLE001 - final diagnostics never replace pytest's failure
        return None


def events(path: Path) -> tuple[dict[str, object], ...]:
    """Read a bounded sidecar snapshot for hermetic tests and native diagnostics."""
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return ()
        result = []
        for line in path.read_bytes().splitlines()[-_MAX_EVENTS:]:
            if len(line) > _MAX_LINE_BYTES:
                return ()
            item = json.loads(line)
            if type(item) is dict and item.get("event") in _EVENTS:
                result.append(item)
        return tuple(result)
    except Exception:  # noqa: BLE001 - corrupt observations remain unknown
        return ()
