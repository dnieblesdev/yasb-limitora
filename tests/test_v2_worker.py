import io
import json
import pickle
import queue
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from yasb_limitora.cli import main
from yasb_limitora.config import LocalConfig
import yasb_limitora.limitora_api as limitora_api, yasb_limitora.v2_worker as v2_worker
from yasb_limitora.model import (
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    ProviderView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SafeErrorCode,
    SnapshotFreshness,
)
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError
from yasb_limitora.v2_worker import OpenCodeWorkerProcess, V2ExecutionOrchestrator, WorkerRecord, cleanup_complete
from yasb_limitora.limitora_api import OpenCodeReadResult, OpenCodeRequest


class Lease:
    def __init__(self, events, close=True):
        self.events, self.close_ok, self.owned = events, close, True
    def close(self):
        self.events.append("close-mutex"); self.owned = not self.close_ok; return self.close_ok
    def release(self):
        self.events.append("release-mutex"); self.owned = False; return True


class Guard:
    def __init__(self, lease): self.lease = lease
    def acquire(self, path, context): return self.lease


def context():
    return DeadlineContext(t0_ns=0, deadline_ns=10_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 0)


def test_opencode_request_is_the_only_secret_bearing_spawn_carrier():
    request = OpenCodeRequest("sentinel-api-key", 7.0)
    payload = pickle.dumps(request)
    assert b"sentinel-api-key" in payload and "sentinel-api-key" not in repr(request) and "sentinel-api-key" not in str(request)
    assert "sentinel-api-key" not in repr(OpenCodeReadResult(ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE))) and b"sentinel-api-key" not in pickle.dumps(OpenCodeReadResult(ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)))
def test_private_result_queue_and_v2_record_retention():
    result = OpenCodeReadResult(ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE), limitora_api.OpenCodeFailureEvidence.RATE_LIMITED)
    queued, output = [], type("Output", (), {"put": lambda self, value: queued.append(value)})()
    v2_worker._opencode_bootstrap(lambda request: result, OpenCodeRequest("sentinel-api-key", 7), output)
    assert queued == [result] and "sentinel-api-key" not in repr(queued[0])
    worker = type("Worker", (), {"record": None, "last_result": result, "run_with_deadline": lambda self, request, deadline: result.view})()
    config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})
    orchestrator = V2ExecutionOrchestrator(guard_factory=lambda: Guard(Lease([])), opencode_factory=lambda: worker)
    document = orchestrator.run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context(), "config")
    assert document.providers[1] is result.view and orchestrator.last_record.opencode_evidence is result.evidence


def test_opencode_child_start_receives_only_public_environment(monkeypatch):
    environment = {
        "PATH": "public-path",
        "LIMITORA_OPENCODE_API_KEY": "opencode-secret",
        "OPENAI_API_KEY": "openai-secret",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
    }
    monkeypatch.setattr(v2_worker.os, "environ", environment)
    observed = []

    class Process:
        pid, exitcode = 42, 0
        def __init__(self, target, args):
            pass
        def start(self):
            observed.append(dict(v2_worker.os.environ))
        def join(self, timeout=None):
            pass
        def is_alive(self):
            return False
        def close(self):
            pass

    class Job:
        active_processes = 0
        state = "assigned"
        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
        def close_with_deadline(self, deadline):
            self.state = "closed"

    class SpawnContext:
        def Queue(self):
            return queue.Queue()
        def Event(self):
            return type("Event", (), {"set": lambda self: None, "close": lambda self: None})()

    OpenCodeWorkerProcess(
        process_factory=lambda **kwargs: Process(kwargs["target"], kwargs["args"]),
        job_factory=Job,
        context_factory=lambda _: SpawnContext(),
    ).run_with_deadline(OpenCodeRequest("request-secret", 7), context())

    assert observed == [{"PATH": "public-path"}]
    assert v2_worker.os.environ is environment
    assert environment["LIMITORA_OPENCODE_API_KEY"] == "opencode-secret"


