"""Executable native Windows proof for the contained production chain."""

from __future__ import annotations

import ctypes
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import pytest

from yasb_limitora.cli import main
from yasb_limitora.codex_helper import CodexHelperExecutor
from yasb_limitora.isolation.windows_job import (
    WAIT_OBJECT_0,
    JobError,
    JobErrorCode,
    WindowsJobBoundary,
)
from yasb_limitora.model import (
    ProviderOutcome,
    ProviderState,
    ProviderView,
    PublicProviderState,
    SafeErrorCode,
    SnapshotFreshness,
)
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import V2Guard
from yasb_limitora.v2_path import V2FileError, canonicalize_v2_path, read_v2_config
from yasb_limitora.worker import cleanup_complete

TEST_SID = bytes((1, 1, 0, 0, 0, 0, 0, 5, 21, 0, 0, 0))


pytestmark = [
    pytest.mark.windows_native,
]

_FIXTURE = Path(__file__).with_name("fixtures") / "windows_descendant.py"
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_DESCENDANT_ATTEMPT = "descendant stderr attempted\n"
_CHECKPOINT_ENV = "YASB_NATIVE_CHECKPOINT_PATH"
(
    _CHECKPOINT_START,
    _CHECKPOINT_SUCCESS_EXECUTOR_RETURNED,
    _CHECKPOINT_SUCCESS_VALIDATED,
    _CHECKPOINT_SUCCESS_TREE_GONE,
    _CHECKPOINT_TIMEOUT_TREE_OBSERVED,
    _CHECKPOINT_TIMEOUT_VALIDATED,
    _CHECKPOINT_TIMEOUT_STATE_VALIDATED,
    _CHECKPOINT_TIMEOUT_TREE_GONE,
    _CHECKPOINT_FINAL_SCAN_COMPLETE,
) = range(1, 10)
_CHECKPOINT_PAYLOADS = {f"{stage}\n".encode("ascii"): str(stage) for stage in range(1, 10)}

class _OsStreamCapture:
    def __init__(self, root: Path, label: str) -> None:
        self.stdout_path = root / f"{label}-stdout.log"
        self.stderr_path = root / f"{label}-stderr.log"
        self._saved: dict[int, int] = {}
        self.stdout_bytes = b""
        self.stderr_bytes = b""

    def __enter__(self) -> _OsStreamCapture:  # noqa: PYI034 - Python 3.10-compatible Self annotation
        try:
            for fd, path in ((1, self.stdout_path), (2, self.stderr_path)):
                self._saved[fd] = os.dup(fd)
                sink = os.open(
                    os.fspath(path),
                    os.O_BINARY | os.O_CREAT | os.O_TRUNC | os.O_WRONLY
                    if hasattr(os, "O_BINARY")
                    else os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                    0o600,
                )
                os.dup2(sink, fd)
                os.close(sink)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        for fd, saved in self._saved.items():
            os.dup2(saved, fd)
            os.close(saved)
        self.stdout_bytes = self.stdout_path.read_bytes()
        self.stderr_bytes = self.stderr_path.read_bytes()

def _assert_streams_clean(capture: _OsStreamCapture) -> None:
    if capture.stdout_bytes or capture.stderr_bytes:
        raise AssertionError("native proof stream isolation failed")

def _assert_descendant_output_attempted(marker: Path) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not marker.exists():
        time.sleep(0.05)
    if not marker.exists() or marker.read_text(encoding="utf-8") != _DESCENDANT_ATTEMPT:
        raise AssertionError("native descendant output attempt was not observed")

def _write_checkpoint(stage: int) -> None:
    if f"{stage}\n".encode("ascii") not in _CHECKPOINT_PAYLOADS:
        raise AssertionError("native proof checkpoint unavailable")
    checkpoint_path = os.environ.get(_CHECKPOINT_ENV)
    if not checkpoint_path:
        return
    target = Path(checkpoint_path)
    temporary = target.with_name(f"{target.name}.tmp")
    try:
        with temporary.open("w", encoding="ascii", newline="\n") as stream:
            stream.write(f"{stage}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise AssertionError("native proof checkpoint unavailable") from error

def _classify_checkpoint(path: Path) -> str:
    try:
        return _CHECKPOINT_PAYLOADS.get(path.read_bytes(), "unknown")
    except FileNotFoundError:
        return "unknown"

def _process_is_running(pid: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE,
        False,
        pid,
    )
    if not handle:
        return False
    code = wintypes.DWORD()
    try:
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)

