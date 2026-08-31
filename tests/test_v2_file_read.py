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


@pytest.mark.parametrize("operation", ("read", "call"))
def test_bounded_private_job_and_process_cleanup_are_retained_and_retried(monkeypatch, operation):
    from yasb_limitora import v2_path

    close_attempts = []
    process_close_attempts = []

    class Job:
        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
        def close_with_deadline(self, context):
            close_attempts.append(len(close_attempts) + 1)
            if len(close_attempts) == 1:
                raise RuntimeError("private Job cleanup")

    class Endpoint:
        def close(self):
            pass
        def poll(self):
            return True
        def recv(self):
            return True, b"{}"

    class Output(Endpoint):
        def get_nowait(self):
            return True, b"{}"
        def get(self, timeout=None):
            return True, b"{}"
        def cancel_join_thread(self):
            pass

    class Event:
        def set(self):
            pass
        def close(self):
            if operation == "read":
                raise RuntimeError("authorization Event is not a closeable IPC endpoint")

    class Process:
        pid = 42
        exitcode = 0
        def start(self):
            pass
        def join(self, timeout=None):
            pass
        def is_alive(self):
            return False
        def close(self):
            process_close_attempts.append(len(process_close_attempts) + 1)
            if len(process_close_attempts) == 1:
                raise RuntimeError("private process cleanup")

    class Context:
        def Queue(self):
            return Output()
        def Event(self):
            return Event()
        def Pipe(self, duplex=False):
            return Endpoint(), Endpoint()
        def Process(self, target, args):
            return Process()

    jobs = []
    module = type("WindowsJobModule", (), {"WindowsJobBoundary": lambda: jobs.append(Job()) or jobs[-1]})
    monkeypatch.setattr(v2_path.os, "name", "nt")
    monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: Context())
    monkeypatch.setitem(v2_path.__dict__, "__import__", lambda *args, **kwargs: module)

    if operation == "read":
        invoke = lambda: v2_path._bounded_file_read("C:\\config.json", _context())
    else:
        invoke = lambda: v2_path._bounded_file_call(lambda: None, (), _context())
    try:
        with pytest.raises(V2FileError):
            invoke()
        assert close_attempts == [1] and len(v2_path._PENDING_JOB_OWNERS) == 1
        assert process_close_attempts == [1] and len(v2_path._PENDING_PROCESS_OWNERS) == 1
        assert invoke() == b"{}"
        assert close_attempts == [1, 2, 3]
        assert process_close_attempts == [1, 2, 3]
        assert not v2_path._PENDING_JOB_OWNERS and not v2_path._PENDING_PROCESS_OWNERS
    finally:
        v2_path._PENDING_JOB_OWNERS.clear()
        v2_path._PENDING_PROCESS_OWNERS.clear()


def test_bounded_file_call_authorizes_child_after_private_job_assignment(monkeypatch):
    from yasb_limitora import v2_path

    events = []

    class Endpoint:
        def close(self):
            events.append("endpoint-close")
        def poll(self):
            return True
        def recv(self):
            return True, b"value"
        def send(self, value):
            events.append("send")

    class Event:
        def set(self):
            events.append("authorize")
        def wait(self):
            events.append("child-wait")
        def close(self):
            events.append("event-close")

    class Process:
        pid = 42
        exitcode = 0
        def __init__(self, target, args):
            self.target, self.args = target, args
        def start(self):
            events.append("process-start")
        def join(self, timeout=None):
            events.append("process-join")
            self.target(*self.args)
        def is_alive(self):
            return False
        def close(self):
            events.append("process-close")

    class Context:
        def Pipe(self, duplex=False):
            return Endpoint(), Endpoint()
        def Event(self):
            return Event()
        def Process(self, target, args):
            return Process(target, args)

    class Job:
        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
            events.append("job-assign")
        def close_with_deadline(self, context):
            events.append("job-close")

    module = type("WindowsJobModule", (), {"WindowsJobBoundary": Job})
    monkeypatch.setattr(v2_path.os, "name", "nt")
    monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: Context())
    monkeypatch.setitem(v2_path.__dict__, "__import__", lambda *args, **kwargs: module)

    callback = lambda: events.append("callback") or b"value"

    assert v2_path._bounded_file_call(callback, (), _context()) == b"value"
    assert events.index("job-assign") < events.index("authorize") < events.index("child-wait") < events.index("callback")


def test_bounded_file_call_ipc_cleanup_failure_is_retained_and_retried(monkeypatch):
    from yasb_limitora import v2_path

    receiver_failure = [True]

    class Endpoint:
        def __init__(self, receiver=False):
            self.receiver = receiver
        def close(self):
            if self.receiver and receiver_failure[0]:
                receiver_failure[0] = False
                raise RuntimeError("receiver cleanup failed")
        def poll(self):
            return True
        def recv(self):
            return True, b"value"

    class Event:
        def set(self):
            pass
        def wait(self):
            pass
        def close(self):
            pass

    class Process:
        pid = 42
        def __init__(self, target, args):
            pass
        def start(self):
            pass
        def join(self, timeout=None):
            pass
        def is_alive(self):
            return False
        def close(self):
            pass

    class Context:
        def Pipe(self, duplex=False):
            return Endpoint(receiver=True), Endpoint()
        def Event(self):
            return Event()
        def Process(self, target, args):
            return Process(target, args)

    class Job:
        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
        def close_with_deadline(self, context):
            pass

    module = type("WindowsJobModule", (), {"WindowsJobBoundary": Job})
    monkeypatch.setattr(v2_path.os, "name", "nt")
    monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: Context())
    monkeypatch.setitem(v2_path.__dict__, "__import__", lambda *args, **kwargs: module)

    try:
        with pytest.raises(V2FileError):
            v2_path._bounded_file_call(lambda: b"value", (), _context())
        assert len(v2_path._PENDING_IPC_OWNERS) == 1
        assert v2_path._bounded_file_call(lambda: b"value", (), _context()) == b"value"
        assert not v2_path._PENDING_IPC_OWNERS
    finally:
        v2_path._PENDING_IPC_OWNERS.clear()