def test_provider_configuration_error_skips_only_invalid_provider():
    launches = []
    config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})

    class Worker:
        record = None
        last_result = None
        def run_with_deadline(self, request, deadline):
            launches.append(ProviderKey.OPENCODE_GO)
            return ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)

    document = V2ExecutionOrchestrator(
        guard_factory=lambda: Guard(Lease([])),
        opencode_factory=Worker,
    ).run(
        config,
        {"LIMITORA_OPENCODE_API_KEY": "key"},
        context(),
        "config",
        provider_errors={ProviderKey.CODEX},
    )

    assert launches == [ProviderKey.OPENCODE_GO]
    assert document.providers[0].error.code is SafeErrorCode.CONFIGURATION_INVALID


def test_reused_orchestrator_retains_only_current_opencode_evidence():
    view = ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)
    results = [
        OpenCodeReadResult(view, limitora_api.OpenCodeFailureEvidence.RATE_LIMITED),
        OpenCodeReadResult(view, limitora_api.OpenCodeFailureEvidence.TIMEOUT),
        OpenCodeReadResult(view),
    ]

    class Worker:
        record = None

        def __init__(self, result):
            self.result = result
            self.last_result = None

        def run_with_deadline(self, request, deadline):
            self.last_result = self.result
            return self.result.view

    workers = [Worker(result) for result in results]
    config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})
    orchestrator = V2ExecutionOrchestrator(
        guard_factory=lambda: Guard(Lease([])),
        opencode_factory=lambda: workers.pop(0),
    )

    for expected in (results[0], results[1], results[2]):
        orchestrator.run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context(), "config")
        assert orchestrator.last_record.opencode_evidence is expected.evidence

    assert len(orchestrator.workers) == 3


def test_disabled_or_codex_only_run_clears_previous_opencode_evidence():
    result = OpenCodeReadResult(
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
        limitora_api.OpenCodeFailureEvidence.RATE_LIMITED,
    )
    worker = type(
        "Worker",
        (),
        {
            "record": None,
            "last_result": result,
            "run_with_deadline": lambda self, request, deadline: result.view,
        },
    )
    open_config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})
    disabled_config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": False}})
    codex_config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}})
    codex_view = ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS)
    codex = type("Codex", (), {"run_with_deadline": lambda self, runner, deadline: codex_view})()
    orchestrator = V2ExecutionOrchestrator(
        guard_factory=lambda: Guard(Lease([])),
        codex_executor=codex,
        opencode_factory=lambda: worker(),
    )

    orchestrator.run(open_config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context(), "config")
    assert orchestrator.last_record.opencode_evidence is result.evidence

    orchestrator.run(disabled_config, {}, context(), "config")
    assert orchestrator.last_record is not None and orchestrator.last_record.opencode_evidence is None

    orchestrator.run(codex_config, {}, context(), "config")
    assert orchestrator.last_record.opencode_evidence is None
    assert len(orchestrator.workers) == 1


def test_cleanup_complete_requires_all_worker_evidence():
    record = WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, job_closed=True, process_closed=True)
    assert cleanup_complete([record])
    record.process_closed = False
    assert not cleanup_complete([record])
    job = type("Job", (), {"active_processes": 0, "state": "assigned", "calls": 0, "close_with_deadline": lambda self, _: setattr(self, "calls", self.calls + 1)})()
    record = WorkerRecord(object(), job, reaped=True, exit_code=0, job_active_zero=True, process_closed=True)
    worker = type("Worker", (), {"record": record, "run_with_deadline": lambda self, request, deadline: (job.close_with_deadline(deadline) or ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS))})()
    events = []; lease = Lease(events); acquired = []
    SerialGuard = type("SerialGuard", (), {"acquire": lambda self, path, deadline: (_ for _ in ()).throw(GuardError("guard_wait_timeout")) if acquired else (acquired.append(True) or lease)})
    config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})
    orchestrator = V2ExecutionOrchestrator(guard_factory=SerialGuard, opencode_factory=lambda: worker)
    result = orchestrator.run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context(), "config")
    assert job.calls == 2 and not record.job_closed and record.process_closed and not cleanup_complete([record]) and result.document_error.code.value == "cleanup_failed" and events == [] and lease.owned
    later = orchestrator.run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context(), "config")
    assert later.document_error.code.value == "cleanup_failed"
    job.state = "closed"; record.job_closed = True
    assert cleanup_complete([record])