def _read_evidence(path: Path, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            time.sleep(0.05)
            continue
        if value.get("authorized"):
            return value
        time.sleep(0.05)
    pytest.fail("native fixture did not reach the post-READY protocol boundary")
    raise AssertionError("native fixture did not reach the post-READY protocol boundary")


def _record_int(record: dict[str, object], key: str) -> int:
    value = record[key]
    assert isinstance(value, int)
    return value

def test_read_evidence_retries_transient_permission_error(monkeypatch, tmp_path: Path) -> None:
    expected = {"authorized": True, "helper_pid": 1}
    attempts = 0

    def read_text(_path: Path, *, encoding: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("transient Windows sharing lock")
        assert encoding == "utf-8"
        return json.dumps(expected)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    assert _read_evidence(tmp_path / "evidence.json", timeout=0.1) == expected
    assert attempts == 2


def _assert_gone(pids: list[int]) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and any(_process_is_running(pid) for pid in pids):
        time.sleep(0.05)
    assert all(not _process_is_running(pid) for pid in pids)

def _runner(mode: str, evidence: Path, sentinel: str, descendant_marker: Path) -> tuple[str, ...]:
    return (sys.executable, str(_FIXTURE), mode, str(evidence), sentinel, str(descendant_marker))


def _assert_artifacts_are_sentinel_free(paths: tuple[Path, ...], sentinel: str) -> None:
    marker = sentinel.encode("ascii")
    for path in paths:
        if marker in path.read_bytes():
            raise AssertionError("native proof artifact scan failed")


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_helper_adapter_ipc_and_complete_job_tree_cleanup(tmp_path: Path) -> None:
    sentinel = "native-" + "redaction-sentinel"
    _write_checkpoint(_CHECKPOINT_START)
    success_evidence = tmp_path / "success.json"
    success_marker = tmp_path / "success-descendant.attempted"
    with _OsStreamCapture(tmp_path, "success") as success_streams:
        success = CodexHelperExecutor(timeout_seconds=5.0).run(
            _runner("success", success_evidence, sentinel, success_marker)
        )
    _write_checkpoint(_CHECKPOINT_SUCCESS_EXECUTOR_RETURNED)
    assert success.state is ProviderState.SUCCESS
    assert success.outcome is ProviderOutcome.SNAPSHOT
    assert success.snapshot is not None
    assert success.snapshot.public_state is PublicProviderState.AVAILABLE
    assert success.snapshot.freshness is SnapshotFreshness.FRESH
    assert success.snapshot.source_id == "codex-app-server-v2"
    assert len(success.snapshot.windows) == 2
    assert success.snapshot.windows[0].limit is not None
    assert success.snapshot.windows[0].remaining is not None
    _assert_streams_clean(success_streams)
    success_record = _read_evidence(success_evidence)
    assert success_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(success_marker)
    _write_checkpoint(_CHECKPOINT_SUCCESS_VALIDATED)
    success_pids = [_record_int(success_record, key) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
    _assert_gone(success_pids)
    _write_checkpoint(_CHECKPOINT_SUCCESS_TREE_GONE)

    timeout_evidence = tmp_path / "timeout.json"
    timeout_marker = tmp_path / "timeout-descendant.attempted"
    result: dict[str, object] = {}
    with _OsStreamCapture(tmp_path, "timeout") as timeout_streams:
        worker = threading.Thread(
            target=lambda: result.setdefault(
                "view",
                CodexHelperExecutor(timeout_seconds=5.0).run(
                    _runner("timeout", timeout_evidence, sentinel, timeout_marker)
                ),
            ),
            daemon=True,
        )
        worker.start()
        timeout_record = _read_evidence(timeout_evidence)
        timeout_pids = [_record_int(timeout_record, key) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
        assert all(_process_is_running(pid) for pid in timeout_pids)
        _write_checkpoint(_CHECKPOINT_TIMEOUT_TREE_OBSERVED)
        worker.join(10.0)
        assert not worker.is_alive()
        timeout_view = result["view"]
        assert isinstance(timeout_view, ProviderView)
        assert timeout_view.error is not None
    _assert_streams_clean(timeout_streams)
    timeout_error = timeout_view.error
    assert timeout_error is not None
    assert timeout_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(timeout_marker)
    _write_checkpoint(_CHECKPOINT_TIMEOUT_VALIDATED)
    assert timeout_view.state is ProviderState.SAFE_ERROR
    assert timeout_view.error.code is SafeErrorCode.TIMEOUT
    assert timeout_view.outcome is ProviderOutcome.EXECUTION_ERROR
    assert timeout_view.snapshot is None
    _write_checkpoint(_CHECKPOINT_TIMEOUT_STATE_VALIDATED)
    _assert_gone(timeout_pids)
    _write_checkpoint(_CHECKPOINT_TIMEOUT_TREE_GONE)

    v2_executor = CodexHelperExecutor(timeout_seconds=5.0)
    v2_result = v2_executor.run_with_deadline(
        _runner("success", tmp_path / "v2-codex.json", "v2-proof", tmp_path / "v2-codex-descendant.attempted"),
        DeadlineContext.from_seconds(10.0),
    )
    assert v2_result.state is ProviderState.SUCCESS, f"v2 provider error: {v2_result.error.code.value if v2_result.error else 'none'}"
    assert v2_result.outcome is ProviderOutcome.SNAPSHOT
    assert v2_result.snapshot is not None
    assert v2_executor._pending_supervisor is None
    assert cleanup_complete([], helpers=(v2_executor,))

    artifact_path = os.environ.get("YASB_NATIVE_EVIDENCE_PATH")
    if artifact_path:
        artifact = {
            "native": True,
            "ready_authorized": bool(success_record["authorized"] and timeout_record["authorized"]),
            "tree_terminated": True,
            "bounded_timeout_error": timeout_error.code.value,
            "streams_clean": not (
                success_streams.stdout_bytes
                or success_streams.stderr_bytes
                or timeout_streams.stdout_bytes
                or timeout_streams.stderr_bytes
            ),
        }
        Path(artifact_path).write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    _assert_artifacts_are_sentinel_free(tuple(tmp_path.iterdir()), sentinel)
    _write_checkpoint(_CHECKPOINT_FINAL_SCAN_COMPLETE)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_v2_default_configuration_reads_localappdata() -> None:
    real_localappdata = os.environ.get("LOCALAPPDATA")
    if not real_localappdata:
        pytest.fail("Windows native proof requires LOCALAPPDATA")
    temp_localappdata = Path(tempfile.mkdtemp(prefix="yasb-limitora-r7-", dir=real_localappdata))
    config_path = temp_localappdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"codex": {"enabled": False}, "opencode_go": {"enabled": False}}),
        encoding="utf-8",
    )
    stdout, stderr = io.BytesIO(), io.StringIO()
    try:
        assert main(
            [],
            environment={"LOCALAPPDATA": str(temp_localappdata)},
            stdout=stdout,
            stderr=stderr,
        ) == 0
        assert "version" not in json.loads(stdout.getvalue())
        assert stderr.getvalue() == ""
        assert str(config_path) not in stdout.getvalue().decode() + stderr.getvalue()
    finally:
        shutil.rmtree(temp_localappdata, ignore_errors=True)


@pytest.mark.skipif(os.name != "nt", reason="native Windows launcher contract requires Windows")
def test_native_yasb_limitora_launcher_contract(tmp_path: Path) -> None:
    launcher = Path(sys.prefix) / "Scripts" / "yasb-limitora.exe"
    assert launcher.is_file()
    config = tmp_path / "disabled.json"
    config.write_bytes(b'{"codex":{"enabled":false},"opencode_go":{"enabled":false}}')
    environment = os.environ.copy()
    environment["YASB_LIMITORA_CONFIG"] = str(config)

    def invoke(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [os.fspath(launcher), *args],
            env=environment,
            capture_output=True,
            timeout=10,
            check=False,
        )

    valid = invoke()
    expected = (
        Path(__file__).parents[1] / "examples/customwidget/fixtures/providers-disabled.json"
    ).read_bytes()
    document = json.loads(valid.stdout)
    leaves = ("compact_text", "alternate_text", "tooltip_text")
    assert valid.returncode == 0
    assert valid.stdout == expected
    assert valid.stderr == b""
    assert list(document) == ["execution_state", "execution_error", "providers"]
    assert "version" not in document
    assert all(
        all(
            leaf in provider
            and isinstance(provider[leaf], str)
            and provider[leaf]
            and "\r" not in provider[leaf]
            and "stderr" not in provider[leaf].lower()
            for leaf in leaves
        )
        for provider in document["providers"]
    )

    invalid_config = tmp_path / "invalid.json"
    invalid_config.write_text('{"codex":{"enabled":true}}', encoding="utf-8")
    environment["YASB_LIMITORA_CONFIG"] = str(invalid_config)
    invalid = invoke()
    environment["YASB_LIMITORA_CONFIG"] = str(config)
    invocation = invoke("--unsupported")
    assert invalid.returncode == 1
    assert json.loads(invalid.stdout)["providers"][0]["execution_error"] == {
        "code": "provider_failed",
        "phase": "provider",
    }
    assert invalid.stderr == b"yasb-limitora: runtime_error\r\n"
    assert str(invalid_config).encode() not in invalid.stdout + invalid.stderr
    assert invocation.returncode == 2
    assert json.loads(invocation.stdout)["execution_error"] == {
        "code": "invocation_invalid",
        "phase": "configuration",
    }
    assert invocation.stderr == b"yasb-limitora: invocation_invalid\r\n"
    assert b"unsupported" not in invocation.stdout + invocation.stderr


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_global_guard_privilege_competition_and_provider_barrier(tmp_path: Path) -> None:
    # The real Global\ mutex acquisition is the runner privilege proof.
    script = """import sys, time
from pathlib import Path
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError, V2Guard
path = sys.argv[1]
sentinel = Path(sys.argv[3])
def provider():
    sentinel.write_text("PROVIDER_STARTED\\n", encoding="ascii")
try:
    lease = V2Guard().acquire(path, DeadlineContext.from_seconds(float(sys.argv[2])))
    print("owned", flush=True)
    provider()
    if len(sys.argv) > 4: time.sleep(30)
except GuardError as error:
    print(error.code, flush=True)
"""
    path = str(tmp_path / "guard.json")
    owner_sentinel = str(tmp_path / "owner-provider.sentinel")
    blocked_sentinel = str(tmp_path / "blocked-provider.sentinel")
    first = subprocess.Popen([sys.executable, "-c", script, path, "5", owner_sentinel, "hold"], stdout=subprocess.PIPE, text=True)
    try:
        assert first.stdout is not None and first.stdout.readline().strip() == "owned"
        provider_deadline = time.monotonic() + 5
        while not Path(owner_sentinel).exists() and time.monotonic() < provider_deadline:
            time.sleep(0.01)
        assert Path(owner_sentinel).read_text(encoding="ascii") == "PROVIDER_STARTED\n"
        blocked = subprocess.run([sys.executable, "-c", script, path, "1", blocked_sentinel], capture_output=True, text=True, timeout=5, check=False)
        assert blocked.stdout.strip() == "guard_wait_timeout"
        assert not Path(blocked_sentinel).exists()
        first.terminate()
        first.wait(timeout=5)
        abandoned_sentinel = str(tmp_path / "abandoned-provider.sentinel")
        abandoned = subprocess.run([sys.executable, "-c", script, path, "5", abandoned_sentinel], capture_output=True, text=True, timeout=5, check=False)
        assert abandoned.stdout.strip() == "owned"
        assert Path(abandoned_sentinel).read_text(encoding="ascii") == "PROVIDER_STARTED\n"
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_path_and_file_limits_reject_before_provider_open(tmp_path: Path) -> None:
    context = DeadlineContext.from_seconds(5)
    with pytest.raises(ValueError):
        canonicalize_v2_path(r"\\server\share\config.json")
    with pytest.raises(ValueError):
        canonicalize_v2_path(r"\\?\C:\config.json")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 16_385)
    with pytest.raises(V2FileError):
        read_v2_config(oversized, context)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_release_fault_is_deterministic_and_sanitized() -> None:
    class Api:
        def CreateMutexW(self, *_): return 1
        def WaitForSingleObject(self, *_): return 0
        def ReleaseMutex(self, _): return False
        def CloseHandle(self, _): return True

    lease = V2Guard(api=Api(), sid_provider=lambda: TEST_SID).acquire(r"C:\native.json", DeadlineContext.from_seconds(1))
    assert lease.release() is False


