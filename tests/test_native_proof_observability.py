"""Hermetic tests for opt-in native-proof observations."""

from __future__ import annotations

import importlib.util
import io
import os
import runpy
import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import yasb_limitora._native_proof_observability as diagnostics
from yasb_limitora import codex_helper
from yasb_limitora.codex_helper import CodexHelperExecutor, _payload
from yasb_limitora.codex_supervisor import _DIAGNOSTICS_ENV, _environment
from yasb_limitora.model import ProviderKey, ProviderOutcome, ProviderState, ProviderView, SafeError, SafeErrorCode


def _read(root, role="executor"):
    return diagnostics.events(root / f"{role}.jsonl")


def _executor(monkeypatch, root, *, acquire=None, write=None, response=None, close=None, process=None):
    expected = ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)

    class Transport:
        def write_control(self, payload, *, timeout_seconds):
            if write:
                write(payload)

        def read_response(self, timeout_seconds):
            if response:
                return response()
            return _payload(expected)

    monkeypatch.setattr("yasb_limitora.codex_helper._PersistentTransport", lambda *args, **kwargs: Transport())

    def factory(**kwargs):
        kwargs["transport_factory"](1, 2, nonblocking=True)
        return SimpleNamespace(
            _nonce=b"nonce",
            _diagnostic_process=process,
            acquire=acquire or (lambda: None),
            close=close or (lambda timeout: None),
        )

    return CodexHelperExecutor(factory, diagnostic_root=root), expected


def test_executor_operation_succeeds_and_records_actual_hooks(monkeypatch, tmp_path):
    executor, expected = _executor(monkeypatch, tmp_path)
    result = executor.run(("fixture-runner",))
    assert result == expected
    events = _read(tmp_path)
    names = [item["event"] for item in events]
    assert "executor_started" in names
    assert "supervisor_hooks_unavailable" in names
    assert "ready_observed" in names
    assert "request_emitted" in names
    assert "cleanup_completed" in names
    assert [item["monotonic_ns"] for item in events] == sorted(item["monotonic_ns"] for item in events)


def test_helper_not_started_is_distinct_from_ready_absent(monkeypatch, tmp_path):
    def fail_factory(**kwargs):
        raise RuntimeError("must not leak this diagnostic")

    result = CodexHelperExecutor(fail_factory, diagnostic_root=tmp_path).run(("runner",))
    assert result.error is not None
    events = _read(tmp_path)
    assert any(item["failure_stage"] == "startup" for item in events if item["event"] == "original_exception")
    assert not any(item["event"] == "helper_started" for item in diagnostics.events(tmp_path / "supervisor.jsonl"))
    assert not any(item["event"] == "ready_observed" for item in events)
    assert "must not leak" not in (tmp_path / "executor.jsonl").read_text(encoding="utf-8")


def test_ready_absent_after_supervisor_acquire_failure(monkeypatch, tmp_path):
    def fail_acquire():
        raise TimeoutError("private startup detail")

    executor, _ = _executor(monkeypatch, tmp_path, acquire=fail_acquire)
    result = executor.run(("runner",))
    assert result.error is not None
    events = _read(tmp_path)
    assert any(item.get("failure_stage") == "startup" for item in events if item["event"] == "original_exception")
    assert not any(item["event"] == "ready_observed" for item in events)


def test_request_absent_after_ready_and_write_failure(monkeypatch, tmp_path):
    def fail_write(_payload):
        raise OSError("private pipe detail")

    executor, _ = _executor(monkeypatch, tmp_path, write=fail_write)
    result = executor.run(("runner",))
    assert result.error is not None
    names = [item["event"] for item in _read(tmp_path)]
    assert "ready_observed" in names
    assert "original_exception" in names
    assert "request_emitted" not in names