def test_cleanup_complete_requires_opencode_and_codex_quiescence():
    records = [
        WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, job_closed=True, process_closed=True),
        WorkerRecord(object(), object(), reaped=True, exit_code=0, job_active_zero=True, job_closed=True, process_closed=True),
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
        def close(self): events.append("process-close"); raise OSError("close failed")

    class Context:
        def Queue(self): return queue.Queue()
        def Event(self): return Event()
        def Process(self, target, args): return Process(target, args)

    class Job:
        active_processes = 0
        state = "assigned"
        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
            events.append("job-assign")
        def close_with_deadline(self, context): events.append("job-close"); self.state = "closed"

    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        reader=lambda request: (_ for _ in ()).throw(AssertionError("provider ran")),
        process_factory=lambda **kwargs: Process(kwargs["target"], kwargs["args"]),
        job_factory=Job,
        context_factory=lambda _name: Context(),
    )
    worker.run_with_deadline(OpenCodeRequest("secret", 7), context())
    assert events[:3] == ["process-start", "job-assign", "provider-release"] and events.index("process-close") > events.index("job-close") and worker.record is not None and worker.record.reaped and worker.record.job_closed and not worker.record.process_closed
def test_prestart_deadline_exhaustion_marks_opencode_not_run_without_spawning():
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        process_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider spawned")),
    )

    result = worker.run_with_deadline(OpenCodeRequest("secret", 7), expired)

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


def test_codex_exhaustion_skips_opencode_request_construction_and_returns_not_run():
    clock = [0]; Codex = type("Codex", (), {"run_with_deadline": lambda self, runner, deadline: (clock.__setitem__(0, 2_000) or ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS))}); config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {"enabled": True}}); context = DeadlineContext(0, 1_000, 0, lambda: clock[0])
    document = V2ExecutionOrchestrator(guard_factory=lambda: Guard(Lease([])), codex_executor=Codex(), opencode_factory=lambda: pytest.fail("OpenCode worker constructed after deadline exhaustion")).run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, context, r"C:\\config.json")
    assert (document.providers[1].outcome, document.providers[1].not_run_reason) == (ProviderOutcome.NOT_RUN, "deadline_exhausted")
def test_opencode_budget_sampling_handles_clock_expiry_race():
    clock = iter((0, 0, 1)); requests = []; Worker = type("Worker", (), {"record": None, "run_with_deadline": lambda self, request, context: (requests.append(request) or ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS))}); config = LocalConfig.from_v2_mapping({"codex": {}, "opencode_go": {"enabled": True}})
    document = V2ExecutionOrchestrator(guard_factory=lambda: Guard(Lease([])), opencode_factory=Worker).run(config, {"LIMITORA_OPENCODE_API_KEY": "key"}, DeadlineContext(0, 1, 0, lambda: next(clock)), "config")
    assert document.providers[1].state is ProviderState.SUCCESS
    assert requests and requests[0].timeout_seconds > 0
