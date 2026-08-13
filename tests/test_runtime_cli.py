import io
import json
import ntpath
import threading
import time
from types import SimpleNamespace

import pytest

import yasb_limitora.cli as cli
from yasb_limitora.cli import main
from yasb_limitora.codex_helper import CodexHelperExecutor, _payload
from yasb_limitora.config import LocalConfig
from yasb_limitora.coordinator import RuntimeCoordinator
from yasb_limitora.limitora_api import read_opencode_go
from yasb_limitora.model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
    V2SafeErrorCode,
)
from yasb_limitora.projection_v2 import V2ProjectionInput, project_v2_bytes, project_v2_failure_bytes, project_v2_not_run_bytes
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError
from yasb_limitora.v2_worker import V2ExecutionOrchestrator


def view(provider, state=ProviderState.SUCCESS, code=None, display_label=None):
    return ProviderView(provider, state, SafeError(code) if code else None, display_label)


class Codex:
    def __init__(self, result):
        self.result, self.runners = result, []
    def run(self, runner):
        self.runners.append(runner)
        return self.result


def enabled_config(codex=True, opencode=True, timeout=0.2):
    return LocalConfig.from_mapping({
        "codex": {"enabled": codex, "runner": r"C:\codex.exe", "timeout_seconds": timeout},
        "opencode_go": {"enabled": opencode, "workspace_id": "workspace", "timeout_seconds": timeout},
    })


def test_coordinator_preserves_mixed_outcomes_and_fixed_order():
    codex = Codex(view(ProviderKey.CODEX))
    document = RuntimeCoordinator(
        codex,
        lambda workspace, environment: view(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, SafeErrorCode.PROVIDER_ERROR),
    ).run(enabled_config(), {"LIMITORA_AUTH_COOKIE": "cookie"})
    assert tuple(v.provider for v in document.providers) == (ProviderKey.CODEX, ProviderKey.OPENCODE_GO)
    assert tuple(v.state for v in document.providers) == (ProviderState.SUCCESS, ProviderState.SAFE_ERROR)
    assert codex.runners == [(r"C:\codex.exe", "app-server")]


def test_coordinator_retries_retained_codex_cleanup_before_next_normal_invocation(monkeypatch):
    response = view(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeErrorCode.PROVIDER_ERROR)
    created, close_calls = [], []

    class Transport:
        def write_control(self, payload, *, timeout_seconds):
            return None

        def read_response(self, timeout_seconds):
            return _payload(response)

    monkeypatch.setattr("yasb_limitora.codex_helper._PersistentTransport", lambda *args, **kwargs: Transport())

    def factory(**kwargs):
        kwargs["transport_factory"](1, 2, nonblocking=True)
        index = len(created)

        def close(timeout):
            close_calls.append(index)
            if index == 0 and close_calls.count(0) == 1:
                raise RuntimeError("cleanup failure")

        supervisor = SimpleNamespace(_nonce=b"nonce", acquire=lambda: None, close=close)
        created.append(supervisor)
        return supervisor

    coordinator = RuntimeCoordinator(CodexHelperExecutor(factory, timeout_seconds=0.01))
    first = coordinator.run(enabled_config(opencode=False), {})
    second = coordinator.run(enabled_config(opencode=False), {})

    assert first.providers[0].error.code is SafeErrorCode.INTERNAL_ERROR
    assert second.providers[0].error.code is SafeErrorCode.PROVIDER_ERROR
    assert close_calls == [0, 0, 1]
    assert len(created) == 2


def test_opencode_timeout_discards_late_completion():
    release = threading.Event()
    late = view(ProviderKey.OPENCODE_GO, display_label="late")
    def reader(workspace, environment):
        release.wait(1)
        return late
    started = time.monotonic()
    document = RuntimeCoordinator(Codex(view(ProviderKey.CODEX)), reader).run(
        enabled_config(timeout=0.02), {"LIMITORA_AUTH_COOKIE": "cookie"}
    )
    assert time.monotonic() - started < 0.4
    assert document.providers[1] == view(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, SafeErrorCode.TIMEOUT)
    release.set()
    time.sleep(0.02)
    assert "late" not in repr(document)


def test_codex_timeout_does_not_erase_opencode_success():
    class SlowCodex:
        def run(self, runner):
            time.sleep(0.1)
            return view(ProviderKey.CODEX)
    document = RuntimeCoordinator(SlowCodex(), lambda *_: view(ProviderKey.OPENCODE_GO)).run(
        enabled_config(timeout=0.02), {"LIMITORA_AUTH_COOKIE": "cookie"}
    )
    assert document.providers[0].error.code is SafeErrorCode.TIMEOUT
    assert document.providers[1].state is ProviderState.SUCCESS


