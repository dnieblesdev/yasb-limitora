"""D01a1/a2a/D01a2b/D01a3a1 — Guard, marker codec, process identity, safe create."""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from typing import Any, cast

import pytest

from yasb_limitora._config_lock import (
    MarkerPrimitiveError,
    MarkerValidationError,
    ParentHold,
    ProbeWitness,
    ProcessTokenMissing,
    ProcessTokenUnprovable,
    _fixed_config_path,
    _real_api,
    config_lease,
    create_exclusive,
    creation_token,
    decode_marker,
    disposition_delete,
    encode_marker,
    identity_reopen,
    read_marker,
    safe_close,
    verify_parent,
    write_marker,
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

# ── D01a3a1 safe-marker-create-and-identity tests ────────────────────


class _MFake:
    """Semantic fake — simulates Win32 handle/file semantics, not API redefinition."""

    def __init__(self):
        self._h, self._n, self._files = 500, 1, {}
        self._pa, self._pi, self.create_calls = {}, {}, []
        self.closed, self._fq, self._ff = [], set(), set()

    def create_file(self, path, access, share, disp, attrs):
        self.create_calls.append((path, access, share, disp, attrs))
        norm = os.path.normcase(os.path.abspath(path))
        if disp == 1:
            if norm in self._pi or norm in self._pa:
                return 0
            h, self._h = self._h, self._h + 1
            self._files[h] = {"p": norm, "a": attrs or 0x80, "i": (0, self._n)}
            self._n += 1
            return h
        if disp == 3 and (norm in self._pi or (norm in self._pa and norm not in self._pi)):
            h, self._h = self._h, self._h + 1
            self._files[h] = {"p": norm, "a": self._pa.get(norm, 0x80), "i": self._pi.get(norm, (0, 0))}
            return h
        return 0

    def query_info(self, handle):
        if handle not in self._files or handle in self._fq:
            return None
        f = self._files[handle]
        return f["a"], 0, f["i"][0], f["i"][1]

    def final_path(self, handle):
        if handle not in self._files or handle in self._ff:
            return None
        return os.path.normcase(os.path.abspath(self._files[handle]["p"]))

    def close(self, handle):
        self.closed.append(handle)
        self._files.pop(handle, None)
        return True


def test_verify_parent_returns_live_hold(tmp_path):
    api = _MFake()
    parent = str(tmp_path)
    norm = os.path.normcase(os.path.abspath(parent))
    api._pa[norm] = 0x10
    hold = verify_parent(parent, api=api)
    assert hold.path == norm and len(hold.identity) == 3
    assert hold.handle not in api.closed
    assert api.create_calls[0][2] == 3  # deny FILE_SHARE_DELETE
    safe_close(hold.handle, api)
    assert hold.handle in api.closed


def test_verify_parent_rejects_invalid_parents(tmp_path):
    api = _MFake()
    norm = os.path.normcase(os.path.abspath(str(tmp_path)))
    api._pa[norm] = 0x10 | 0x400  # Reparse
    with pytest.raises(MarkerPrimitiveError):
        verify_parent(str(tmp_path), api=api)
    api._pa[norm] = 0x80  # Non-directory
    with pytest.raises(MarkerPrimitiveError):
        verify_parent(str(tmp_path), api=api)
    with pytest.raises(MarkerPrimitiveError):
        verify_parent("/nonexistent_path_zzz", api=_MFake())


def _parent_hold(path):
    return ParentHold(os.path.normcase(os.path.abspath(path)), 99, (0, 0, 0))


def test_create_exclusive_create_new_with_delete_rw_attrs_share_null():
    api = _MFake()
    parent = os.path.join(tempfile.gettempdir(), "t_d01a3a1_cr")
    expected = os.path.normcase(os.path.abspath(os.path.join(parent, "yasb-limitora.lock")))
    h, fp, ident = create_exclusive(_parent_hold(parent), api=api)
    try:
        c = api.create_calls[0]
        assert c[3] == 1  # CREATE_NEW
        assert c[1] & 0xC0010180 == 0xC0010180  # DELETE|RW|attributes
        assert c[2] == 7  # FILE_SHARE_READ|WRITE|DELETE
        assert c[4] == 0x80  # FILE_ATTRIBUTE_NORMAL
        assert fp == expected
        assert isinstance(ident, tuple) and len(ident) == 3
    finally:
        safe_close(h, api=api)


@pytest.mark.parametrize("bad_attr", [0x80 | 0x400, 0x10])
def test_create_exclusive_rejects_reparse_or_directory(bad_attr):
    api = _MFake()
    parent = os.path.join(tempfile.gettempdir(), f"t_d01a3a1_{bad_attr:x}")
    h_val = api._h
    orig = api.create_file

    def _patched(path, access, share, disp, attrs):
        h = orig(path, access, share, disp, attrs)
        if h and h in api._files:
            api._files[h]["a"] = bad_attr
        return h

    api.create_file = _patched
    with pytest.raises(MarkerPrimitiveError):
        create_exclusive(_parent_hold(parent), api=api)
    assert h_val in api.closed


@pytest.mark.parametrize("fail_set", ["_fq", "_ff"])
def test_create_exclusive_closes_on_query_or_final_failure(fail_set):
    api = _MFake()
    parent = os.path.join(tempfile.gettempdir(), f"t_d01a3a1_{fail_set}")
    h_val = api._h
    getattr(api, fail_set).add(h_val)
    with pytest.raises(MarkerPrimitiveError):
        create_exclusive(_parent_hold(parent), api=api)
    assert h_val in api.closed


def test_real_windows_create_close_no_residue(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows only")
    api = _real_api()
    assert api is not None
    parent = str(tmp_path)
    hold = verify_parent(parent, api=api)
    assert len(hold.identity) == 3  # (Volume, IndexHigh, IndexLow)
    with pytest.raises(PermissionError):
        os.rename(parent, parent + ".moved")
    mp = os.path.join(parent, "yasb-limitora.lock")
    try:
        h, mfp, mid = create_exclusive(hold, api=api)
        try:
            assert mfp == os.path.normcase(os.path.abspath(mp))
            assert os.path.isfile(mp) and os.path.getsize(mp) == 0
            assert len(mid) == 3
        finally:
            safe_close(h, api=api)
    finally:
        safe_close(hold.handle, api=api)
    os.unlink(mp)
    assert not os.path.exists(mp)


# ── D01a3a2a — Durable marker IO tests ───────────────────────────────


class _IOFake:
    def __init__(self):
        self._h, self._n, self._files = 500, 1, {}
        self._pa, self._pi, self.create_calls = {}, {}, []
        self.closed, self._fq, self._ff = [], set(), set()
        self._markers = {}
        self.flush_count, self.flush_fails, self.write_fails, self.read_fails = 0, False, False, False
        self._partial = 1024

    def create_file(self, path, access, share, disp, attrs):
        self.create_calls.append((path, access, share, disp, attrs))
        norm = os.path.normcase(os.path.abspath(path))
        if disp == 1:
            if norm in self._pi or norm in self._pa or norm in self._markers:
                return 0
            h, self._h = self._h, self._h + 1
            identity = (0, self._n, 0)
            self._n += 1
            self._files[h] = {"p": norm, "a": attrs or 0x80, "i": identity}
            self._markers[norm] = {"identity": identity, "content": b"", "attrs": attrs or 0x80}
            return h
        if disp == 3:
            if norm in self._markers:
                h, self._h = self._h, self._h + 1
                m = self._markers[norm]
                self._files[h] = {"p": norm, "a": m["attrs"], "i": m["identity"]}
                return h
            if norm in self._pi or norm in self._pa:
                h, self._h = self._h, self._h + 1
                self._files[h] = {"p": norm, "a": self._pa.get(norm, 0x80), "i": self._pi.get(norm, (0, 0, 0))}
                return h
            return 0
        return 0

    def query_info(self, handle):
        if handle not in self._files or handle in self._fq:
            return None
        f = self._files[handle]
        return f["a"], f["i"][0], f["i"][1], f["i"][2]

    def final_path(self, handle):
        if handle not in self._files or handle in self._ff:
            return None
        return os.path.normcase(os.path.abspath(self._files[handle]["p"]))

    def close(self, handle):
        self.closed.append(handle)
        self._files.pop(handle, None)
        return True

    def read_file(self, handle, max_bytes):
        if self.read_fails or handle not in self._files:
            return None
        return self._markers.get(self._files[handle]["p"], {}).get("content", b"")[: max_bytes + 1]

    def write_file(self, handle, data):
        if self.write_fails or handle not in self._files:
            return 0
        norm = self._files[handle]["p"]
        if norm in self._markers:
            n = min(len(data), self._partial)
            self._markers[norm]["content"] += data[:n]
            return n
        return 0

    def set_file_pointer(self, handle, _offset, _origin=0):
        if handle not in self._files:
            return None
        return 0

    def flush(self, handle):
        if self.flush_fails or handle not in self._files:
            return False
        self.flush_count += 1
        return True

    def set_disposition(self, handle):
        if handle not in self._files:
            return False
        norm = self._files[handle]["p"]
        if norm in self._markers:
            self._markers[norm]["_deleted"] = True
            return True
        return False


@contextlib.contextmanager
def _fh():
    a = _IOFake()
    p = os.path.join(tempfile.gettempdir(), f"t_{id(a)}")
    a._pa[os.path.normcase(os.path.abspath(p))] = 0x10
    hold = verify_parent(p, api=a)
    h, _fp, _ident = create_exclusive(hold, api=a)
    try:
        yield a, p, hold, h
    finally:
        safe_close(h, api=a)
        safe_close(hold.handle, api=a)


def test_read_write_marker_basic():
    with _fh() as (a, p, _hold, h):
        marker = encode_marker(42, "cafebabe00")
        assert write_marker(h, marker, api=a) is True
        mp = os.path.join(p, "yasb-limitora.lock")
        assert a._markers[os.path.normcase(os.path.abspath(mp))]["content"] == marker
        assert a.flush_count == 1
        assert read_marker(h, api=a) == marker


def test_read_marker_oversize_and_seek_failure():
    with _fh() as (a, p, _hold, h):
        mp = os.path.join(p, "yasb-limitora.lock")
        a._markers[os.path.normcase(os.path.abspath(mp))]["content"] = b"x" * 257
        with pytest.raises(MarkerPrimitiveError):
            read_marker(h, api=a)
        a._markers[os.path.normcase(os.path.abspath(mp))]["content"] = b"ok"
        orig = a.set_file_pointer
        a.set_file_pointer = lambda *_: None  # type: ignore[assignment]
        with pytest.raises(MarkerPrimitiveError):
            read_marker(h, api=a)
        a.set_file_pointer = orig


@pytest.mark.parametrize("fail_attr", ["read_fails", "write_fails", "flush_fails"])
def test_io_fails_closed_on_error(fail_attr):
    with _fh() as (api, _parent, _hold, h):
        setattr(api, fail_attr, True)
        marker = encode_marker(1, "a")
        if fail_attr == "read_fails":
            with pytest.raises(MarkerPrimitiveError):
                read_marker(h, api=api)
        else:
            with pytest.raises(MarkerPrimitiveError):
                write_marker(h, marker, api=api)


def test_write_marker_validation_and_looping():
    with _fh() as (api, parent, _hold, h):
        for bad in (b"", b"x" * 257, "str", 42, None):
            with pytest.raises(MarkerPrimitiveError):
                write_marker(h, bad, api=api)  # type: ignore[arg-type]
        api._partial = 0
        with pytest.raises(MarkerPrimitiveError):
            write_marker(h, encode_marker(1, "a"), api=api)
        api._partial = 5
        api.write_fails = False
        marker = encode_marker(42, "cafebabe00")
        assert write_marker(h, marker, api=api) is True
        mp = os.path.join(parent, "yasb-limitora.lock")
        assert api._markers[os.path.normcase(os.path.abspath(mp))]["content"] == marker


def test_real_windows_same_handle_write_read(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows only")
    api = _real_api()
    hold = verify_parent(str(tmp_path), api=api)
    h, _mfp, _mid = create_exclusive(hold, api=api)
    try:
        marker = encode_marker(5678, "fedcba9876543210")
        write_marker(h, marker, api=api)
        assert read_marker(h, api=api) == marker
    finally:
        safe_close(h, api=api)
        safe_close(hold.handle, api=api)
        mp = os.path.join(str(tmp_path), "yasb-limitora.lock")
        if os.path.exists(mp):
            os.unlink(mp)


# ── D01a3a2b — Identity re-open and disposition delete tests ─────────


def test_identity_reopen_open_existing_with_identity_check():
    """identity_reopen uses OPEN_EXISTING and verifies volume/file identity."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        orig_ident = api._markers[os.path.normcase(os.path.abspath(mp))]["identity"]
        w = identity_reopen(mp, parent=hold, expected=orig_ident, original=h, api=api)
        assert isinstance(w, ProbeWitness) and w._handle == h and w._identity == orig_ident
        assert api.create_calls[-1][3] == 3  # OPEN_EXISTING


def test_identity_reopen_rejects_alias_path():
    """identity_reopen refuses when final path doesn't match expected leaf."""
    with _fh() as (api, _parent, hold, h):
        # Create a second marker in a different parent
        other_path = os.path.join(tempfile.gettempdir(), "t_d01a3a2b_alias")
        api._pa[os.path.normcase(os.path.abspath(other_path))] = 0x10
        other_hold = verify_parent(other_path, api=api)
        other_h, _, _ = create_exclusive(other_hold, api=api)
        safe_close(other_h, api=api)
        other_mp = os.path.join(other_path, "yasb-limitora.lock")
        # Reopen with wrong parent must fail (path mismatch)
        with pytest.raises(MarkerPrimitiveError):
            identity_reopen(other_mp, parent=hold, expected=(0, 0, 0), original=h, api=api)
        safe_close(other_hold.handle, api=api)


def test_identity_reopen_rejects_reparse():
    """identity_reopen refuses reparse-point markers."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        norm = os.path.normcase(os.path.abspath(mp))
        api._markers[norm]["attrs"] = 0x80 | 0x400  # reparse
        with pytest.raises(MarkerPrimitiveError):
            identity_reopen(mp, parent=hold, expected=(0, 0, 0), original=h, api=api)


def test_disposition_delete_on_original_handle():
    """disposition_delete calls SetFileInformationByHandle(FileDispositionInfo)."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        norm = os.path.normcase(os.path.abspath(mp))
        orig = api._markers[norm]["identity"]
        w = identity_reopen(mp, parent=hold, expected=orig, original=h, api=api)
        assert disposition_delete(h, witness=w, api=api) is True
        assert api._markers[norm].get("_deleted") is True


def test_real_windows_identity_reopen_and_disposition_delete(tmp_path):
    """Real Windows: OPEN_EXISTING, identity match, disposition delete, no residue."""
    if os.name != "nt":
        pytest.skip("Windows only")
    api = _real_api()
    hold = verify_parent(str(tmp_path), api=api)
    mp = os.path.join(str(tmp_path), "yasb-limitora.lock")
    h, _mfp, mid = create_exclusive(hold, api=api)
    try:
        marker = encode_marker(7777, "abcdef0123456789")
        write_marker(h, marker, api=api)
        # Identity re-open
        w = identity_reopen(mp, parent=hold, expected=mid, original=h, api=api)
        assert isinstance(w, ProbeWitness) and w._handle == h
        assert read_marker(h, api=api) == marker
        # Disposition delete
        disposition_delete(h, witness=w, api=api)
    finally:
        safe_close(h, api=api)
        safe_close(hold.handle, api=api)
    assert not os.path.exists(mp)


def test_real_windows_disposition_delete_never_removes_successor(tmp_path):
    """Real Windows: disposition delete of handle 1 never removes successor handle 2."""
    if os.name != "nt":
        pytest.skip("Windows only")
    api = _real_api()
    hold = verify_parent(str(tmp_path), api=api)
    mp = os.path.join(str(tmp_path), "yasb-limitora.lock")
    h1, _fp1, mid1 = create_exclusive(hold, api=api)
    write_marker(h1, encode_marker(1, "aaaa"), api=api)
    w1 = identity_reopen(mp, parent=hold, expected=mid1, original=h1, api=api)
    disposition_delete(h1, witness=w1, api=api)
    safe_close(h1, api=api)
    assert not os.path.exists(mp)
    # Create successor
    h2, _fp2, mid2 = create_exclusive(hold, api=api)
    marker2 = encode_marker(2, "bbbb")
    write_marker(h2, marker2, api=api)
    assert os.path.exists(mp)
    # Identity re-open must match successor, not predecessor
    w2 = identity_reopen(mp, parent=hold, expected=mid2, original=h2, api=api)
    assert w2._identity == mid2 and w2._identity != mid1
    assert read_marker(h2, api=api) == marker2
    safe_close(h2, api=api)
    safe_close(hold.handle, api=api)
    os.unlink(mp)


# ── D01a3a2b corrective — mandatory verification inputs + ABI ────────


def test_real_api_set_disposition_uses_one_byte_boolean():
    """FILE_DISPOSITION_INFO is a 1-byte BOOLEAN per Win32 ABI."""
    if os.name != "nt":
        pytest.skip("Windows only")
    import ctypes as _ct

    from yasb_limitora._config_lock import _FileDispositionInfo

    info = _FileDispositionInfo()
    assert _ct.sizeof(info) == 1, f"FILE_DISPOSITION_INFO must be 1 byte, got {_ct.sizeof(info)}"


def test_identity_reopen_requires_parent_and_expected():
    """parent, expected and original are mandatory; omission must be refused."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        orig_ident = api._markers[os.path.normcase(os.path.abspath(mp))]["identity"]
        reopen = cast(Any, identity_reopen)
        with pytest.raises((MarkerPrimitiveError, TypeError)):
            reopen(mp, api=api)
        with pytest.raises((MarkerPrimitiveError, TypeError)):
            reopen(mp, parent=hold, original=h, api=api)
        with pytest.raises((MarkerPrimitiveError, TypeError)):
            reopen(mp, expected=orig_ident, original=h, api=api)
        with pytest.raises((MarkerPrimitiveError, TypeError)):
            reopen(mp, parent=hold, expected=orig_ident, api=api)


def test_identity_reopen_closes_probe_on_failure():
    """Every probe handle is closed on success and failure."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        closed_before = len(api.closed)
        with pytest.raises(MarkerPrimitiveError):
            identity_reopen(mp, parent=hold, expected=(999, 999, 0), original=h, api=api)
        assert len(api.closed) > closed_before


def test_forged_witness_refused():
    """Forged ProbeWitness (invalid handle or zero identity) is refused."""
    for bad_h in (0, -1):
        with pytest.raises(MarkerPrimitiveError):
            ProbeWitness(bad_h, (0, 0, 0))
    with _fh() as (api, _parent, _hold, h):
        fake_w = ProbeWitness(h, (0, 0, 0))
        with pytest.raises(MarkerPrimitiveError):
            disposition_delete(h, witness=fake_w, api=api)

def test_stale_witness_recycled_handle_refused_successor_survives():
    """Stale witness from deleted predecessor cannot delete successor."""
    with _fh() as (api, parent, hold, h1):
        mp = os.path.join(parent, "yasb-limitora.lock")
        norm = os.path.normcase(os.path.abspath(mp))
        ident1 = api._markers[norm]["identity"]
        w1 = identity_reopen(mp, parent=hold, expected=ident1, original=h1, api=api)
        disposition_delete(h1, witness=w1, api=api)
        safe_close(h1, api=api)
        del api._markers[norm]
        api._h = h1
        h2, _, ident2 = create_exclusive(hold, api=api)
        assert h2 == h1 and ident2 != ident1
        with pytest.raises(MarkerPrimitiveError):
            disposition_delete(h2, witness=w1, api=api)
        assert not api._markers[norm].get("_deleted")

def test_identity_reopen_close_failure_no_witness():
    """Probe close failure returns no witness and raises sanitized error."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        orig_ident = api._markers[os.path.normcase(os.path.abspath(mp))]["identity"]
        orig_close = api.close
        try:
            api.close = lambda _h: False  # type: ignore[assignment]
            with pytest.raises(MarkerPrimitiveError):
                identity_reopen(mp, parent=hold, expected=orig_ident, original=h, api=api)
        finally:
            api.close = orig_close  # type: ignore[assignment]

def test_set_disposition_exception_sanitized_no_message_leak():
    """set_disposition exception is wrapped; no raw message leaks."""
    with _fh() as (api, parent, hold, h):
        mp = os.path.join(parent, "yasb-limitora.lock")
        orig_ident = api._markers[os.path.normcase(os.path.abspath(mp))]["identity"]
        w = identity_reopen(mp, parent=hold, expected=orig_ident, original=h, api=api)
        def _raising(_h):
            raise OSError("SECRET-LEAK-12345")
        api.set_disposition = _raising  # type: ignore[assignment]
        with pytest.raises(MarkerPrimitiveError) as exc_info:
            disposition_delete(h, witness=w, api=api)
        assert "SECRET-LEAK-12345" not in str(exc_info.value)
