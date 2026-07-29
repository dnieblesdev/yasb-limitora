import inspect
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

import yasb_limitora.codex_supervisor as s


def _bootstrap_wrapper():
    return (
        "import sys,types; m=types.ModuleType('msvcrt'); "
        "m.open_osfhandle=lambda handle,flags: handle; "
        "sys.modules['msvcrt']=m; exec(%r)"
        % s._BOOTSTRAP
    )


def _windows_startup_metadata(gate_read, data_write):
    import msvcrt

    child_handles = [
        msvcrt.get_osfhandle(data_write),
        msvcrt.get_osfhandle(gate_read),
    ]
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": child_handles}
    return child_handles, startup


def _reap(process):
    if process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _reset_inheritable(handles):
    for handle in reversed(handles):
        try:
            os.set_handle_inheritable(handle, False)
        except Exception:
            pass
    handles.clear()


def _run_real_bootstrap(signal, nonce, *, include_metadata=True):
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    process = None
    inheritable_handles = []
    try:
        if signal is not None:
            os.write(gate_write, signal)
        os.close(gate_write)
        gate_write = -1
        env = os.environ.copy()
        startupinfo = None
        if include_metadata:
            if os.name == "nt":
                child_handles, startupinfo = _windows_startup_metadata(
                    gate_read, data_write
                )
                env.update(
                    {
                        s._GATE_ENV: str(child_handles[1]),
                        s._DATA_ENV: str(child_handles[0]),
                        s._NONCE_ENV: nonce.decode("ascii"),
                    }
                )
                for handle in child_handles:
                    os.set_handle_inheritable(handle, True)
                    inheritable_handles.append(handle)
            else:
                env.update(
                    {
                        s._GATE_ENV: str(gate_read),
                        s._DATA_ENV: str(data_write),
                        s._NONCE_ENV: nonce.decode("ascii"),
                    }
                )
        argv = [sys.executable, "-I", "-S", "-E", "-c", s._BOOTSTRAP]
        if os.name == "nt":
            child_argv, extra = argv, {}
        else:
            child_argv, extra = [argv[0], *argv[1:-1], _bootstrap_wrapper()], {
                "pass_fds": (gate_read, data_write),
            }
        process = subprocess.Popen(
            child_argv,
            env=env,
            startupinfo=startupinfo,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **extra,
        )
        _reset_inheritable(inheritable_handles)
        os.close(gate_read)
        gate_read = -1
        os.close(data_write)
        data_write = -1
        code = process.wait(timeout=2)
        output = os.read(data_read, 4096)
        return code, output
    finally:
        _reset_inheritable(inheritable_handles)
        if process is not None:
            try:
                _reap(process)
            except Exception:
                pass
        for fd in (gate_read, gate_write, data_read, data_write):
            if fd >= 0:
                try:
                    os.close(fd)
                except Exception:
                    pass


def test_real_bootstrap_emits_exact_nonce_bound_ready_frame():
    code, output = _run_real_bootstrap(b"1", b"dynamic-nonce")
    assert code == 0
    assert output == b"READY:dynamic-nonce"


@pytest.mark.parametrize(
    ("signal", "include_metadata"),
    ((b"0", True), (b"1", False)),
)
def test_real_bootstrap_rejects_invalid_or_missing_metadata_without_ready(
    signal, include_metadata
):
    code, output = _run_real_bootstrap(
        signal,
        b"dynamic-nonce",
        include_metadata=include_metadata,
    )
    assert code == 1
    assert output == b""


def test_bootstrap_harness_reaps_live_child_with_bounded_cleanup():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _reap(process)
        assert process.poll() is not None
    finally:
        _reap(process)


def test_default_nonce_is_dynamic_and_ascii_safe():
    first, second = s._new_ready_nonce(), s._new_ready_nonce()
    assert first != second
    assert 0 < len(first) <= s._NONCE_LIMIT
    assert first.decode("ascii")
    assert second.decode("ascii")


