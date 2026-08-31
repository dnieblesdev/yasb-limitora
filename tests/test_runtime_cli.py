import io
import json
import ntpath
import threading
import time
from typing import cast

import pytest

from yasb_limitora import cli
from yasb_limitora.cli import main
from yasb_limitora.config import LocalConfig
from yasb_limitora.limitora_api import (
    OpenCodeFailureEvidence,
    OpenCodeReadResult,
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


def enabled_config(codex=True, opencode=True, timeout=0.2):
    return LocalConfig.from_mapping({
        "codex": {"enabled": codex, "runner": r"C:\codex.exe", "timeout_seconds": timeout},
        "opencode_go": {"enabled": opencode, "timeout_seconds": timeout},
    })


class _FakeOrchestrator:
    last_record = None

    def __init__(self, document):
        self.document = document
        self.calls = []

    def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
        self.calls.append((config, environment, context, config_path, provider_errors))
        return self.document



@pytest.mark.parametrize("bad", [("--token", "secret"), ("--bad", "value"), ("--config",)])
def test_invalid_arguments_are_safe_and_exit_two(bad):
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(bad, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 2
    assert json.loads(stdout.getvalue())["execution_error"]["code"] == "invocation_invalid"
    assert "secret" not in stdout.getvalue().decode() + stderr.getvalue()


def test_missing_cookie_is_unavailable_and_streams_are_isolated(monkeypatch):
    monkeypatch.setattr(cli, "read_v2_config", lambda path, context: json.dumps({"codex": {}, "opencode_go": {}}))
    orchestrator = _FakeOrchestrator(
        DocumentView.ordered(
            ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.UNDETECTED),
            ProviderView(
                ProviderKey.OPENCODE_GO,
                ProviderState.UNAVAILABLE,
                outcome=ProviderOutcome.NOT_RUN,
                not_run_reason="disabled",
            ),
        )
    )
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(
        (),
        environment={"LOCALAPPDATA": r"C:\Users\runtime-test\AppData\Local"}, stdout=stdout, stderr=stderr,
        platform_is_windows=lambda: True,
    )
    document = json.loads(stdout.getvalue())
    assert code == 0 and stderr.getvalue() == ""
    assert document["providers"][1]["provider"] == "opencode_go"
    assert document["providers"][1]["outcome"] == "not_run"
    assert document["providers"][1]["not_run_reason"] == "disabled"


def test_runtime_safe_error_has_exit_one_and_sanitized_diagnostic(monkeypatch):
    monkeypatch.setattr(cli, "read_v2_config", lambda path, context: json.dumps({"codex": {}, "opencode_go": {}}))
    stdout, stderr = io.BytesIO(), io.StringIO()
    class FailingOrchestrator:
        last_record = None

        def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
            return DocumentView.ordered(
                view(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeErrorCode.TIMEOUT),
                view(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
            )

    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", FailingOrchestrator)
    assert main(
        (),
        environment={
            "LOCALAPPDATA": r"C:\Users\runtime-test\AppData\Local",
            "LIMITORA_OPENCODE_API_KEY": "key",
        },
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    ) == 1

    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"
    assert "cookie" not in stdout.getvalue().decode() + stderr.getvalue()


def test_config_file_and_runtime_error_are_redacted(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": "relative"}}), encoding="utf-8")
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(("--config", str(path)), stdout=stdout, stderr=stderr, platform_is_windows=lambda: True) == 1
    assert "relative" not in stdout.getvalue().decode() + stderr.getvalue()
    assert stderr.getvalue() == "yasb-limitora: runtime_error\n"


def test_v2_default_resolution_reads_injected_localappdata(monkeypatch):
    paths = []
    localappdata = r"C:\Users\runtime-test\AppData\Local"

    def read_config(path, context):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "read_v2_config", read_config)
    orchestrator = _FakeOrchestrator(
        DocumentView.ordered(
            view(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
            ProviderView(
                ProviderKey.OPENCODE_GO,
                ProviderState.UNAVAILABLE,
                outcome=ProviderOutcome.NOT_RUN,
                not_run_reason="disabled",
            ),
        )
    )
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", lambda: orchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main(
        (),
        environment={"LOCALAPPDATA": localappdata},
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
        ("--config", str(path)),
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
        ("--config", str(path)),
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
        ("--config", str(path)),
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

    def read_config(path, context):
        raise OSError("private config detail")

    class UnexpectedOrchestrator:
        def __init__(self):
            starts.append(True)

        def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
            raise AssertionError("provider execution started after configuration failure")

    monkeypatch.setattr(cli, "read_v2_config", read_config)
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", UnexpectedOrchestrator)
    stdout, stderr = io.BytesIO(), io.StringIO()
    assert main(
        (),
        environment={"LOCALAPPDATA": r"C:\Users\runtime-test\AppData\Local"},
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
    code = main(("--config", str(path)), environment={"LOCALAPPDATA": str(tmp_path), "LIMITORA_OPENCODE_API_KEY": "key"}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)

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
            ("--config", str(path)),
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
        ("--config", str(path)),
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
        ("--config", str(path)),
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
    code = main(("--config", str(path)), environment={"LOCALAPPDATA": str(tmp_path)}, stdout=stdout, stderr=stderr, platform_is_windows=lambda: True)

    assert code == 2
    assert stdout.getvalue() == project_v2_not_run_bytes("guard_wait_timeout")
    assert stderr.getvalue() == "yasb-limitora: guard_wait_timeout\n"
    assert producer_calls == []