def test_opencode_start_failure_closes_unstarted_process_and_queue_handles():
    events = []; Queue = type("Queue", (), {"cancel_join_thread": lambda self: events.append("queue-cancel"), "close": lambda self: events.append("queue-close")}); Process = type("Process", (), {"pid": 42, "exitcode": None, "start": lambda self: (events.append("process-start") or (_ for _ in ()).throw(RuntimeError("start failed"))), "is_alive": lambda self: (_ for _ in ()).throw(AssertionError("unstarted process queried")), "join": lambda self, timeout=None: (_ for _ in ()).throw(AssertionError("unstarted process joined")), "close": lambda self: events.append("process-close")})
    Context = type("Context", (), {"Queue": lambda self: Queue(), "Event": lambda self: type("Event", (), {})()}); worker = OpenCodeWorkerProcess(process_factory=lambda **kwargs: Process(), context_factory=lambda _name: Context()); result = worker.run_with_deadline(OpenCodeRequest("secret", 7), context())
    assert result.error.code is SafeErrorCode.PROVIDER_ERROR and events == ["process-start", "process-close", "queue-cancel", "queue-close"] and worker.record is not None and worker.record.reaped and worker.record.process_closed and not worker.record.started and worker.record.exit_code is None
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

        def terminate(self):
            self.alive = False
        def close(self):
            self.closed = True
    class Job:
        active_processes = 0
        state = "assigned"

        def assign_process(self, pid, *, allow_nested=False):
            assert allow_nested is True
            pass

        def close_with_deadline(self, context):
            self.state = "closed"

    worker = __import__("yasb_limitora.v2_worker", fromlist=["OpenCodeWorkerProcess"]).OpenCodeWorkerProcess(
        process_factory=lambda **kwargs: Process(kwargs["target"], kwargs["args"]),
        job_factory=Job,
        context_factory=lambda _name: type("Context", (), {"Queue": lambda self: queue.Queue(), "Event": lambda self: type("Event", (), {"set": lambda self: None})()})(),
    )

    result = worker.run_with_deadline(OpenCodeRequest("secret", 7), context())

    assert result.outcome is ProviderOutcome.EXECUTION_ERROR
    assert result.error is not None
    assert result.error.code is SafeErrorCode.TIMEOUT
    assert worker.record is not None and worker.record.reaped and worker.record.job_closed and worker.record.process_closed
    assert worker.last_result is not None and worker.last_result.evidence.value == "timeout"


def test_orchestrator_preserves_outcomes_when_mutex_cleanup_fails():
    events, lease = [], Lease([], close=False)
    lease.events = events
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}})
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    snapshot = ProviderSnapshotView(
        PublicProviderState.PARTIAL,
        SnapshotFreshness.FRESH,
        now,
        now,
        now,
        "codex-app-server-v2",
        (QuotaWindowView(
            QuotaWindowKind.COMMERCIAL_QUOTA,
            "account",
            "weekly",
            None,
            QuotaAvailability.KNOWN,
            "codex-app-server-v2",
            remaining=QuotaQuantity(Decimal("75"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points"),
        ),),
    )
    expected = ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, outcome=ProviderOutcome.SNAPSHOT, snapshot=snapshot)
    executor = type("Executor", (), {"run_with_deadline": lambda self, runner, deadline: expected})()
    document = V2ExecutionOrchestrator(guard_factory=lambda: Guard(lease), codex_executor=executor).run(config, {}, context(), r"C:\config.json")
    assert document.document_error.code.value == "cleanup_failed"
    assert document.providers[0] == expected
    assert document.providers[1].outcome is ProviderOutcome.NOT_RUN
    assert events == ["release-mutex", "close-mutex"]


def test_retries_only_lease_close_after_release_succeeds():
    class FirstLease:
        __slots__ = ("release_calls", "close_calls", "owned", "closed")

        def __init__(self):
            self.release_calls = 0
            self.close_calls = 0
            self.owned = True
            self.closed = False

        def release(self):
            self.release_calls += 1
            if self.release_calls > 1:
                raise AssertionError("released lease must not be released again")
            self.owned = False
            return True

        def close(self):
            self.close_calls += 1
            self.closed = self.close_calls == 2
            return self.closed

    first = FirstLease()
    later = Lease([])
    leases = iter((first, later))
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}})
    executor = type(
        "Executor",
        (),
        {"run_with_deadline": lambda self, runner, deadline: ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)},
    )()
    orchestrator = V2ExecutionOrchestrator(guard_factory=lambda: Guard(next(leases)), codex_executor=executor)

    first_document = orchestrator.run(config, {}, context(), "config")
    second_document = orchestrator.run(config, {}, context(), "config")

    assert first_document.document_error.code.value == "cleanup_failed"
    assert second_document.document_error is None
    assert (first.release_calls, first.close_calls) == (1, 2)


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

    assert main(("--output-version", "2", "--config", str(config_path)), environment={"LOCALAPPDATA": str(tmp_path)}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 2
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