@pytest.mark.parametrize("frozen", (False, True))
def test_frozen_and_nonfrozen_bootstraps_emit_ready_observation(monkeypatch, tmp_path, frozen):
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    handles = {gate_read: gate_read, data_write: data_write}
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(open_osfhandle=lambda handle, _flags: handles[handle]))
    monkeypatch.setattr(runpy, "run_module", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(codex_helper, "_child_main", lambda: None)
    for key, value in ((codex_helper._GATE, str(gate_read)), (codex_helper._DATA, str(data_write)), ("_YASB_CODEX_READY_NONCE", "nonce"), (diagnostics._ENV_ROOT, str(tmp_path))):
        monkeypatch.setenv(key, value)
    os.write(gate_write, b"1")
    try:
        if frozen:
            codex_helper._run_frozen_helper_bootstrap()
        else:
            exec(codex_helper._CHILD_BOOTSTRAP, {})
        assert os.read(data_read, len(b"READY:nonce")) == b"READY:nonce"
        rows = diagnostics.events(tmp_path / "helper.jsonl")
        assert [row["event"] for row in rows] == ["ready_emitted"]
    finally:
        for fd in (gate_read, gate_write, data_read, data_write):
            os.close(fd)


def test_supervisor_start_and_ready_hooks_use_injected_fake_process(monkeypatch, tmp_path):
    from tests.test_codex_supervisor import _prepared_supervisor

    events = []
    ready = SimpleNamespace(write_control=lambda *_args, **_kwargs: None, read_frame=lambda **_kwargs: b"READY:test")
    supervisor, _, _ = _prepared_supervisor(
        monkeypatch, events, transport_factory=lambda *_args, **_kwargs: ready
    )
    supervisor._diagnostic_root = tmp_path
    supervisor.acquire(nonce=b"test")
    rows = diagnostics.events(tmp_path / "supervisor.jsonl")
    assert [row["event"] for row in rows] == ["helper_started", "ready_observed"]
    assert all(row["state"] == "alive" and "pid" not in row for row in rows)
    supervisor.close()


def test_supervisor_start_failure_is_reported_without_raw_exception(monkeypatch, tmp_path):
    from tests.test_codex_supervisor import _prepared_supervisor
    from yasb_limitora.codex_supervisor import _AcquisitionError

    supervisor, _, _ = _prepared_supervisor(monkeypatch, [])
    supervisor._diagnostic_root = tmp_path
    supervisor._popen_factory = lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("secret path"))
    with pytest.raises(_AcquisitionError):
        supervisor.acquire(nonce=b"test")
    row = diagnostics.events(tmp_path / "supervisor.jsonl")[0]
    assert row["event"] == "helper_start_failed"
    assert row["error_type"] == "FileNotFoundError"
    assert b"secret path" not in (tmp_path / "supervisor.jsonl").read_bytes()


def test_authorization_unprocessed_by_real_child_request_hook(monkeypatch, tmp_path):
    from yasb_limitora.codex_helper import _child_main

    request = json.dumps({"nonce": "wrong", "runner": ["secret-argv"]}).encode()
    frames = iter((len(request).to_bytes(4, "big"), request))
    writes = []
    monkeypatch.setenv("_YASB_CODEX_GATE_HANDLE", "10")
    monkeypatch.setenv("_YASB_CODEX_DATA_HANDLE", "11")
    monkeypatch.setenv("_YASB_HELPER_NONCE", "expected")
    monkeypatch.setenv(diagnostics._ENV_ROOT, str(tmp_path))
    monkeypatch.setattr("yasb_limitora.codex_helper._read_exact", lambda _fd, _size: next(frames))
    monkeypatch.setattr("yasb_limitora.codex_helper._write_all", lambda _fd, value: writes.append(value))
    monkeypatch.setattr("yasb_limitora.codex_helper.os.close", lambda _fd: None)
    _child_main()
    names = [item["event"] for item in _read(tmp_path, "helper")]
    assert "request_received" in names
    assert "authorization_processed" not in names
    assert writes
    assert b"secret-argv" not in (tmp_path / "helper.jsonl").read_bytes()


def test_premature_response_exit_preserves_safe_executor_failure(monkeypatch, tmp_path):
    def fail_response():
        raise EOFError("private response detail")

    executor, _ = _executor(monkeypatch, tmp_path, response=fail_response)
    result = executor.run(("runner",))
    assert result.error is not None
    row = next(item for item in _read(tmp_path) if item["event"] == "original_exception")
    assert row["failure_stage"] == "response"
    assert row["error_type"] == "EOFError"
    assert "private response" not in (tmp_path / "executor.jsonl").read_text(encoding="utf-8")


def test_cleanup_incomplete_does_not_replace_decoded_result(monkeypatch, tmp_path):
    def fail_close(_timeout):
        raise RuntimeError("private cleanup detail")

    executor, expected = _executor(monkeypatch, tmp_path, close=fail_close)
    assert executor.run(("runner",)) == expected
    names = [item["event"] for item in _read(tmp_path)]
    assert "cleanup_started" in names
    assert "cleanup_incomplete" in names
    assert "executor_result" in names
    result_row = next(item for item in _read(tmp_path) if item["event"] == "executor_result")
    assert result_row["state"] == "unavailable"
    assert result_row["outcome"] == "undetected"
    assert result_row["error_code"] == "none"


