import queue; import os
from types import SimpleNamespace
import pytest

from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora import v2_path
from yasb_limitora.isolation.windows_job import JobError, JobErrorCode
from yasb_limitora.v2_path import V2DeadlineError, V2FileError, read_v2_config


def _context():
    return DeadlineContext(t0_ns=0, deadline_ns=10_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 0)
class _ReadOutput:
    def __init__(self, result=None, error=None): self.result, self.error, self.timeouts, self.closed = result, error, [], False
    def get(self, timeout=None): self.timeouts.append(timeout); return self._raise_or_result()
    def _raise_or_result(self): return self.result if self.error is None else (_ for _ in ()).throw(self.error)
    def close(self): self.closed = True
class _ReadProcess:
    pid = 7
    def __init__(self, events): self.events, self.alive, self.authorized, self.terminated = events, True, False, False
    def start(self): self.events.append("start")
    def join(self, timeout=None): self.events.append(("join", timeout)); self.alive &= not self.authorized
    def is_alive(self): return self.alive
    def terminate(self): self.events.append("terminate"); self.terminated = True; self.alive = False
def _bounded_harness(monkeypatch, job_factory, output):
    events = []; process = _ReadProcess(events)
    job = job_factory(events, process)
    context = SimpleNamespace(Queue=lambda: output, Event=lambda: SimpleNamespace(set=lambda: (events.append("authorize"), setattr(process, "authorized", True))), Process=lambda target, args: process)
    monkeypatch.setattr(v2_path, "os", SimpleNamespace(name="nt")); monkeypatch.setattr(v2_path.multiprocessing, "get_all_start_methods", lambda: ["fork"]); monkeypatch.setattr(v2_path.multiprocessing, "get_context", lambda method: context); monkeypatch.setattr("yasb_limitora.isolation.windows_job.WindowsJobBoundary", lambda: job)
    return events, process
class _ReadJob:
    def __init__(self, events, process, nested=False, error=None, assignment_error=None): self.events, self.process, self.nested, self.error, self.assignment_error = events, process, nested, error, assignment_error
    def is_process_externally_contained(self, pid): self.events.append("preflight"); self.error and (_ for _ in ()).throw(self.error); assert self.process.alive and not self.process.authorized if self.nested else True; return self.nested
    def assign_process(self, pid): self.events.append("assign"); self.assignment_error and (_ for _ in ()).throw(self.assignment_error)
    def close_with_deadline(self, context): self.events.append("dispose" if self.nested else "close")
@pytest.mark.parametrize("kwargs, expected", [({"nested": True}, ["start", "preflight", "dispose", "authorize", ("join", 0.1), ("join", 9.75)]), ({}, ["start", "preflight", "assign", "authorize", ("join", 0.1), ("join", 9.75), "close"])])
def test_bounded_read_preserves_nested_and_private_lifecycle(monkeypatch, kwargs, expected):
    output = _ReadOutput((True, b"{}")); events, process = _bounded_harness(monkeypatch, lambda events, process: _ReadJob(events, process, **kwargs), output)
    assert v2_path._bounded_file_read("config", _context()) == b"{}" and events == expected and output.closed and not process.terminated
@pytest.mark.parametrize("error", [JobError(JobErrorCode.ASSIGNMENT_FAILED), JobError(JobErrorCode.INTERNAL_ERROR)])
def test_bounded_read_rejects_job_failure_without_authorization(monkeypatch, error):
    output = _ReadOutput((True, b"{}")); events, process = _bounded_harness(monkeypatch, lambda events, process: _ReadJob(events, process, error=error) if error.code is JobErrorCode.INTERNAL_ERROR else _ReadJob(events, process, assignment_error=error), output)
    with pytest.raises(V2FileError): v2_path._bounded_file_read("config", _context())
    assert events == ["start", "preflight", "close", "terminate", ("join", 0.25)] if error.code is JobErrorCode.INTERNAL_ERROR else events == ["start", "preflight", "assign", "close", "terminate", ("join", 0.25)]
    assert process.terminated and "authorize" not in events
def test_bounded_read_receive_is_deadline_bounded_after_process_exit(monkeypatch):
    output = _ReadOutput(error=queue.Empty())
    events, process = _bounded_harness(monkeypatch, lambda events, process: _ReadJob(events, process, nested=True), output)
    with pytest.raises(V2DeadlineError, match="configuration deadline exhausted"): v2_path._bounded_file_read("config", _context())
    assert output.timeouts == [9.75] and output.closed and process.terminated and any(event[0] == "join" and event[1] == 0.25 for event in events if isinstance(event, tuple))


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