def test_private_metadata_allowlist_and_directional_startup_contract():
    environment = s._environment(
        {
            "SystemRoot": "root",
            "PATH": "path",
            "OPENAI_API_KEY": "secret",
            s._GATE_ENV: "wrong-gate",
        },
        gate_read=41,
        data_write=42,
        nonce=b"nonce-04d1",
    )
    assert environment == {
        "SystemRoot": "root",
        "PATH": "path",
        s._GATE_ENV: "41",
        s._DATA_ENV: "42",
        s._NONCE_ENV: "nonce-04d1",
    }

    startup = s._startup([42, 41], lambda: type("Startup", (), {})())
    assert startup.lpAttributeList["handle_list"] == [42, 41]
    assert 43 not in startup.lpAttributeList["handle_list"]
    assert f"os.environ.pop({s._GATE_ENV!r})" in s._BOOTSTRAP
    assert f"os.environ.pop({s._DATA_ENV!r})" in s._BOOTSTRAP
    assert f"os.environ.pop({s._NONCE_ENV!r})" in s._BOOTSTRAP
    assert f"len(nonce)>{s._NONCE_LIMIT}" in s._BOOTSTRAP


def test_windows_cleanup_resets_handles_before_closing_descriptors():
    source = inspect.getsource(_run_real_bootstrap)
    assert source.index("_reset_inheritable(inheritable_handles)") < source.index(
        "os.close(gate_read)"
    )


@pytest.mark.skipif(os.name != "nt", reason="raw HANDLE contract is Windows-specific")
def test_windows_harness_uses_raw_directional_handles():
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    try:
        import msvcrt

        handles, startup = _windows_startup_metadata(gate_read, data_write)
        assert handles == [
            msvcrt.get_osfhandle(data_write),
            msvcrt.get_osfhandle(gate_read),
        ]
        assert startup.lpAttributeList["handle_list"] == handles
    finally:
        os.close(gate_read)
        os.close(gate_write)
        os.close(data_read)
        os.close(data_write)


def test_private_surface_has_no_public_supervisor_or_provider_exports():
    assert s.__all__ == ()
    assert not hasattr(s, "Popen")
    assert not hasattr(s, "Limitora")
    assert not hasattr(s, "StatusClient")
    assert not hasattr(s, "activate_provider")
    assert all(name.startswith("_") for name in s.__dict__ if name not in {"__name__", "__doc__", "__package__", "__loader__", "__spec__", "__all__", "__builtins__"})


def test_transport_reports_runtime_eof():
    transport = s._PipeTransport(1, 2, peek=lambda fd: (0, True), nonblocking=True)
    with pytest.raises(s._TransportError, match="eof"):
        transport.read_frame(expected_size=1)


def test_transport_rejects_partial_frame_followed_by_eof():
    available = iter(((2, False), (0, True)))
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=lambda fd, size: b"ab",
        nonblocking=True,
    )
    with pytest.raises(s._TransportError, match="eof"):
        transport.read_frame(expected_size=3)


def test_transport_requires_nonblocking_io_contract():
    with pytest.raises(s._TransportError, match="nonblocking_required"):
        s._PipeTransport(1, 2)


class _ControlledClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_transport_times_out_when_empty_without_eof():
    clock = _ControlledClock()
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: (0, False),
        clock=clock,
        sleep=clock.sleep,
        nonblocking=True,
    )
    with pytest.raises(s._TransportTimeout, match="timeout"):
        transport.read_frame(expected_size=1, timeout_seconds=0.002)
    assert clock.sleeps and all(seconds > 0 for seconds in clock.sleeps)


def test_transport_rejects_oversized_frame():
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: (4, False),
        nonblocking=True,
    )
    with pytest.raises(s._TransportError, match="frame_oversize"):
        transport.read_frame(expected_size=3, max_size=3)


def test_transport_assembles_partial_reads_within_frame_bound():
    chunks = iter((b"a", b"bc"))
    available = iter(((3, False), (2, False), (0, True)))
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=lambda fd, size: next(chunks),
        nonblocking=True,
    )
    assert transport.read_frame(expected_size=3) == b"abc"


def test_transport_completes_partial_writes_and_rejects_broken_writes():
    writes = []

    def partial_write(fd, data):
        writes.append(data)
        return 1

    s._PipeTransport(1, 2, write=partial_write, nonblocking=True).write_control(b"abc")
    assert writes == [b"abc", b"bc", b"c"]
    clock = _ControlledClock()
    with pytest.raises(s._TransportTimeout, match="timeout"):
        s._PipeTransport(
            1,
            2,
            write=lambda fd, data: 0,
            clock=clock,
            sleep=clock.sleep,
            nonblocking=True,
        ).write_control(b"x", timeout_seconds=0.002)
    assert clock.sleeps and all(seconds > 0 for seconds in clock.sleeps)

    def broken_write(fd, data):
        raise OSError("broken")

    with pytest.raises(s._TransportError, match="write_failed"):
        s._PipeTransport(1, 2, write=broken_write, nonblocking=True).write_control(b"x")


