import io
import json
import ntpath
import threading
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest

from yasb_limitora import cli
from yasb_limitora.cli import main
from yasb_limitora.codex_helper import CodexHelperExecutor, _payload
from yasb_limitora.config import LocalConfig
from yasb_limitora.coordinator import RuntimeCoordinator
from yasb_limitora.limitora_api import (
    OpenCodeFailureEvidence,
    OpenCodeReadResult,
    OpenCodeRequest,
    read_opencode_go,
)
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
from yasb_limitora.projection_v2 import (
    V2ProjectionInput,
    project_v2_bytes,
    project_v2_failure_bytes,
    project_v2_not_run_bytes,
)
from yasb_limitora.v2_cache import SingleFlightResult, V2QuotaCache
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError, V2Guard
from yasb_limitora.v2_worker import OpenCodeWorkerProcess, V2ExecutionOrchestrator


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
        "opencode_go": {"enabled": opencode, "timeout_seconds": timeout},
    })


def test_coordinator_preserves_mixed_outcomes_and_fixed_order():
    codex = Codex(view(ProviderKey.CODEX))
    document = RuntimeCoordinator(
        codex,
        lambda request: OpenCodeReadResult(view(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, SafeErrorCode.PROVIDER_ERROR)),
    ).run(enabled_config(), {"LIMITORA_OPENCODE_API_KEY": "key"})
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

    assert first.providers[0].error is not None
    assert first.providers[0].error.code is SafeErrorCode.INTERNAL_ERROR
    assert second.providers[0].error is not None
    assert second.providers[0].error.code is SafeErrorCode.PROVIDER_ERROR
    assert close_calls == [0, 0, 1]
    assert len(created) == 2


