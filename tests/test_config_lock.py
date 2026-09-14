"""D01a1/a2a — Guard domain, deadline, and marker codec tests."""
from __future__ import annotations

import json

import pytest

from yasb_limitora._config_lock import (
    MarkerValidationError,
    _fixed_config_path,
    config_lease,
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