def test_transport_handles_nonblocking_read_stall_then_completion():
    clock = _ControlledClock()
    available = iter(((1, False), (1, False), (0, False), (2, False), (0, True)))
    reads = iter((b"a", BlockingIOError(), b"bc"))

    def read(fd, size):
        value = next(reads)
        if isinstance(value, Exception):
            raise value
        return value

    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=read,
        clock=clock,
        sleep=clock.sleep,
        nonblocking=True,
    )
    assert transport.read_frame(expected_size=3, timeout_seconds=1) == b"abc"
    assert clock.sleeps and all(seconds > 0 for seconds in clock.sleeps)


def test_transport_times_out_during_nonblocking_read_stall():
    clock = _ControlledClock()
    reads = iter((b"a", BlockingIOError()))

    def read(fd, size):
        value = next(reads, BlockingIOError())
        if isinstance(value, Exception):
            raise value
        return value

    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: (1, False),
        read=read,
        clock=clock,
        sleep=clock.sleep,
        nonblocking=True,
    )
    with pytest.raises(s._TransportTimeout, match="timeout"):
        transport.read_frame(expected_size=2, timeout_seconds=0.002)
    assert clock.sleeps and all(seconds > 0 for seconds in clock.sleeps)


def test_transport_rejects_cumulative_split_oversize_and_trailing_data():
    available = iter(((2, False), (2, False)))
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=lambda fd, size: b"ab",
        nonblocking=True,
    )
    with pytest.raises(s._TransportError, match="trailing_data"):
        transport.read_frame(expected_size=3)

    available = iter(((3, False), (1, False)))
    transport = s._PipeTransport(
        1,
        2,
        peek=lambda fd: next(available),
        read=lambda fd, size: b"abc",
        nonblocking=True,
    )
    with pytest.raises(s._TransportError, match="trailing_data"):
        transport.read_frame(expected_size=3)


def test_acquisition_pipes_create_gate_then_data_and_clean_partial_creation(monkeypatch):
    events, closed, close_failures = [], [], {11}

    def factory():
        index = len(events) + 1
        events.append(f"pipe{index}")
        if index == 2:
            raise RuntimeError("data pipe failed")
        return 10, 11

    def close(fd):
        closed.append(fd)
        if fd in close_failures:
            close_failures.remove(fd)
            return s._CloseOutcome.RETRY
        return s._CloseOutcome.CLOSED

    monkeypatch.setattr(s._os, "close", close)
    with pytest.raises(s._CleanupError) as failure:
        s._pipes(factory, s._OwnerToken())
    assert events == ["pipe1", "pipe2"]
    assert closed == [11, 10]
    assert len(failure.value.owner._pending) == 1
    failure.value.owner.close()
    assert closed == [11, 10, 11] and not failure.value.owner._pending


def test_transaction_rolls_back_in_reverse_order_and_attempts_every_entry():
    events, failing = [], {"second", "third"}
    transaction = s._AcquisitionTransaction()

    def close(name):
        def action():
            events.append(name)
            if name in failing:
                failing.remove(name)
                raise RuntimeError(name)

        return action

    entries = [transaction.add(close(name)) for name in ("first", "second", "third")]
    equal_entry = s._AcquisitionEntry(entries[0].close)
    with pytest.raises(s._OwnershipError):
        transaction.release(equal_entry)
    with pytest.raises(s._CleanupError):
        transaction.rollback()
    assert events == ["third", "second", "first"]
    assert transaction._entries == [entries[1], entries[2]]
    transaction.rollback()
    assert events == ["third", "second", "first", "third", "second"]
    assert transaction._entries == []