def test_opencode_timeout_discards_late_completion():
    release = threading.Event()
    late = view(ProviderKey.OPENCODE_GO, display_label="late")
    def reader(request):
        release.wait(1)
        return OpenCodeReadResult(late)
    started = time.monotonic()
    document = RuntimeCoordinator(Codex(view(ProviderKey.CODEX)), reader).run(
        enabled_config(timeout=0.02), {"LIMITORA_OPENCODE_API_KEY": "key"}
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
    document = RuntimeCoordinator(SlowCodex(), lambda *_: OpenCodeReadResult(view(ProviderKey.OPENCODE_GO))).run(
        enabled_config(timeout=0.02), {"LIMITORA_OPENCODE_API_KEY": "key"}
    )
    assert document.providers[0].error is not None
    assert document.providers[0].error.code is SafeErrorCode.TIMEOUT
    assert document.providers[1].state is ProviderState.SUCCESS


def test_concurrent_timeouts_use_invocation_deadlines_not_collection_order():
    release, started, calls = threading.Event(), [threading.Event(), threading.Event()], []
    def blocked(index, provider):
        started[index].set(); release.wait(1); return view(provider)
    class BlockedCodex:
        def run(self, runner): calls.append("codex"); return blocked(0, ProviderKey.CODEX)
    def blocked_opencode(request): calls.append("opencode"); return OpenCodeReadResult(blocked(1, ProviderKey.OPENCODE_GO))
    config = enabled_config(timeout=0.05)
    result, worker = {}, threading.Thread(target=lambda: result.setdefault("document", RuntimeCoordinator(BlockedCodex(), blocked_opencode).run(config, {"LIMITORA_OPENCODE_API_KEY": "key"})), daemon=True)
    started_at = time.monotonic()
    worker.start()
    assert all(event.wait(1) for event in started)
    worker.join(1)
    elapsed = time.monotonic() - started_at
    release.set()
    assert not worker.is_alive()
    document = result["document"]
    assert elapsed < config.codex.timeout_seconds * 1.6
    for provider_view in document.providers:
        assert provider_view.error is not None
        assert provider_view.error.code is SafeErrorCode.TIMEOUT
    calls.clear()
    invalid = enabled_config()
    object.__setattr__(invalid.codex, "timeout_seconds", -1)
    object.__setattr__(invalid.opencode_go, "timeout_seconds", float("nan"))
    invalid_document = RuntimeCoordinator(BlockedCodex(), blocked_opencode).run(invalid, {"LIMITORA_OPENCODE_API_KEY": "key"})
    assert calls == []
    for provider_view in invalid_document.providers:
        assert provider_view.error is not None
        assert provider_view.error.code is SafeErrorCode.CONFIGURATION_INVALID


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

        coordinator=RuntimeCoordinator(
            Codex(view(ProviderKey.CODEX)),
            cast(Callable[[OpenCodeRequest], OpenCodeReadResult], lambda _request: pytest.fail("reader must not run without credentials")),
        ),
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
    assert main((), coordinator=cast(RuntimeCoordinator, coordinator), environment={"LIMITORA_OPENCODE_API_KEY": "key"}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 1

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
        cast(Callable[[OpenCodeRequest], OpenCodeReadResult], lambda _request: pytest.fail("reader must not run without credentials")),
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
    assert "version" not in json.loads(stdout.getvalue())
    assert stderr.getvalue() == ""


def test_v2_cli_missing_opencode_credentials_is_clean_not_run(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"codex": {}, "opencode_go": {"enabled": True}}),
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

        def run_with_deadline(self, request, context):
            return read_opencode_go(request).view

    orchestrator = V2ExecutionOrchestrator(
        guard_factory=cast(type[V2Guard], Guard),
        opencode_factory=cast(type[OpenCodeWorkerProcess], Worker),
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


@pytest.mark.parametrize(
    ("evidence", "expected"),
    (
        (OpenCodeFailureEvidence.CREDENTIAL_INVALID, "credential_invalid"),
        (OpenCodeFailureEvidence.RATE_LIMITED, "provider_rate_limited"),
    ),
)
def test_v2_cli_consumes_private_opencode_evidence_sidecar(evidence, expected, monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {}, "opencode_go": {"enabled": True}}), encoding="utf-8")

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

        def __init__(self):
            self.last_result = None

        def run_with_deadline(self, request, context):
            view = ProviderView(
                ProviderKey.OPENCODE_GO,
                ProviderState.SAFE_ERROR,
                SafeError(SafeErrorCode.PROVIDER_ERROR),
                outcome=ProviderOutcome.EXECUTION_ERROR,
            )
            self.last_result = OpenCodeReadResult(view, evidence)
            return view

    orchestrator = V2ExecutionOrchestrator(
        guard_factory=cast(type[V2Guard], Guard),
        opencode_factory=cast(type[OpenCodeWorkerProcess], Worker),
    )
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2", "--config", str(path)),
        environment={"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "private-key"},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )

    document = json.loads(stdout.getvalue())
    assert code == 1
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
    assert document["providers"][1]["execution_error"] == {"code": expected, "phase": "provider"}
    assert document["execution_error"] == {"code": "provider_failed", "phase": "provider"}


def test_v2_provider_config_error_bypasses_cache_and_preserves_usable_peer(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"codex": {"enabled": True}, "opencode_go": {"enabled": True}}),
        encoding="utf-8",
    )
    cache_calls, run_calls = [], []

    class Cache:
        def __init__(self, *args):
            cache_calls.append(args)

        def get_or_refresh(self, *args):
            raise AssertionError("cache must be bypassed for provider configuration errors")

    class Orchestrator:
        last_record = None

        def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
            run_calls.append(provider_errors)
            return DocumentView.ordered(
                ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
                ProviderView(
                    ProviderKey.OPENCODE_GO,
                    ProviderState.UNAVAILABLE,
                    outcome=ProviderOutcome.UNDETECTED,
                ),
            )

    monkeypatch.setattr(cli, "V2QuotaCache", Cache)
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", Orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2", "--config", str(path)),
        environment={"LIMITORA_OPENCODE_API_KEY": "key"},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )

    document = json.loads(stdout.getvalue())
    assert code == 0
    assert stderr.getvalue() == ""
    assert cache_calls == []
    assert run_calls == [frozenset({ProviderKey.CODEX})]
    assert document["execution_state"] == "partial"
    assert document["providers"][0]["execution_error"] == {"code": "provider_failed", "phase": "provider"}
    assert [provider["provider"] for provider in document["providers"]] == ["codex", "opencode_go"]


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
        coordinator=cast(RuntimeCoordinator, UnexpectedCoordinator()),
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
    opencode_config = {"enabled": True} if scenario == "deadline_exhausted" else {}
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": opencode_config}), encoding="utf-8")

    codex: _MatrixCodex | None = None
    if scenario == "guard_wait_timeout":
        orchestrator = V2ExecutionOrchestrator(guard_factory=cast(type[V2Guard], lambda: _MatrixGuard(error=scenario)))
        expected = project_v2_not_run_bytes(scenario)
        expected_stderr = "yasb-limitora: guard_wait_timeout\n"
    elif scenario == "guard_acquisition_failed":
        orchestrator = V2ExecutionOrchestrator(guard_factory=cast(type[V2Guard], lambda: _MatrixGuard(error=scenario)))
        expected = project_v2_failure_bytes(scenario)
        expected_stderr = "yasb-limitora: runtime_error\n"
    elif scenario == "deadline_exhausted":
        orchestrator = V2ExecutionOrchestrator(guard_factory=cast(type[V2Guard], _MatrixGuard))
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
            guard_factory=cast(type[V2Guard], lambda: _MatrixGuard(lease=_MatrixLease(close=False))),
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
    code = main(("--output-version", "2", "--config", str(path)), environment={"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "key"}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)

    assert code == 2
    assert stdout.getvalue() == expected
    assert stdout.getvalue().endswith(b"\n") and not stdout.getvalue().endswith(b"\n\n")
    assert stderr.getvalue() == expected_stderr
    if scenario == "cleanup_failed":
        assert codex is not None
        assert codex.runners == [(r"C:\\codex.exe", "app-server")]


def test_v2_cli_second_invocation_uses_published_cache_without_rerunning_producer(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}}), encoding="utf-8")
    from yasb_limitora import v2_cache

    monkeypatch.setattr(v2_cache, "_bounded_call", lambda function, args, context: function(*args))
    lock = threading.Lock()
    cache_results = []

    class Lease:
        def release(self):
            lock.release()
            return True

        def close(self):
            return True

    class Guard:
        def acquire_key(self, key, context):
            lock.acquire()
            return Lease()

    def cache_factory(config, environment, config_path):
        cache = V2QuotaCache(config, environment, config_path)
        object.__setattr__(cache, "_guard_factory", Guard)
        original = cache.get_or_refresh

        def get_or_refresh(context, producer):
            result = original(context, producer)
            cache_results.append(result)
            return result

        monkeypatch.setattr(cache, "get_or_refresh", get_or_refresh)
        return cache

    monkeypatch.setattr(cli, "V2QuotaCache", cache_factory)

    class RunLease:
        def release(self):
            return True

        def close(self):
            return True

    class RunGuard(Guard):
        def acquire(self, path, context):
            return RunLease()

    codex = _MatrixCodex()
    orchestrator = V2ExecutionOrchestrator(
        guard_factory=cast(type[V2Guard], RunGuard),
        codex_executor=codex,
    )
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    environment = {"LOCALAPPDATA": str(tmp_path)}
    outputs = []
    for _ in range(2):
        stdout, stderr = io.BytesIO(), io.StringIO()
        assert main(
            ("--output-version", "2", "--config", str(path)),
            environment=environment,
            stdout=stdout,
            stderr=stderr,
            platform_is_windows=lambda: True,
        ) == 0
        assert stderr.getvalue() == ""
        outputs.append(stdout.getvalue())

    assert codex.runners == [(r"C:\\codex.exe", "app-server")]
    assert outputs[0] == outputs[1]
    assert cache_results[0].produced and cache_results[0].cached_public_bytes is not None
    assert not cache_results[1].produced and cache_results[1].cached_public_bytes == outputs[1]


