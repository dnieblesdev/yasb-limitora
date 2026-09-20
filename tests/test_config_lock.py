"""D01a1 — Guard domain and real deadline tests (strict TDD: RED -> GREEN)."""
from __future__ import annotations

import pytest

from yasb_limitora._config_lock import _fixed_config_path, config_lease
from yasb_limitora.guard import WAIT_OBJECT_0, WAIT_TIMEOUT, Guard, GuardError

_SID = b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


class _FakeApi:
    def __init__(self, wait_results=(WAIT_OBJECT_0,), release_ok=True, close_ok=True):
        self.names: list[str] = []
        self._results = list(wait_results)
        self._idx = 0
        self._h = 100
        self.released: list[int] = []
        self.closed: list[int] = []
        self._release_ok = release_ok
        self._close_ok = close_ok

    def CreateMutexW(self, _sa, _initial, name):
        self.names.append(name)
        h = self._h
        self._h += 1
        return h

    def WaitForSingleObject(self, _handle, _timeout_ms):
        r = self._results[min(self._idx, len(self._results) - 1)]
        self._idx += 1
        return r

    def ReleaseMutex(self, handle):
        self.released.append(handle)
        return self._release_ok

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return self._close_ok


def _guard(api):
    return Guard(api=api, sid_provider=lambda: _SID)


def test_path_construction():
    for bad in ("", "  "):
        with pytest.raises(ValueError):
            _fixed_config_path(bad)
    assert _fixed_config_path("C:\\u") == "C:\\u\\yasb-limitora\\config.json"


def test_global_name_prefix_and_path_key(tmp_path):
    a, b = _FakeApi(), _FakeApi()
    with config_lease(str(tmp_path), guard=_guard(a)) as lease:
        assert a.names[0] == lease.name
        assert a.names[0].startswith(r"Global\yasb-limitora-v2-guard-")
    with config_lease(str(tmp_path / "b"), guard=_guard(b)):
        pass
    assert a.names[0] != b.names[0]


def test_eventual_acquisition_after_contention(tmp_path):
    api = _FakeApi([WAIT_TIMEOUT, WAIT_TIMEOUT, WAIT_OBJECT_0])
    with config_lease(str(tmp_path), guard=_guard(api)) as lease:
        assert lease.owned
    assert len(api.names) == 3


def test_terminal_timeout_raises_config_lock_busy(tmp_path):
    api = _FakeApi([WAIT_TIMEOUT])
    t = [1_000_000_000_000]

    def clock():
        t[0] += 300_000_000
        return t[0]

    with pytest.raises(GuardError, match="config-lock-busy"):
        ctx = config_lease(str(tmp_path), guard=_guard(api), deadline_seconds=0.5, clock_ns=clock)
        ctx.__enter__()
        ctx.__exit__(None, None, None)


def test_guaranteed_release_normal_exit(tmp_path):
    api = _FakeApi()
    with config_lease(str(tmp_path), guard=_guard(api)):
        pass
    assert api.released and api.closed


def test_guaranteed_release_on_exception(tmp_path):
    api = _FakeApi()
    ctx = config_lease(str(tmp_path), guard=_guard(api))
    with pytest.raises(RuntimeError), ctx:
        raise RuntimeError("boom")
    assert api.released and api.closed


def test_release_or_close_failure_sanitized(tmp_path):
    for kw, code in [({"release_ok": False}, "release"), ({"close_ok": False}, "close")]:
        api = _FakeApi(**kw)
        with pytest.raises(GuardError, match=f"config-lock-{code}-failed"), config_lease(
            str(tmp_path), guard=_guard(api)
        ):
            pass
        assert api.released and api.closed


def test_zero_filesystem_writes(tmp_path):
    state = tmp_path / "yasb-limitora"
    api = _FakeApi()
    with config_lease(str(tmp_path), guard=_guard(api)):
        pass
    assert not state.exists()