def test_fd_cleanup_retains_compound_owner_across_real_fd_reuse():
    registry = s._GenerationRegistry()
    old_read, old_write = os.pipe()
    replacement_read = replacement_write = -1
    events = []
    try:
        old_generation, retry_state = s._GenerationToken(), [True]

        def closes_old_then_raises(identity):
            events.append("read")
            os.close(identity._number)
            raise OSError("closed before reporting failure")

        def retries_then_closes(identity):
            events.append("write")
            if retry_state:
                retry_state.pop()
                return s._CloseOutcome.RETRY
            os.close(identity._number)
            return s._CloseOutcome.CLOSED

        old_spec = s._new_endpoint_spec(old_read, old_generation, closes_old_then_raises)
        write_spec = s._new_endpoint_spec(old_write, old_generation, retries_then_closes)
        registry._register(old_spec._identity)
        registry._register(write_spec._identity)
        pair = s._IpcPair(old_spec, write_spec, s._OwnerToken(), registry)
        cleanup = s._FdCleanup([lambda: pair._close(pair._owner)])
        with pytest.raises(s._CleanupError) as failure:
            cleanup.close()
        assert failure.value.owner is cleanup
        assert isinstance(failure.value.__cause__, s._IndeterminateCleanupError)
        assert cleanup._pending and events == ["write", "read"]

        replacement_read, replacement_write = os.pipe()
        if replacement_read != old_read:
            os.dup2(replacement_read, old_read)
            os.close(replacement_read)
        replacement_read = -1
        cleanup.close()
        assert not cleanup._pending and events == ["write", "read", "write"]
        with pytest.raises(OSError):
            os.write(old_write, b"stale")
        os.write(replacement_write, b"x")
        assert os.read(old_read, 1) == b"x"
    finally:
        for fd in (old_read, old_write, replacement_read, replacement_write):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass


def test_fd_handle_and_inheritable_seams_validate_owned_inputs(monkeypatch):
    class Msvcrt:
        @staticmethod
        def get_osfhandle(fd):
            return 900 + fd

    monkeypatch.setitem(sys.modules, "msvcrt", Msvcrt)
    assert s._fd_handle(4) == 904
    with pytest.raises(s._OwnershipError):
        s._fd_handle(-1)
    calls = []
    monkeypatch.setattr(
        s._os,
        "set_handle_inheritable",
        lambda *args: calls.append(args),
        raising=False,
    )
    s._set_inheritable(904, True)
    assert calls == [(904, True)]
    with pytest.raises(s._OwnershipError):
        s._set_inheritable(-1, False)


def test_handle_reset_attempts_all_retains_failures_retries_and_owns_lock():
    class TrackingLock:
        def __init__(self):
            self.depth = 0
            self.observed = []

        def __enter__(self):
            self.depth += 1
            return self

        def __exit__(self, *args):
            self.depth -= 1

    lock, attempts, failing = TrackingLock(), [], {2}
    original = s._SPAWN_LOCK
    try:
        s._SPAWN_LOCK = lock

        def reset(handle, inheritable):
            lock.observed.append(lock.depth)
            attempts.append((handle, inheritable))
            if not inheritable and handle in failing:
                raise RuntimeError

        resetter = s._InheritableHandleReset(reset)
        for handle in (1, 2, 3):
            resetter.mark(handle)
        with pytest.raises(s._CleanupError):
            resetter.reset()
        assert attempts == [(1, False), (2, False), (3, False)]
        assert resetter._pending == [2] and lock.observed == [1, 1, 1]
        failing.clear()
        resetter.close()
        assert attempts[-1] == (2, False) and not resetter._pending
        assert all(depth == 1 for depth in lock.observed)
    finally:
        s._SPAWN_LOCK = original


@pytest.mark.parametrize("retry", (True, False))
def test_close_retries_or_retains_pending_owner(retry):
    supervisor = s._CodexSupervisor()
    transaction = s._AcquisitionTransaction()
    error = s._CleanupError
    transaction.rollback = Mock(side_effect=(error(), None if retry else error()))
    with pytest.raises(s._AcquisitionError):
        supervisor._abort(transaction, RuntimeError("acquisition failed"))
    if retry:
        supervisor.close()
    else:
        with pytest.raises(s._AcquisitionError):
            supervisor.close()
    assert supervisor._pending is (None if retry else transaction)
    assert supervisor._state.value == ("closed" if retry else "broken")


def test_empty_nonce_is_rejected_without_generating_a_replacement(monkeypatch):
    supervisor, _, _ = _prepared_supervisor(monkeypatch, [])
    monkeypatch.setattr(s, "_new_ready_nonce", pytest.fail)
    pytest.raises(s._AcquisitionError, supervisor.acquire, nonce=b"")


class _PreparedProcess:
    def __init__(self, events, handle="native"):
        self.events, self.handle, self.alive = events, handle, True

    @property
    def _handle(self):
        self.events.append("adapt")
        return self.handle

    def poll(self):
        self.events.append("poll")
        return None if self.alive else 0

    def terminate(self):
        self.events.append("terminate")
        self.alive = False

    def wait(self, timeout):
        self.events.append("wait")
        self.alive = False