def test_concurrent_timeouts_use_invocation_deadlines_not_collection_order():
    release, started, calls = threading.Event(), [threading.Event(), threading.Event()], []
    def blocked(index, provider):
        started[index].set(); release.wait(1); return view(provider)
    class BlockedCodex:
        def run(self, runner): calls.append("codex"); return blocked(0, ProviderKey.CODEX)
    def blocked_opencode(workspace, environment): calls.append("opencode"); return blocked(1, ProviderKey.OPENCODE_GO)
    config = enabled_config(timeout=0.05)
    result, worker = {}, threading.Thread(target=lambda: result.setdefault("document", RuntimeCoordinator(BlockedCodex(), blocked_opencode).run(config, {"LIMITORA_AUTH_COOKIE": "cookie"})), daemon=True)
    started_at = time.monotonic()
    worker.start()
    assert all(event.wait(1) for event in started)
    worker.join(1)
    elapsed = time.monotonic() - started_at
    release.set()
    assert not worker.is_alive()
    document = result["document"]
    assert elapsed < config.codex.timeout_seconds * 1.6
    assert all(view.error.code is SafeErrorCode.TIMEOUT for view in document.providers)
    calls.clear()
    invalid = enabled_config()
    object.__setattr__(invalid.codex, "timeout_seconds", -1)
    object.__setattr__(invalid.opencode_go, "timeout_seconds", float("nan"))
    invalid_document = RuntimeCoordinator(BlockedCodex(), blocked_opencode).run(invalid, {"LIMITORA_AUTH_COOKIE": "cookie"})
    assert calls == [] and all(view.error.code is SafeErrorCode.CONFIGURATION_INVALID for view in invalid_document.providers)


