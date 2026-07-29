"""Executable native Windows proof for the contained production chain."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

from yasb_limitora.codex_helper import CodexHelperExecutor
from yasb_limitora.isolation.windows_job import (
    WAIT_OBJECT_0,
    JobError,
    JobErrorCode,
    WindowsJobBoundary,
)
from yasb_limitora.model import ProviderState, SafeErrorCode


pytestmark = [
    pytest.mark.windows_native,
]

_FIXTURE = Path(__file__).with_name("fixtures") / "windows_descendant.py"
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_DESCENDANT_ATTEMPT = "descendant stderr attempted\n"


class _OsStreamCapture:
    def __init__(self, root: Path, label: str) -> None:
        self.stdout_path = root / f"{label}-stdout.log"
        self.stderr_path = root / f"{label}-stderr.log"
        self._saved: dict[int, int] = {}
        self.stdout_bytes = b""
        self.stderr_bytes = b""

    def __enter__(self) -> "_OsStreamCapture":
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
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.05)
            continue
        if value.get("authorized"):
            return value
        time.sleep(0.05)
    pytest.fail("native fixture did not reach the post-READY protocol boundary")


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
    sentinel = "native-redaction-sentinel"

    success_evidence = tmp_path / "success.json"
    success_marker = tmp_path / "success-descendant.attempted"
    with _OsStreamCapture(tmp_path, "success") as success_streams:
        success = CodexHelperExecutor(timeout_seconds=2.0).run(
            _runner("success", success_evidence, sentinel, success_marker)
        )
    assert success.state is ProviderState.SUCCESS
    _assert_streams_clean(success_streams)
    success_record = _read_evidence(success_evidence)
    assert success_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(success_marker)
    success_pids = [int(success_record[key]) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
    _assert_gone(success_pids)

    timeout_evidence = tmp_path / "timeout.json"
    timeout_marker = tmp_path / "timeout-descendant.attempted"
    result: dict[str, object] = {}
    with _OsStreamCapture(tmp_path, "timeout") as timeout_streams:
        worker = threading.Thread(
            target=lambda: result.setdefault(
                "view",
                CodexHelperExecutor(timeout_seconds=0.5).run(
                    _runner("timeout", timeout_evidence, sentinel, timeout_marker)
                ),
            ),
            daemon=True,
        )
        worker.start()
        timeout_record = _read_evidence(timeout_evidence)
        timeout_pids = [int(timeout_record[key]) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
        assert all(_process_is_running(pid) for pid in timeout_pids)
        worker.join(5.0)
        assert not worker.is_alive()
        timeout_view = result["view"]
    _assert_streams_clean(timeout_streams)
    assert timeout_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(timeout_marker)
    assert timeout_view.state is ProviderState.SAFE_ERROR
    assert timeout_view.error.code is SafeErrorCode.TIMEOUT
    _assert_gone(timeout_pids)

    artifact_path = os.environ.get("YASB_NATIVE_EVIDENCE_PATH")
    if artifact_path:
        artifact = {
            "native": True,
            "ready_authorized": bool(success_record["authorized"] and timeout_record["authorized"]),
            "tree_terminated": True,
            "bounded_timeout_error": timeout_view.error.code.value,
            "streams_clean": not (
                success_streams.stdout_bytes
                or success_streams.stderr_bytes
                or timeout_streams.stdout_bytes
                or timeout_streams.stderr_bytes
            ),
        }
        Path(artifact_path).write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    _assert_artifacts_are_sentinel_free(tuple(tmp_path.iterdir()), sentinel)


def test_sentinel_scan_failure_diagnostics_are_redacted(tmp_path: Path) -> None:
    sentinel = "native-redaction-sentinel"
    unsafe = tmp_path / "unsafe-proof.txt"
    unsafe.write_bytes(sentinel.encode("ascii"))
    with pytest.raises(AssertionError) as error:
        _assert_artifacts_are_sentinel_free((unsafe,), sentinel)
    if sentinel in str(error.value):
        pytest.fail("sentinel escaped artifact-scan diagnostics")


class _NestedJobApi:
    def create_job(self):
        return "job"

    def make_non_inheritable(self, handle):
        return True

    def enable_kill_on_close(self, handle):
        return True

    def open_process(self, pid, access):
        return "process"

    def is_process_in_job(self, process, job):
        return job is None

    def assign(self, job, process):
        raise AssertionError("nested containment must not authorize assignment")

    def query_active(self, job):
        return 0

    def terminate(self, job):
        return True

    def terminate_process(self, process):
        return True

    def wait(self, handle, timeout_ms):
        return WAIT_OBJECT_0

    def close(self, handle):
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
    assert view.error.code is SafeErrorCode.PROVIDER_ERROR
