import io
import json

from yasb_limitora.cli import main
from yasb_limitora.config import LocalConfig
from yasb_limitora.model import ProviderKey, ProviderOutcome, ProviderState, ProviderView
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


def test_orchestrator_preserves_outcomes_when_mutex_cleanup_fails():
    events, lease = [], Lease([], close=False)
    lease.events = events
    config = LocalConfig.from_v2_mapping({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}})
    executor = type("Executor", (), {"run_with_deadline": lambda self, runner, deadline: ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)})()
    document = V2ExecutionOrchestrator(guard_factory=lambda: Guard(lease), codex_executor=executor).run(config, {}, context(), r"C:\config.json")
    assert document.document_error.code.value == "cleanup_failed"
    assert tuple(view.outcome for view in document.providers) == (ProviderOutcome.UNDETECTED, ProviderOutcome.NOT_RUN)
    assert events == ["close-mutex", "release-mutex"]


def test_v2_default_path_fails_closed_without_a_process_local_lock(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\codex.exe"}, "opencode_go": {}}), encoding="utf-8")
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(("--output-version", "2", "--config", str(config)), stdout=stdout, stderr=stderr)
    projected = json.loads(stdout.getvalue())
    assert code == 1
    assert projected["execution_error"]["code"] in {"guard_acquisition_failed", "cleanup_failed"}
    if projected["execution_error"]["code"] == "guard_acquisition_failed":
        assert all(item["not_run_reason"] == "document_aborted" for item in projected["providers"])
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
