"""S04a focused tests: exact-name fresh YASB process snapshots with no control API."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

from yasb_limitora import discovery

MODULE = Path(__file__).resolve().parents[1] / "src" / "yasb_limitora" / "discovery.py"


def test_known_process_set_is_small_and_exact():
    assert sorted(discovery.YASB_PROCESS_NAMES) == ["yasb-limitora.exe", "yasb.exe"]


def test_exact_name_match_only_no_substrings():
    snapshot = [(1, "yasb.exe"), (2, "YASB.EXE"), (3, "yasb-helper.exe"), (4, "notyasb.exe"), (5, "yasb.exe.bak")]
    probe = discovery.probe_running_yasb(snapshot=lambda: snapshot)
    assert probe.status == "running"
    assert sorted(pid for pid, _ in probe.matches) == [1, 2]


def test_clear_when_no_exact_match():
    probe = discovery.probe_running_yasb(snapshot=lambda: [(7, "explorer.exe")])
    assert probe.status == "clear" and probe.matches == ()


def test_snapshot_failure_is_inconclusive_never_clear():
    def boom():
        raise RuntimeError("CreateToolhelp32Snapshot failed")

    probe = discovery.probe_running_yasb(snapshot=boom)
    assert probe.status == "inconclusive" and probe.matches == ()


def test_every_probe_is_a_fresh_snapshot_never_cached():
    calls = []

    def snapshot():
        calls.append(1)
        return [(1, "yasb.exe")] if len(calls) == 1 else []

    first = discovery.probe_running_yasb(snapshot=snapshot)
    second = discovery.probe_running_yasb(snapshot=snapshot)
    assert first.status == "running" and second.status == "clear" and len(calls) == 2


def test_module_exposes_no_process_control_api():
    source = MODULE.read_text(encoding="utf-8")
    forbidden = ("TerminateProcess", "CloseMainWindow", "taskkill", "SuspendThread", "ResumeThread",
                 "OpenProcess", "PROCESS_TERMINATE", "GenerateConsoleCtrl", "PostMessage", "SendMessage")
    assert not [token for token in forbidden if token in source]


@pytest.mark.skipif(os.name != "nt", reason="native Windows toolhelp snapshot")
def test_native_toolhelp_snapshot_sees_current_process():
    entries = discovery.snapshot_processes()
    current = os.path.basename(sys.executable).casefold()
    assert os.getpid() in {pid for pid, _ in entries}
    assert any(name.casefold() == current for pid, name in entries if pid == os.getpid())
    again = discovery.snapshot_processes()
    assert os.getpid() in {pid for pid, _ in again}  # fresh snapshot, not a cached first result
