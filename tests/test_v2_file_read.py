import os

import pytest

from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_path import V2DeadlineError, V2FileError, read_v2_config


def _context():
    return DeadlineContext(t0_ns=0, deadline_ns=10_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 0)


def test_v2_config_read_accepts_16384_bytes_and_rejects_the_extra_byte(tmp_path):
    valid = tmp_path / "valid.json"
    valid.write_bytes(b"{" + b" " * 16_382 + b"}")
    assert len(read_v2_config(valid, _context())) == 16_384

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 16_385)
    with pytest.raises(V2FileError):
        read_v2_config(oversized, _context())


def test_v2_config_read_rejects_non_regular_files_without_fallback(tmp_path):
    with pytest.raises(V2FileError):
        read_v2_config(tmp_path, _context())


def test_v2_config_read_does_not_open_after_deadline_expiry(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    opened = []
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 1)

    def open_file(*args):
        opened.append(args)
        return os.open(*args)

    with pytest.raises(V2FileError):
        read_v2_config(path, expired, open_fn=open_file)
    assert opened == []


def test_v2_config_read_uses_usable_budget_before_cleanup_reserve(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    context = DeadlineContext(t0_ns=0, deadline_ns=1_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 800_000_000)

    with pytest.raises(V2DeadlineError):
        read_v2_config(path, context, open_fn=lambda *args: os.open(*args))


def test_v2_config_read_closes_descriptor_when_deadline_expires_during_read(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    opened = []
    ticks = iter((0, 0, 0, 1))

    def open_file(*args):
        descriptor = os.open(*args)
        opened.append(descriptor)
        return descriptor

    context = DeadlineContext(t0_ns=0, deadline_ns=1, reserve_ns=0, clock_ns=lambda: next(ticks))
    with pytest.raises(V2DeadlineError):
        read_v2_config(path, context, open_fn=open_file, close_fn=lambda descriptor: os.close(descriptor))

    descriptor = opened[0]
    try:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def test_v2_config_read_close_failure_is_sanitized(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")

    def close_file(_fd):
        raise OSError("private close detail")

    with pytest.raises(V2FileError) as error:
        read_v2_config(path, _context(), close_fn=close_file)
    assert str(error.value) == "configuration read failed"


def test_v2_config_read_kills_a_blocking_injected_read_within_remaining_budget(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")

    def blocking_read(_fd, _size):
        import time
        time.sleep(2)
        return b"{}"

    context = DeadlineContext(t0_ns=0, deadline_ns=100_000_000, reserve_ns=20_000_000, clock_ns=lambda: 0)
    with pytest.raises(V2FileError):
        read_v2_config(path, context, read_fn=blocking_read)


def test_bounded_file_call_closes_both_pipe_endpoints_when_start_fails(monkeypatch):
    from yasb_limitora import v2_path

    events = []

    class Endpoint:
        def __init__(self, name):
            self.name = name

        def close(self):
            events.append(self.name)

    observed = []

    class Process:
        def start(self):
            observed.append(dict(os.environ))
            raise OSError("private process start detail")

        def is_alive(self):
            return False

        def close(self):
            events.append("process")

    class Event:
        def close(self):
            pass

    class Context:
        def Pipe(self, duplex=False):
            return Endpoint("receiver"), Endpoint("sender")

        def Event(self):
            return Event()

        def Process(self, target, args):
            return Process()

    monkeypatch.setenv("LIMITORA_TEST_SECRET", "must-not-leak")
    monkeypatch.setenv("SYSTEMROOT", "public-sentinel")
    expected = dict(os.environ)
    monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: Context())

    with pytest.raises(V2FileError) as error:
        v2_path._bounded_file_call(lambda: None, (), _context())

    assert str(error.value) == "configuration read failed"
    assert events == ["process", "receiver", "sender"]
    assert observed == [expected] and dict(os.environ) == expected


@pytest.mark.skipif(os.name != "nt", reason="native Windows CreateProcess seam")
def test_windows_spawn_passes_only_public_environment_to_create_process(monkeypatch):
    from multiprocessing import popen_spawn_win32

    from yasb_limitora import v2_path
    captured = {}
    winapi = vars(popen_spawn_win32)["_winapi"]
    real_create_process = winapi.CreateProcess

    def capture_create_process(application, command, *args):
        captured["environment"] = args[4]
        return real_create_process(application, command, *args)

    public_path = os.environ["PATH"] + ";public-sentinel"
    monkeypatch.setenv("PATH", public_path)
    monkeypatch.setenv("LIMITORA_TEST_SECRET", "must-not-leak")
    monkeypatch.setattr(winapi, "CreateProcess", capture_create_process)
    assert v2_path._bounded_file_call(bytes, (b"ok",), _context()) == b"ok"
    environment = captured["environment"]
    public_keys = vars(v2_path)["_PUBLIC_CHILD_ENV_KEYS"]
    assert environment["PATH"] == public_path
    assert "LIMITORA_TEST_SECRET" not in environment and set(environment) <= public_keys | {"__PYVENV_LAUNCHER__"}