def test_v2_cli_cache_producer_failure_fails_closed_without_direct_run(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}}), encoding="utf-8")
    attempts, direct_runs = [], []

    class FailingOrchestrator:
        last_record = None

        def run_refresh_attempt(self, config, environment, context, config_path):
            attempts.append(True)
            raise RuntimeError("provider failure")

        def run(self, config, environment, context, config_path):
            direct_runs.append(True)
            raise AssertionError("direct run bypassed single-flight")

    class Cache:
        def get_or_refresh(self, context, producer):
            return producer(context)

    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", FailingOrchestrator)
    monkeypatch.setattr(cli, "V2QuotaCache", lambda config, environment, config_path: Cache())
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2", "--config", str(path)),
        environment={"LOCALAPPDATA": str(tmp_path)},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )

    assert code == 2
    assert stdout.getvalue() == project_v2_failure_bytes("internal_error")
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
    assert len(attempts) == 1
    assert direct_runs == []


def test_v2_cli_cache_constructor_failure_runs_orchestrator(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    config = {"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}}
    path.write_text(json.dumps(config), encoding="utf-8")
    direct_runs = []
    expected_document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason="disabled"),
    )

    class Orchestrator:
        last_record = None

        def run(self, config, environment, context, config_path):
            direct_runs.append(True)
            return expected_document

    def fail_cache(config, environment, config_path):
        raise OSError("private cache setup failure")

    monkeypatch.setattr(cli, "read_v2_config", lambda path, context: json.dumps(config).encode())
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", Orchestrator)
    monkeypatch.setattr(cli, "V2QuotaCache", fail_cache)
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2", "--config", str(path)),
        environment={"LOCALAPPDATA": str(tmp_path)},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )

    assert code == 0, stderr.getvalue()
    assert stdout.getvalue() == project_v2_bytes(V2ProjectionInput(expected_document, frozenset({ProviderKey.CODEX})))
    assert stderr.getvalue() == ""
    assert direct_runs == [True]


def test_v2_cli_cache_guard_timeout_preserves_diagnostic_without_running_producer(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    config = {"codex": {"enabled": True, "runner": r"C:\\codex.exe"}, "opencode_go": {}}
    path.write_text(json.dumps(config), encoding="utf-8")
    producer_calls = []

    class Orchestrator:
        last_record = None
        def run_refresh_attempt(self, *args):
            producer_calls.append(True)
        def run(self, *args):
            pytest.fail("direct run bypassed cache coordination")

    class Cache:
        def get_or_refresh(self, context, producer):
            return SingleFlightResult(coordination_failed=True, coordination_error="guard_wait_timeout")

    monkeypatch.setattr(cli, "read_v2_config", lambda path, context: json.dumps(config).encode())
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", Orchestrator)
    monkeypatch.setattr(cli, "V2QuotaCache", lambda *args: Cache())
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(("--output-version", "2", "--config", str(path)), environment={"LOCALAPPDATA": str(tmp_path)}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)

    assert code == 2
    assert stdout.getvalue() == project_v2_not_run_bytes("guard_wait_timeout")
    assert stderr.getvalue() == "yasb-limitora: guard_wait_timeout\n"
    assert producer_calls == []
