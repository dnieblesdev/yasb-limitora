"""D01a1/a2a/D01a2b — Guard domain, marker codec, and process identity tests."""
from __future__ import annotations

import json
import os

import pytest

from yasb_limitora._config_lock import (
    MarkerValidationError,
    ProcessTokenMissing,
    ProcessTokenUnprovable,
    _fixed_config_path,
    config_lease,
    creation_token,
    decode_marker,
    encode_marker,
)
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


# ── D01a1 guard-domain tests ─────────────────────────────────────────


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


# ── D01a2a marker-codec tests ────────────────────────────────────────


def test_encode_decode_roundtrip():
    for pid, tok in [(1, "a"), (999999, "deadbeef00"), (4294967295, "0123456789abcdef")]:
        m = encode_marker(pid, tok)
        assert isinstance(m, bytes)
        p, t, v = decode_marker(m)
        assert (p, t, v) == (pid, tok, 1)


def test_marker_canonical_json():
    m1, m2 = encode_marker(42, "cafebabe00"), encode_marker(42, "cafebabe00")
    assert m1 == m2
    assert json.loads(m1) == {"pid": 42, "token": "cafebabe00", "version": 1}


def test_marker_exact_canonical_bytes():
    """Assert exact canonical byte sequence: sorted keys, no whitespace."""
    m = encode_marker(42, "cafebabe00")
    expected = b'{"pid":42,"token":"cafebabe00","version":1}'
    assert m == expected
    # Verify no whitespace
    assert b" " not in m
    assert b"\t" not in m
    assert b"\n" not in m
    # Verify key order: pid < token < version (alphabetical)
    pid_pos = m.find(b'"pid"')
    token_pos = m.find(b'"token"')
    version_pos = m.find(b'"version"')
    assert pid_pos < token_pos < version_pos


def test_decode_rejects_noncanonical_whitespace():
    """Reject markers with whitespace even if otherwise valid."""
    canonical = encode_marker(42, "cafebabe00")
    # Add space after colon
    with_space = canonical.replace(b":", b": ", 1)
    with pytest.raises(MarkerValidationError):
        decode_marker(with_space)
    # Add newline
    with_newline = canonical + b"\n"
    with pytest.raises(MarkerValidationError):
        decode_marker(with_newline)
    # Add tab
    with_tab = b'{"pid":42,\t"token":"cafebabe00","version":1}'
    with pytest.raises(MarkerValidationError):
        decode_marker(with_tab)


def test_decode_rejects_noncanonical_key_order():
    """Reject markers with keys not in sorted order."""
    # Valid JSON but wrong key order: token < pid < version
    wrong_order = b'{"token":"cafebabe00","pid":42,"version":1}'
    with pytest.raises(MarkerValidationError):
        decode_marker(wrong_order)
    # Another wrong order: version first
    wrong_order2 = b'{"version":1,"pid":42,"token":"cafebabe00"}'
    with pytest.raises(MarkerValidationError):
        decode_marker(wrong_order2)


def test_decode_rejects_invalid():
    cases = [
        b"",
        b"x" * 257,
        b"not json",
        b"[1,2]",
        b'{"token":"a"}',
        b'{"pid":1}',
        b'{"pid":1,"token":"a"}',
        b'{"pid":1,"token":"a","x":1}',
        b'{"pid":0,"token":"a","version":1}',
        b'{"pid":-1,"token":"a","version":1}',
        b'{"pid":4294967296,"token":"a","version":1}',
        b'{"pid":"1","token":"a","version":1}',
        b'{"pid":true,"token":"a","version":1}',
        b'{"pid":1,"token":"","version":1}',
        b'{"pid":1,"token":1,"version":1}',
        b'{"pid":1,"token":"ABC","version":1}',
        b'{"pid":1,"token":"xyz","version":1}',
        b'{"pid":1,"token":"' + b"a" * 65 + b'","version":1}',
        b'{"pid":1,"pid":2,"token":"a","version":1}',
        b'{"pid":1,"token":"a","version":true}',
        b'{"pid":1,"token":"a","version":0}',
        b'{"pid":1,"token":"a","version":2}',
        b'{"pid":1,"token":"a","version":"1"}',
    ]
    for data in cases:
        with pytest.raises(MarkerValidationError):
            decode_marker(data)


def test_marker_validation_error_stable_message():
    """All invalid marker cases raise MarkerValidationError with stable message."""
    try:
        decode_marker(b"")
    except MarkerValidationError as e:
        assert str(e) == "marker-validation"
    try:
        encode_marker(0, "a")
    except MarkerValidationError as e:
        assert str(e) == "marker-validation"


def test_decode_no_cause_leakage():
    """Invalid UTF-8 and malformed JSON have __cause__ is None."""
    # Invalid UTF-8
    try:
        decode_marker(b"\xff\xfe")
    except MarkerValidationError as e:
        assert e.__cause__ is None
    # Malformed JSON
    try:
        decode_marker(b"{invalid")
    except MarkerValidationError as e:
        assert e.__cause__ is None


def test_decode_rejects_escape_spellings():
    """Roundtrip check rejects escaped key/value spellings."""
    # Escaped key: \u0070id instead of pid
    escaped_key = b'{"\\u0070id":42,"token":"cafebabe00","version":1}'
    with pytest.raises(MarkerValidationError):
        decode_marker(escaped_key)
    # Escaped value in token: \u0063 instead of c
    escaped_value = b'{"pid":42,"token":"\\u0063afebabe00","version":1}'
    with pytest.raises(MarkerValidationError):
        decode_marker(escaped_value)
    # Escaped colon: \u003a instead of :
    escaped_colon = b'{"pid"\\u003a42,"token":"cafebabe00","version":1}'
    with pytest.raises(MarkerValidationError):
        decode_marker(escaped_colon)