def test_executor_result_keeps_safe_error_separate_from_not_run(monkeypatch, tmp_path):
    expected = ProviderView(
        ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.PROVIDER_ERROR),
        outcome=ProviderOutcome.EXECUTION_ERROR,
    )
    executor, _ = _executor(monkeypatch, tmp_path, response=lambda: _payload(expected))
    assert executor.run(("runner",)) == expected
    row = next(item for item in _read(tmp_path) if item["event"] == "executor_result")
    assert row["state"] == "safe_error"
    assert row["outcome"] == "execution_error"
    assert row["error_code"] == "provider_error"


def test_timeout_with_live_fake_process_keeps_liveness_unknown(monkeypatch, tmp_path):
    process = SimpleNamespace(returncode=None, is_alive=True)

    def timeout():
        assert process.is_alive
        raise TimeoutError("bounded wait expired")

    executor, _ = _executor(monkeypatch, tmp_path, response=timeout, process=process)
    result = executor.run(("runner",))
    assert result.error is not None
    events = _read(tmp_path)
    failure = next(item for item in events if item["event"] == "original_exception")
    assert failure["failure_stage"] == "response"
    assert not any(item["event"] == "helper_exit_observed" for item in diagnostics.events(tmp_path / "supervisor.jsonl"))
    summary = diagnostics.persist_snapshot(tmp_path)
    assert summary is not None
    assert json.loads(summary.read_text(encoding="ascii"))["roles"]["supervisor"]["process_status"] == "unknown"
    assert process.is_alive


@pytest.mark.parametrize("exit_code", (-1, 0xC0000005))
def test_available_signed_and_unsigned_process_exit_codes_are_preserved(monkeypatch, tmp_path, exit_code):
    process = SimpleNamespace(returncode=exit_code)
    executor, _ = _executor(monkeypatch, tmp_path, process=process)
    executor.run(("runner",))
    row = next(item for item in diagnostics.events(tmp_path / "supervisor.jsonl") if item["event"] == "helper_exit_observed")
    assert row["exit_code"] == exit_code


