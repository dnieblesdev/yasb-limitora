import io
import json
import queue

import pytest

from yasb_limitora.cli import main
from yasb_limitora.config import LocalConfig
from yasb_limitora.model import ProviderKey, ProviderOutcome, ProviderState, ProviderView, SafeErrorCode
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_worker import V2ExecutionOrchestrator, WorkerRecord, cleanup_complete


class Lease:
    def __init__(self, events, close=True):
        self.events, self.close_ok, self.owned = events, close, True
    def close(self):
        self.events.append("close-mutex")
        return self.close_ok
    def release(self):
        self.events.append("release-mutex")
        return True


class Guard:
    def __init__(self, lease): self.lease = lease
    def acquire(self, path, context): return self.lease


def context():
    return DeadlineContext(t0_ns=0, deadline_ns=10_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 0)


def test_cleanup_complete_requires_all_worker_evidence():
    record = WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, handles_closed=True)
    assert cleanup_complete([record])
    record.handles_closed = False
    assert not cleanup_complete([record])


def test_cleanup_complete_requires_opencode_and_codex_quiescence():
    records = [
        WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, handles_closed=True),
        WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, handles_closed=True),
    ]
    supervisor = type("Supervisor", (), {"_state": "closed", "_pending": None, "_prepared": None, "_helper": None, "_gate": None, "_data": None})()
    helper = type("Helper", (), {"_pending_supervisor": None, "_active": False, "_retrying": False, "_last_supervisor": supervisor})()
    assert cleanup_complete(records, supervisors=(supervisor,), helpers=(helper,))
    supervisor._pending = object()
    assert not cleanup_complete(records, supervisors=(supervisor,), helpers=(helper,))


def test_opencode_authorizes_job_before_releasing_provider_start():
    events = []

    class Event:
        def set(self): events.append("provider-release")
        def wait(self): events.append("provider-wait")

    class Process:
        pid, exitcode = 42, 0
        def __init__(self, target, args): self.target, self.args = target, args
        def start(self): events.append("process-start")
        def join(self, timeout=None): events.append("process-join")
        def is_alive(self): return False

    class Context:
        def Queue(self): return queue.Queue()
        def Event(self): return Event()
        def Process(self, target, args): return Process(target, args)

    class Job:
        active_processes = 0
        state = "assigned"
        def assign_process(self, pid): events.append("job-assign")
        def close_with_deadline(self, context): events.append("job-close"); self.state = "closed"

    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        reader=lambda workspace, environment: (_ for _ in ()).throw(AssertionError("provider ran")),
        process_factory=lambda **kwargs: Process(kwargs["target"], kwargs["args"]),
        job_factory=Job,
        context_factory=lambda _name: Context(),
    )
    worker.run_with_deadline("workspace", {}, context())
    assert events[:3] == ["process-start", "job-assign", "provider-release"]


def test_prestart_deadline_exhaustion_marks_opencode_not_run_without_spawning():
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        process_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider spawned")),
    )

    result = worker.run_with_deadline("workspace", {}, expired)

    assert result.outcome is ProviderOutcome.NOT_RUN
    assert result.not_run_reason == "deadline_exhausted"


def test_prestart_deadline_exhaustion_retries_pending_codex_cleanup():
    closed = []

    class Supervisor:
        def close_with_deadline(self, deadline):
            closed.append(deadline)

    from yasb_limitora.codex_helper import CodexHelperExecutor

    executor = CodexHelperExecutor()
    executor._pending_supervisor = Supervisor()
    clock = iter((0, 200))
    expiring = DeadlineContext(t0_ns=0, deadline_ns=100, reserve_ns=0, clock_ns=lambda: next(clock))
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}})

    document = V2ExecutionOrchestrator(
        guard_factory=lambda: Guard(Lease([])),
        codex_executor=executor,
    ).run(config, {}, expiring, r"C:\config.json")

    assert document.document_error is None
    assert document.providers[0].outcome is ProviderOutcome.NOT_RUN
    assert document.providers[0].not_run_reason == "deadline_exhausted"
    assert closed == [expiring]
    assert executor._pending_supervisor is None


def test_started_opencode_overrun_remains_provider_timeout():
    class Process:
        pid, exitcode = 42, None

        def __init__(self, target, args):
            self.alive = True

        def start(self):
            pass

        def join(self, timeout=None):
            pass

        def is_alive(self):
            return self.alive

    class Job:
        active_processes = 0
        state = "assigned"

        def assign_process(self, pid):
            pass

        def close_with_deadline(self, context):
            self.state = "closed"

    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        process_factory=lambda **kwargs: Process(kwargs["target"], kwargs["args"]),
        job_factory=Job,
        context_factory=lambda _name: type("Context", (), {"Queue": lambda self: queue.Queue(), "Event": lambda self: type("Event", (), {"set": lambda self: None})()})(),
    )

    result = worker.run_with_deadline("workspace", {}, context())

    assert result.outcome is ProviderOutcome.EXECUTION_ERROR
    assert result.error is not None
    assert result.error.code is SafeErrorCode.TIMEOUT


def test_orchestrator_preserves_outcomes_when_mutex_cleanup_fails():
    events, lease = [], Lease([], close=False)
    lease.events = events
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}})
    executor = type("Executor", (), {"run_with_deadline": lambda self, runner, deadline: ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)})()
    document = V2ExecutionOrchestrator(guard_factory=lambda: Guard(lease), codex_executor=executor).run(config, {}, context(), r"C:\config.json")
    assert document.document_error.code.value == "cleanup_failed"
    assert tuple(view.outcome for view in document.providers) == (ProviderOutcome.UNDETECTED, ProviderOutcome.NOT_RUN)
    assert events == ["release-mutex", "close-mutex"]


def test_unexpected_provider_exception_is_not_relabelled_as_guard_failure():
    events, lease = [], Lease([])
    lease.events = events
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}})

    class ExplodingExecutor:
        def run_with_deadline(self, runner, deadline):
            raise RuntimeError("private provider detail")

    orchestrator = V2ExecutionOrchestrator(guard_factory=lambda: Guard(lease), codex_executor=ExplodingExecutor())
    with pytest.raises(RuntimeError, match="private provider detail"):
        orchestrator.run(config, {}, context(), r"C:\config.json")
    assert events == ["release-mutex", "close-mutex"]


def test_unexpected_provider_exception_emits_schema_safe_internal_document(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}}), encoding="utf-8")
    lease = Lease([])

    class ExplodingExecutor:
        def run_with_deadline(self, runner, deadline):
            raise RuntimeError("private provider detail")

    monkeypatch.setattr(
        "yasb_limitora.cli.V2ExecutionOrchestrator",
        lambda: V2ExecutionOrchestrator(guard_factory=lambda: Guard(lease), codex_executor=ExplodingExecutor()),
    )
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main(("--output-version", "2", "--config", str(config_path)), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 1
    document = json.loads(stdout.getvalue())
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert all(provider["not_run_reason"] == "document_aborted" for provider in document["providers"])
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"


def test_v2_default_path_fails_closed_without_a_process_local_lock(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}}), encoding="utf-8")
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(("--output-version", "2", "--config", str(config)), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)
    projected = json.loads(stdout.getvalue())
    assert code == 1
    assert projected["execution_error"]["code"] in {"guard_acquisition_failed", "cleanup_failed", "provider_failed"}
    if projected["execution_error"]["code"] == "guard_acquisition_failed":
        assert all(item["not_run_reason"] == "document_aborted" for item in projected["providers"])
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