def test_bounded_file_call_rechecks_deadline_before_authorization(monkeypatch):
    from yasb_limitora import v2_path

    events = []

    class ExpiringContext:
        def __init__(self):
            self.calls = 0
        def usable_ns(self):
            self.calls += 1
            return 1_000_000 if self.calls == 1 else 0
        def remaining_ns(self):
            return 1_000_000
        def cleanup_ns(self):
            return 1_000_000

    class Endpoint:
        def close(self):
            events.append("endpoint-close")
        def poll(self):
            return False

    class Event:
        def set(self):
            events.append("authorize")
        def wait(self):
            pass
        def close(self):
            events.append("event-close")

    class Process:
        pid = 42
        def __init__(self, target, args):
            pass
        def start(self):
            events.append("process-start")
        def join(self, timeout=None):
            events.append("process-join")
        def is_alive(self):
            return False
        def close(self):
            events.append("process-close")

    class Context:
        def Pipe(self, duplex=False):
            return Endpoint(), Endpoint()
        def Event(self):
            return Event()
        def Process(self, target, args):
            return Process(target, args)

    class Job:
        def assign_process(self, pid, *, allow_nested=False):
            events.append("job-assign")
        def close_with_deadline(self, context):
            events.append("job-close")

    module = type("WindowsJobModule", (), {"WindowsJobBoundary": Job})
    monkeypatch.setattr(v2_path.os, "name", "nt")
    monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["spawn"])
    monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: Context())
    monkeypatch.setitem(v2_path.__dict__, "__import__", lambda *args, **kwargs: module)

    with pytest.raises(V2DeadlineError):
        v2_path._bounded_file_call(lambda: b"value", (), ExpiringContext())

    assert "job-assign" in events and "authorize" not in events
    assert "job-close" in events and "process-close" in events and "event-close" in events


def test_frozen_windows_spawn_uses_bundle_executable_and_required_bootloader_context(monkeypatch):
    from yasb_limitora import v2_path

    bundle_executable = r"C:\\bundle\\yasb-limitora.exe"
    source = {
        "PATH": "public-sentinel",
        "_PYI_ARCHIVE_FILE": "archive-sentinel",
        "_PYI_APPLICATION_HOME_DIR": "home-sentinel",
        "_PYI_PARENT_PROCESS_LEVEL": "1",
        "_PYI_PRIVATE_SECRET": "must-not-leak",
        "LIMITORA_OPENCODE_API_KEY": "must-not-leak",
        "OPENAI_API_KEY": "must-not-leak",
    }
    monkeypatch.setattr(v2_path._PRIVATE_SYS, "frozen", True, raising=False)

    environment = v2_path._private_child_environment(source)
    application = v2_path._windows_spawn_executable(
        bundle_executable, replace_with_base=True, base_executable=r"C:\\Python\\python.exe"
    )

    assert application == bundle_executable
    assert environment == {
        "PATH": "public-sentinel",
        "_PYI_ARCHIVE_FILE": "archive-sentinel",
        "_PYI_APPLICATION_HOME_DIR": "home-sentinel",
        "_PYI_PARENT_PROCESS_LEVEL": "1",
    }
    assert "__PYVENV_LAUNCHER__" not in environment
    assert not any("SECRET" in key or "API_KEY" in key for key in environment)


def test_non_frozen_windows_spawn_keeps_base_executable_and_public_environment(monkeypatch):
    from yasb_limitora import v2_path

    source = {
        "PATH": "public-sentinel",
        "_PYI_ARCHIVE_FILE": "archive-sentinel",
        "_PYI_APPLICATION_HOME_DIR": "home-sentinel",
        "_PYI_PARENT_PROCESS_LEVEL": "1",
        "LIMITORA_OPENCODE_API_KEY": "must-not-leak",
    }
    monkeypatch.delattr(v2_path._PRIVATE_SYS, "frozen", raising=False)

    environment = v2_path._private_child_environment(source)
    application = v2_path._windows_spawn_executable(
        r"C:\\venv\\Scripts\\python.exe", replace_with_base=True, base_executable=r"C:\\Python\\python.exe"
    )

    assert application == r"C:\\Python\\python.exe"
    assert environment == {"PATH": "public-sentinel"}
    assert "__PYVENV_LAUNCHER__" not in environment


def test_spawn_environment_contains_only_public_sentinels(monkeypatch):
    from yasb_limitora import v2_path

    source = {
        "PATH": "public-sentinel",
        "LIMITORA_OPENCODE_API_KEY": "secret-sentinel",
        "OPENAI_API_KEY": "other-secret-sentinel",
    }
    monkeypatch.setattr(v2_path.os, "environ", source)
    observed = {}

    with v2_path._spawn_environment(v2_path._public_child_environment(source)):
        observed.update({
            "path_present": "PATH" in v2_path.os.environ,
            "opencode_present": "LIMITORA_OPENCODE_API_KEY" in v2_path.os.environ,
            "openai_present": "OPENAI_API_KEY" in v2_path.os.environ,
        })

    assert observed == {"path_present": True, "opencode_present": False, "openai_present": False}