def test_sentinel_scan_failure_diagnostics_are_redacted(tmp_path: Path) -> None:
    sentinel = "native-redaction-sentinel"
    unsafe = tmp_path / "unsafe-proof.txt"
    unsafe.write_bytes(sentinel.encode("ascii"))
    with pytest.raises(AssertionError) as error:
        _assert_artifacts_are_sentinel_free((unsafe,), sentinel)
    if sentinel in str(error.value):
        pytest.fail("sentinel escaped artifact-scan diagnostics")


def test_checkpoint_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "native-proof.checkpoint"
    for content, expected in ((b"1\n", "1"), (None, "unknown"), (b"arbitrary", "unknown")):
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)
        assert _classify_checkpoint(path) == expected
    monkeypatch.setenv(_CHECKPOINT_ENV, str(path))
    _write_checkpoint(_CHECKPOINT_START)
    _write_checkpoint(_CHECKPOINT_FINAL_SCAN_COMPLETE)
    assert path.read_bytes() == b"9\n"
    assert not path.with_name(f"{path.name}.tmp").exists()

    def fail_replace(source: str, target: str) -> None:
        raise OSError

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(AssertionError, match="native proof checkpoint unavailable"):
        _write_checkpoint(_CHECKPOINT_START)
    assert path.read_bytes() == b"9\n"
    assert not path.with_name(f"{path.name}.tmp").exists()