class _PreparedJob:
    def __init__(self, events, assign_error=None):
        self.events, self.assign_error = events, assign_error

    def assign_borrowed_handle(self, handle):
        self.events.append(("assign", handle))
        if self.assign_error is not None:
            raise self.assign_error

    def close(self, timeout=2.0):
        self.events.append("job")


def _prepared_supervisor(monkeypatch, events, job=None, default_job=False):
    process = _PreparedProcess(events)
    job = None if default_job else job or _PreparedJob(events)
    pairs = iter(((10, 11), (12, 13)))

    def popen(command, **kwargs):
        events.append("popen")
        return process

    def set_inheritable(handle, value):
        events.append(("inherit", handle, value))

    def job_factory(api):
        events.append(("job_api", api))
        return job

    monkeypatch.setattr(s._os, "close", lambda fd: s._CloseOutcome.CLOSED)
    supervisor = s._CodexSupervisor(
        popen_factory=popen,
        pipe_factory=lambda: next(pairs),
        handle_adapter=lambda fd: 1000 + fd,
        set_inheritable=set_inheritable,
        job_factory=job_factory if not default_job else None,
        startup_factory=lambda: type("Startup", (), {})(),
    )
    return supervisor, process, job


def test_prepared_acquisition_owns_exact_handles_and_job_before_return(monkeypatch):
    events = []
    supervisor, process, _ = _prepared_supervisor(monkeypatch, events)
    prepared = supervisor.acquire(nonce=b"unit-a")
    inheritance = [
        event for event in events if isinstance(event, tuple) and event[0] == "inherit"
    ]
    assert inheritance == [
        ("inherit", 1010, True),
        ("inherit", 1013, True),
        ("inherit", 1010, False),
        ("inherit", 1013, False),
    ]
    api_index = next(
        index for index, event in enumerate(events) if event[0] == "job_api"
    )
    assert (
        events.index("popen")
        < events.index("adapt")
        < api_index
        < events.index(("assign", "native"))
    )
    assert prepared._helper._popen._popen is process
    assert prepared._descriptors == ((10, 11), (12, 13))
    assert supervisor._state is s._SupervisorState.PREPARED
    supervisor.close()
    assert (
        events.index("job") < events.index("poll")
        and supervisor._state is s._SupervisorState.CLOSED
    )


def test_default_job_factory_fails_safely_after_spawn_without_type_error(monkeypatch):
    events = []
    supervisor, process, _ = _prepared_supervisor(monkeypatch, events, default_job=True)
    with pytest.raises(s._AcquisitionError) as error:
        supervisor.acquire(nonce=b"unit-a")
    assert error.value.__cause__.__class__.__name__ == "_JobAcquisitionFailure"
    assert process.alive is False


def test_prepared_acquisition_serializes_acquire_and_close_state(monkeypatch):
    events = []
    supervisor, _, _ = _prepared_supervisor(monkeypatch, events)
    entered, release = s._threading.Event(), s._threading.Event()
    original = supervisor._popen_factory

    def blocked_popen(command, **kwargs):
        entered.set()
        release.wait(1)
        return original(command, **kwargs)

    supervisor._popen_factory = blocked_popen
    results = []

    def acquire():
        try:
            results.append(supervisor.acquire(nonce=b"unit-a"))
        except Exception as error:  # noqa: BLE001 - retain concurrent failure evidence
            results.append(error)

    first = s._threading.Thread(target=acquire)
    second = s._threading.Thread(target=acquire)
    first.start()
    assert entered.wait(1)
    second.start()
    release.set()
    first.join(2)
    second.join(2)
    assert sum(isinstance(result, s._PreparedAcquisition) for result in results) == 1
    assert sum(isinstance(result, s._OwnershipError) for result in results) == 1
    closer = s._threading.Thread(target=supervisor.close)
    again = s._threading.Thread(target=acquire)
    closer.start()
    again.start()
    closer.join(2)
    again.join(2)
    assert supervisor._state is s._SupervisorState.CLOSED


def test_prepared_helper_attachment_failure_rolls_back_or_retains_owner(monkeypatch):
    events = []
    job = _PreparedJob(events, assign_error=RuntimeError("assign"))
    supervisor, process, _ = _prepared_supervisor(monkeypatch, events, job=job)
    with pytest.raises(s._AcquisitionError) as error:
        supervisor.acquire(nonce=b"unit-a")
    assert process.alive is False
    assert error.value.owner is None or error.value.owner._entries