def test_fixture_hooks_report_requests_authorization_response_and_stream_counts(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "native_fixture_test", Path(__file__).parent / "fixtures" / "windows_descendant.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    marker = tmp_path / "descendant.marker"
    marker.touch()
    monkeypatch.setenv(diagnostics._ENV_ROOT, str(tmp_path))
    monkeypatch.setattr(fixture.subprocess, "Popen", lambda *_args, **_kwargs: SimpleNamespace(pid=123))
    monkeypatch.setattr(fixture.sys, "stdin", io.StringIO('{"id":1}\n{"id":2}\n'))
    monkeypatch.setattr(fixture.sys, "stdout", io.StringIO())

    fixture._run("success", tmp_path / "evidence.json", "", marker)

    rows = _read(tmp_path, "fixture")
    names = [item["event"] for item in rows]
    assert names.count("request_received") == 2
    assert names.count("authorization_processed") == 2
    assert "fixture_started" in names
    assert "response_emitted" in names
    assert any(item.get("stream") == "stdout" and item.get("byte_count", 0) > 0 for item in rows)
    assert b'"id":' not in (tmp_path / "fixture.jsonl").read_bytes()
    assert b"rateLimits" not in (tmp_path / "fixture.jsonl").read_bytes()


def test_timeout_fixture_keeps_any_nonempty_stdin_line_authorization(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "native_timeout_fixture_test", Path(__file__).parent / "fixtures" / "windows_descendant.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    marker = tmp_path / "descendant.marker"
    marker.touch()
    monkeypatch.setenv(diagnostics._ENV_ROOT, str(tmp_path))
    monkeypatch.setattr(fixture.subprocess, "Popen", lambda *_args, **_kwargs: SimpleNamespace(pid=123))
    monkeypatch.setattr(fixture.sys, "stdin", io.StringIO("any nonempty line\n"))

    class StopLoop(BaseException):
        pass

    monkeypatch.setattr(fixture.time, "sleep", lambda _seconds: (_ for _ in ()).throw(StopLoop()))
    with pytest.raises(StopLoop):
        fixture._run("timeout", tmp_path / "evidence.json", "", marker)
    names = [item["event"] for item in _read(tmp_path, "fixture")]
    assert "request_received" in names
    assert "authorization_processed" in names
    assert "stream_summary" in names


def test_private_sink_is_removed_from_inherited_environment_unless_explicit(tmp_path):
    source = {"PATH": "safe", _DIAGNOSTICS_ENV.lower(): "untrusted-destination"}
    defaults = _environment(source, gate_read=1, data_write=2, nonce=b"nonce")
    assert not any(key.casefold() == _DIAGNOSTICS_ENV.casefold() for key in defaults)
    enabled = _environment(
        source, gate_read=1, data_write=2, nonce=b"nonce", diagnostic_root=tmp_path
    )
    assert enabled[_DIAGNOSTICS_ENV] == str(tmp_path)


@pytest.mark.parametrize(("error_type", "recorded"), (("FileNotFoundError", "FileNotFoundError"), ("PrivateSecretException", "unknown")))
def test_exception_identity_is_allowlisted_with_explicit_unknown(error_type, recorded, tmp_path):
    diagnostics.record(tmp_path, "executor", "original_exception", error_type=error_type, failure_stage="response")
    row = _read(tmp_path)[0]
    assert row["error_type"] == recorded
    if recorded == "unknown":
        assert error_type.encode() not in (tmp_path / "executor.jsonl").read_bytes()


def test_concurrent_role_writers_remain_bounded_and_separate(tmp_path):
    import threading

    roles = ("executor", "supervisor", "helper", "fixture")
    threads = [threading.Thread(target=lambda role=role: [diagnostics.record(tmp_path, role, "executor_started") for _ in range(12)]) for role in roles]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for role in roles:
        rows = diagnostics.events(tmp_path / f"{role}.jsonl")
        assert len(rows) == 12
        assert all(row["role"] == role for row in rows)


def test_default_off_and_observer_failure_preserve_operation(monkeypatch, tmp_path):
    executor, expected = _executor(monkeypatch, None)
    assert executor.run(("runner",)) == expected
    assert not tuple(tmp_path.iterdir())

    monkeypatch.setattr(diagnostics, "record", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    executor, expected = _executor(monkeypatch, tmp_path)
    assert executor.run(("runner",)) == expected


def test_observations_are_bounded_allowlisted_and_snapshot_is_persisted(tmp_path):
    for index in range(100):
        diagnostics.record(tmp_path, "executor", "executor_started", pid=index, secret="do-not-record", argv="secret")
    path = tmp_path / "executor.jsonl"
    lines = path.read_text(encoding="ascii").splitlines()
    assert path.stat().st_size <= diagnostics._MAX_FILE_BYTES
    assert len(lines) == diagnostics._MAX_EVENTS
    assert json.loads(lines[-1])["event"] == "observer_truncated"
    assert b"secret" not in path.read_bytes()
    final = diagnostics.persist_snapshot(tmp_path)
    assert final is not None
    snapshot = json.loads(final.read_text(encoding="ascii"))
    role = snapshot["roles"]["executor"]
    assert role["facts"]["pid"] == diagnostics._MAX_EVENTS - 2
    assert role["truncated"] is True


def test_byte_cap_reserves_explicit_truncation_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnostics, "_MAX_FILE_BYTES", 420)
    for index in range(20):
        diagnostics.record(tmp_path, "fixture", "fixture_started", pid=index)
    path = tmp_path / "fixture.jsonl"
    assert path.stat().st_size <= 420
    assert diagnostics.events(path)[-1]["event"] == "observer_truncated"


def test_missing_fixture_evidence_persists_snapshot_before_original_failure(monkeypatch, tmp_path):
    from tests.test_windows_native_proof import _CHECKPOINT_ENV, _read_evidence

    executor, _ = _executor(monkeypatch, tmp_path)
    executor.run(("runner",))
    checkpoint = tmp_path / "checkpoint"
    checkpoint.write_bytes(b"4\n")
    monkeypatch.setenv(_CHECKPOINT_ENV, str(checkpoint))
    with pytest.raises(pytest.fail.Exception, match="native fixture did not reach the post-READY protocol boundary"):
        _read_evidence(tmp_path / "absent.json", timeout=0, diagnostic_root=tmp_path)
    snapshot = json.loads((tmp_path / "final-snapshot.json").read_text(encoding="ascii"))
    assert snapshot["checkpoint"] == "4"
    assert snapshot["roles"]["executor"]["executor_result"]["outcome"] == "undetected"
    assert snapshot["roles"]["fixture"]["process_status"] == "unknown"
    assert snapshot["roles"]["fixture"]["observation_status"] == "unknown"