class _NestedJobApi:
    def create_job(self) -> Any:
        return "job"

    def make_non_inheritable(self, handle: Any) -> bool:
        return True

    def enable_kill_on_close(self, handle: Any) -> bool:
        return True

    def open_process(self, pid: int, access: int) -> Any:
        return "process"

    def is_process_in_job(self, process: Any, job: Any) -> bool:
        return job is None

    def assign(self, job: Any, process: Any) -> bool:
        raise AssertionError("nested containment must not authorize assignment")

    def query_active(self, job: Any) -> int:
        return 0

    def terminate(self, job: Any) -> bool:
        return True

    def terminate_process(self, process: Any) -> bool:
        return True

    def wait(self, handle: Any, timeout_ms: int) -> int:
        return WAIT_OBJECT_0

    def close(self, handle: Any) -> bool:
        return True


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_nested_job_is_explicit_safe_failure_without_authorization() -> None:
    boundary = WindowsJobBoundary(api=_NestedJobApi())
    with pytest.raises(JobError) as error:
        boundary.assign_process(1234)
    assert error.value.code is JobErrorCode.NESTED_JOB
    with pytest.raises(JobError):
        boundary.authorize()


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_supervisor_setup_failure_is_safe_and_does_not_run_runner() -> None:
    calls: list[str] = []

    def fail_before_authorization(**kwargs):
        calls.append("setup")
        raise JobError(JobErrorCode.ASSIGNMENT_FAILED)

    view = CodexHelperExecutor(fail_before_authorization).run((sys.executable, str(_FIXTURE), "success", "unused"))
    assert calls == ["setup"]
    assert view.state is ProviderState.SAFE_ERROR
    assert view.error is not None
    assert view.error.code is SafeErrorCode.PROVIDER_ERROR


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or sys.argv[1] != "--classify-checkpoint":
            raise ValueError
        print(_classify_checkpoint(Path(sys.argv[2])))
    except Exception:  # noqa: BLE001 - classifier fails closed
        raise SystemExit(1) from None