@pytest.mark.parametrize("bad", [("--token", "secret"), ("--bad", "value"), ("--config",)])
def test_invalid_arguments_are_safe_and_exit_two(bad):
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(bad, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 2
    assert json.loads(stdout.getvalue())["providers"][0]["error"]["code"] == "invocation_invalid"
    assert "secret" not in stdout.getvalue().decode() + stderr.getvalue()


def test_missing_cookie_is_unavailable_and_streams_are_isolated():
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(
        (),
        coordinator=RuntimeCoordinator(Codex(view(ProviderKey.CODEX)), lambda *_: pytest.fail()),
        environment={}, stdout=stdout, stderr=stderr,
        platform_is_windows=lambda: True,
    )
    document = json.loads(stdout.getvalue())
    assert code == 0 and stderr.getvalue() == ""
    assert document["providers"][1] == {"provider": "opencode_go", "state": "unavailable"}


def test_runtime_safe_error_has_exit_one_and_sanitized_diagnostic():
    stdout, stderr = io.BytesIO(), io.StringIO()
    class FailingCoordinator:
        def run(self, config, environment):
            return DocumentView.ordered(
                view(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeErrorCode.TIMEOUT),
                view(ProviderKey.OPENCODE_GO),
            )
    coordinator = FailingCoordinator()
    assert main((), coordinator=coordinator, environment={"LIMITORA_AUTH_COOKIE": "cookie"}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 1
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
    assert "cookie" not in stdout.getvalue().decode() + stderr.getvalue()


def test_config_file_and_runtime_error_are_redacted(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": "relative"}}), encoding="utf-8")
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(("--config", str(path)), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 2
    assert "relative" not in stdout.getvalue().decode() + stderr.getvalue()
    assert stderr.getvalue() == "yasb-limitora: configuration_invalid\n"


def test_v2_default_resolution_reads_injected_localappdata(monkeypatch):
    paths = []
    localappdata = r"C:\Users\runtime-test\AppData\Local"

    def read_config(path):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "_read_config", read_config)
    coordinator = RuntimeCoordinator(
        Codex(view(ProviderKey.CODEX, ProviderState.UNAVAILABLE)),
        lambda *_: view(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main(
        ("--output-version", "2"),
        environment={"LOCALAPPDATA": localappdata},
        coordinator=coordinator,
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    ) == 0
    assert paths == [ntpath.join(localappdata, "yasb-limitora", "config.json")]
    assert json.loads(stdout.getvalue())["version"] == 2
    assert stderr.getvalue() == ""


def test_v2_cli_missing_opencode_credentials_is_clean_not_run(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"codex": {}, "opencode_go": {"enabled": True, "workspace_id": "workspace"}}),
        encoding="utf-8",
    )

    class Lease:
        def release(self):
            return True

        def close(self):
            return True

    class Guard:
        def acquire(self, path, context):
            return Lease()

    class Worker:
        record = None

        def run_with_deadline(self, workspace, environment, context):
            return read_opencode_go(workspace, environment)

    orchestrator = V2ExecutionOrchestrator(
        guard_factory=Guard,
        opencode_factory=Worker,
    )
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2", "--config", str(path)),
        environment={},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )

    data = stdout.getvalue()
    document = json.loads(data)
    assert code == 0
    assert stderr.getvalue() == ""
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
    assert document["execution_state"] == "not_run"
    assert document["execution_error"] is None
    assert all(provider["outcome"] == "not_run" for provider in document["providers"])
    assert all(provider["not_run_reason"] == "disabled" for provider in document["providers"])


def test_v2_configuration_failure_starts_no_provider(monkeypatch):
    starts = []

    def read_config(path):
        raise OSError("private config detail")

    class UnexpectedCoordinator:
        def run(self, config, environment):
            starts.append((config, environment))
            raise AssertionError("provider execution started after configuration failure")

    monkeypatch.setattr(cli, "_read_config", read_config)
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(
        ("--output-version", "2"),
        environment={"LOCALAPPDATA": r"C:\Users\runtime-test\AppData\Local"},
        coordinator=UnexpectedCoordinator(),
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    ) == 2
    assert json.loads(stdout.getvalue())["execution_error"] == {
        "code": "configuration_invalid",
        "phase": "configuration",
    }
    assert stderr.getvalue() == "yasb-limitora: configuration_invalid\n"
    assert starts == []


def test_success_bytes_have_one_newline_and_provider_order():
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main((), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)
    data = stdout.getvalue()
    assert code == 0 and stderr.getvalue() == "" and data.endswith(b"\n") and not data.endswith(b"\n\n")
    assert [item["provider"] for item in json.loads(data)["providers"]] == ["codex", "opencode_go"]


class _MatrixLease:
    def __init__(self, *, close=True):
        self.close_ok = close

    def release(self):
        return True

    def close(self):
        return self.close_ok


class _MatrixGuard:
    def __init__(self, *, error=None, lease=None):
        self.error = error
        self.lease = lease or _MatrixLease()

    def acquire(self, path, context):
        if self.error is not None:
            raise GuardError(self.error)
        return self.lease


class _MatrixCodex:
    def __init__(self):
        self.runners = []

    def run_with_deadline(self, runner, context):
        self.runners.append(runner)
        return ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED)


@pytest.mark.parametrize("scenario", ("guard_wait_timeout", "guard_acquisition_failed", "deadline_exhausted", "cleanup_failed"))
def test_v2_cli_runtime_matrix_has_exact_document_streams_and_exit(monkeypatch, tmp_path, scenario):
    path = tmp_path / "config.json"
    opencode_config = {"enabled": True, "workspace_id": "workspace"} if scenario == "deadline_exhausted" else {}
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": opencode_config}), encoding="utf-8")

    if scenario == "guard_wait_timeout":
        orchestrator = V2ExecutionOrchestrator(guard_factory=lambda: _MatrixGuard(error=scenario))
        expected = project_v2_not_run_bytes(scenario)
        expected_stderr = "yasb-limitora: guard_wait_timeout\n"
    elif scenario == "guard_acquisition_failed":
        orchestrator = V2ExecutionOrchestrator(guard_factory=lambda: _MatrixGuard(error=scenario))
        expected = project_v2_failure_bytes(scenario)
        expected_stderr = "yasb-limitora: runtime_error\n"
    elif scenario == "deadline_exhausted":
        orchestrator = V2ExecutionOrchestrator(guard_factory=_MatrixGuard)
        real_from_seconds = DeadlineContext.from_seconds
        calls = []

        def expired_after_config(cls, seconds, *, t0_ns=None, clock_ns=time.monotonic_ns):
            calls.append(seconds)
            if len(calls) == 2:
                return DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
            return real_from_seconds(seconds, t0_ns=t0_ns, clock_ns=clock_ns)

        monkeypatch.setattr(DeadlineContext, "from_seconds", classmethod(expired_after_config))
        expected = project_v2_not_run_bytes(scenario)
        expected_stderr = "yasb-limitora: runtime_error\n"
    else:
        codex = _MatrixCodex()
        orchestrator = V2ExecutionOrchestrator(
            guard_factory=lambda: _MatrixGuard(lease=_MatrixLease(close=False)),
            codex_executor=codex,
        )
        expected_document = DocumentView.ordered(
            ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED),
            ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled"),
            SafeError(V2SafeErrorCode.CLEANUP_FAILED),
        )
        expected = project_v2_bytes(V2ProjectionInput(expected_document, frozenset({ProviderKey.CODEX})))
        expected_stderr = "yasb-limitora: runtime_error\n"

    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(("--output-version", "2", "--config", str(path)), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)

    assert code == 1
    assert stdout.getvalue() == expected
    assert stdout.getvalue().endswith(b"\n") and not stdout.getvalue().endswith(b"\n\n")
    assert stderr.getvalue() == expected_stderr
    if scenario == "cleanup_failed":
        assert codex.runners == [(r"C:\\codex.exe", "app-server")]