# ── D01a2b process-identity tests ────────────────────────────────────


class _FakeKernel32:
    """Minimal Win32 kernel32 stub for creation_token injection tests."""

    def __init__(
        self,
        *,
        open_handle=200,
        open_error=0,
        times_ok=True,
        close_ok=True,
    ):
        self.open_handle = open_handle
        self.open_error = open_error
        self.times_ok = times_ok
        self.close_ok = close_ok
        self.opened: list[int] = []
        self.closed: list[int] = []
        self.creation_value: object = 0x01D9A3B2C4E6F800

    def OpenProcess(self, _access, _inherit, pid):
        if self.open_error:
            return 0
        self.opened.append(pid)
        return self.open_handle

    def GetProcessTimes(self, handle):
        if not self.times_ok:
            return None
        return self.creation_value

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return self.close_ok

    def get_last_error(self):
        return self.open_error


def test_real_current_pid_returns_lowercase_hex_token():
    """Real current PID produces a lowercase hex FILETIME token."""
    if os.name != "nt":
        pytest.skip("Windows only")
    token = creation_token(os.getpid())
    assert isinstance(token, str)
    assert 1 <= len(token) <= 16
    assert all(c in "0123456789abcdef" for c in token)


def test_invalid_pid_raises_unprovable():
    """Invalid/out-of-range/non-integer PID raises ProcessTokenUnprovable."""
    for bad in (0, -1, 4294967296, "42", 3.14, True, None):
        with pytest.raises(ProcessTokenUnprovable):
            creation_token(bad)


def test_openprocess_error_87_raises_missing():
    """OpenProcess NULL with last-error 87 raises ProcessTokenMissing."""
    fake = _FakeKernel32(open_handle=0, open_error=87)
    with pytest.raises(ProcessTokenMissing):
        creation_token(1234, api=fake)


def test_openprocess_non87_error_raises_unprovable():
    """OpenProcess NULL with non-87 error (access denied, other) → Unprovable."""
    for err in (5, 1234):
        fake = _FakeKernel32(open_handle=0, open_error=err)
        with pytest.raises(ProcessTokenUnprovable):
            creation_token(1234, api=fake)


def test_query_and_close_failures_raise_unprovable():
    """GetProcessTimes None or CloseHandle False → Unprovable; handle always closed."""
    fake_t = _FakeKernel32(times_ok=False)
    with pytest.raises(ProcessTokenUnprovable):
        creation_token(1234, api=fake_t)
    assert fake_t.open_handle in fake_t.closed
    fake_c = _FakeKernel32(close_ok=False)
    with pytest.raises(ProcessTokenUnprovable):
        creation_token(1234, api=fake_c)
    assert fake_c.open_handle in fake_c.closed


def test_missing_noncallable_and_raising_api():
    """Missing, non-callable, or raising API methods → ProcessTokenUnprovable."""
    class _Empty:
        pass
    class _Noncallable:
        OpenProcess = 42
        GetProcessTimes = 0
        CloseHandle = 0
    for api in (_Empty(), _Noncallable()):
        with pytest.raises(ProcessTokenUnprovable):
            creation_token(1234, api=api)
    class _OpenRaises:
        def OpenProcess(self, *_a): raise OSError
        def GetProcessTimes(self, *_a): return 0
        def CloseHandle(self, *_a): return True
        def get_last_error(self): return 0
    class _TimesRaises:
        def OpenProcess(self, *_a): return 200
        def GetProcessTimes(self, *_a): raise OSError
        def CloseHandle(self, *_a): return True
        def get_last_error(self): return 0
    class _CloseRaises:
        def OpenProcess(self, *_a): return 200
        def GetProcessTimes(self, *_a): return 0x100
        def CloseHandle(self, *_a): raise OSError
        def get_last_error(self): return 0
    for api in (_OpenRaises(), _TimesRaises(), _CloseRaises()):
        with pytest.raises(ProcessTokenUnprovable):
            creation_token(1234, api=api)


def test_invalid_filetime_and_missing_last_error():
    """Invalid FILETIME values and missing get_last_error → Unprovable."""
    for bad in (-1, True, None):
        fake = _FakeKernel32()
        fake.creation_value = bad
        with pytest.raises(ProcessTokenUnprovable):
            creation_token(1234, api=fake)
        assert fake.open_handle in fake.closed
    class _NoLastError:
        def OpenProcess(self, *_a): return 0
        def GetProcessTimes(self, *_a): return 0
        def CloseHandle(self, *_a): return True
    with pytest.raises(ProcessTokenUnprovable):
        creation_token(1234, api=_NoLastError())


def test_token_is_unpadded_lowercase_hex():
    """Token matches cache.py format: unpadded lowercase f\"{value:x}\"."""
    fake = _FakeKernel32()
    fake.creation_value = 0x0123456789ABCDEF
    assert creation_token(1234, api=fake) == f"{0x0123456789ABCDEF:x}"


def test_closehandle_always_called_after_open():
    """CloseHandle always attempted after successful OpenProcess."""
    import contextlib
    for ok in (True, False):
        fake = _FakeKernel32(times_ok=ok)
        with contextlib.suppress(ProcessTokenMissing, ProcessTokenUnprovable):
            creation_token(1234, api=fake)
        assert fake.open_handle in fake.closed

def test_real_current_pid_differential():
    """Real PID token is stable and matches unpadded hex format."""
    if os.name != "nt":
        pytest.skip("Windows only")
    t1 = creation_token(os.getpid())
    assert t1 == creation_token(os.getpid())
    assert t1 == f"{int(t1, 16):x}"
