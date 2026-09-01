import io
import json
import ntpath
from contextlib import nullcontext
from unittest.mock import patch

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

from yasb_limitora import cli
from yasb_limitora.cli import main
from yasb_limitora.model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
)
from yasb_limitora.path import DeadlineError


def _run(argv, *, orchestrator=None, environment=None):
    stdout, stderr = io.BytesIO(), io.StringIO()
    seam = patch.object(cli, "ExecutionOrchestrator", lambda: orchestrator) if orchestrator is not None else nullcontext()
    with seam:
        code = main(
            argv,
            environment=environment or {},
            stdout=stdout,
            stderr=stderr,
            platform_is_windows=lambda: True,
        )
    return code, json.loads(stdout.getvalue()), stderr.getvalue(), stdout.getvalue()


def _disabled_document():
    return DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )


def test_windows_freeze_support_claims_terminal_child_before_cli_dispatch(monkeypatch):
    events = []

    class FreezeSupportClaimed(Exception):
        pass

    def terminal_freeze_support():
        events.append("freeze_support")
        raise FreezeSupportClaimed

    def unexpected(stage):
        events.append(stage)
        raise AssertionError(f"{stage} ran after terminal freeze_support")

    monkeypatch.setattr(cli.multiprocessing, "freeze_support", terminal_freeze_support)
    monkeypatch.setattr(cli, "_resolve_config_path", lambda argv, environment: unexpected("config_resolution"))
    monkeypatch.setattr(cli, "ExecutionOrchestrator", lambda: unexpected("orchestrator"))

    with pytest.raises(FreezeSupportClaimed):
        main(
            ("--output-version", "2"),
            stdout=io.BytesIO(),
            stderr=io.StringIO(),
            platform_is_windows=lambda: True,
        )

    assert events == ["freeze_support"]


def test_non_windows_platform_gate_precedes_freeze_support(monkeypatch):
    events = []

    def unexpected_freeze_support():
        events.append("freeze_support")
        raise AssertionError("freeze_support ran on an unsupported platform")

    monkeypatch.setattr(cli.multiprocessing, "freeze_support", unexpected_freeze_support)
    stdout, stderr = io.BytesIO(), io.StringIO()

    code = main(
        ("--output-version", "2"),
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: False,
    )

    assert code == 2
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == "yasb-limitora: unsupported_platform\n"
    assert events == []


def _disabled_config_path(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {}, "opencode_go": {}}), encoding="utf-8")
    return path


class _Orchestrator:
    last_record = None

    def __init__(self, document):
        self.document = document
        self.calls = []

    def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
        self.calls.append((config, environment, context, config_path, provider_errors))
        return self.document


@pytest.mark.parametrize(
    "argv",
    (
        ("--output-version", "1"),
        ("--output-version=1",),
        ("--output-version", "2"),
        ("--output-version=2",),
        ("--output-version",),
        ("--output-version=",),
        ("--output-version", "2", "--output-version=1"),
        ("--output-version", "2", "--config", "config.json"),
        ("--output-version=2", "positional"),
    ),
)
def test_removed_output_selector_is_invalid_before_config_or_runtime(monkeypatch, argv):
    def unexpected_read(path, context):
        raise AssertionError(f"removed selector read configuration: {path}")

    def unexpected_bounded_read(path, context):
        raise AssertionError(f"removed selector read bounded configuration: {path}")

    monkeypatch.setattr(cli, "read_config", unexpected_read, raising=False)
    monkeypatch.setattr(cli, "read_config", unexpected_bounded_read)
    orchestrator = _Orchestrator(_disabled_document())
    code, document, stderr, raw = _run(argv, orchestrator=orchestrator)

    assert code == 2
    assert "version" not in document
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert orchestrator.calls == []
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")


@pytest.mark.parametrize("argv", (("--unknown",), ("positional",)))
def test_selector_free_invocation_rejection_uses_current_contract(monkeypatch, argv):
    events = []

    def controlled_resolve(load_args, environment):
        events.append(("resolve", tuple(load_args), environment))
        raise cli.InvocationError

    monkeypatch.setattr(cli, "_resolve_config_path", controlled_resolve)
    orchestrator = _Orchestrator(_disabled_document())
    code, document, stderr, _ = _run(argv, orchestrator=orchestrator)

    assert code == 2
    assert "version" not in document
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert events == [("resolve", argv, {})]
    assert orchestrator.calls == []


def test_selector_free_configuration_failure_is_sanitized(tmp_path):
    missing = tmp_path / "missing.json"
    orchestrator = _Orchestrator(_disabled_document())
    code, document, stderr, _ = _run(("--config", str(missing)), orchestrator=orchestrator)
    assert code == 2
    assert "version" not in document
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert orchestrator.calls == []


def test_selector_free_runtime_failure_is_sanitized(tmp_path):
    class FailingOrchestrator:
        last_record = None

        def run(self, config, environment, context, config_path, *, provider_errors=frozenset()):
            raise RuntimeError("private runtime detail")

    path = _disabled_config_path(tmp_path)
    code, document, stderr, raw = _run(("--config", str(path)), orchestrator=FailingOrchestrator())
    assert code == 2
    assert "version" not in document
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private runtime detail" not in raw + stderr.encode()


def test_selector_free_projection_failure_is_sanitized(monkeypatch, tmp_path):
    def fail_projection(input):
        raise ValueError("private projection detail")

    monkeypatch.setattr(cli, "project_bytes", fail_projection)
    path = _disabled_config_path(tmp_path)
    code, document, stderr, raw = _run(("--config", str(path)), orchestrator=_Orchestrator(_disabled_document()))
    assert code == 2
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private projection detail" not in raw


def test_selector_free_preserves_provider_error_exit_and_streams(tmp_path):
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT)),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )
    path = _disabled_config_path(tmp_path)
    code, projected, stderr, _ = _run(("--config", str(path)), orchestrator=_Orchestrator(document))
    assert code == 1 and stderr == "yasb-limitora: runtime_error\n"
    assert projected["providers"][0]["execution_error"] == {"code": "provider_timeout", "phase": "provider"}


def test_duplicate_config_flags_fail_safely(tmp_path):
    path = str(tmp_path / "config.json")
    code, document, stderr, _ = _run(("--config", path, "-c", path))

    assert code == 2 and "version" not in document
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"


@pytest.mark.parametrize("form", ("long", "short", "equals"))
def test_selector_free_invocation_preserves_existing_config_forms(tmp_path, form):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}}), encoding="utf-8")
    config_args = {"long": ("--config", str(path)), "short": ("-c", str(path)), "equals": (f"--config={path}",)}[form]
    orchestrator = _Orchestrator(_disabled_document())
    code, document, stderr, _ = _run(config_args, orchestrator=orchestrator)
    assert code == 0 and stderr == "" and "version" not in document
    assert orchestrator.calls[0][0].codex.enabled is True


def test_current_explicit_config_wins_over_environment_and_default(monkeypatch):
    paths = []

    def read_config(path, context):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "read_config", read_config, raising=False)
    explicit = r"C:\explicit.json"
    environment = {
        "YASB_LIMITORA_CONFIG": r"C:\environment.json",
        "LOCALAPPDATA": r"C:\Users\user\AppData\Local",
    }
    code, document, stderr, _ = _run(("--config", explicit), environment=environment)

    assert code == 0 and "version" not in document and stderr == ""
    assert paths == [explicit]


def test_current_environment_config_wins_over_default(monkeypatch):
    paths = []

    def read_config(path, context):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "read_config", read_config, raising=False)
    environment_path = r"C:\environment.json"
    code, document, stderr, _ = _run(
        (),
        environment={"YASB_LIMITORA_CONFIG": environment_path, "LOCALAPPDATA": r"C:\Users\user\AppData\Local"},
    )

    assert code == 0 and "version" not in document and stderr == ""
    assert paths == [environment_path]


def test_current_default_uses_injected_localappdata(monkeypatch):
    paths = []

    def read_config(path, context):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "read_config", read_config, raising=False)
    localappdata = r"C:\Users\user\AppData\Local"
    code, document, stderr, _ = _run((), environment={"LOCALAPPDATA": localappdata})

    assert code == 0 and "version" not in document and stderr == ""
    assert paths == [ntpath.join(localappdata, "yasb-limitora", "config.json")]


def test_current_empty_environment_config_is_configuration_invalid(monkeypatch):
    def unexpected_read(path, context):
        raise AssertionError("empty environment config fell back")

    monkeypatch.setattr(cli, "read_config", unexpected_read, raising=False)
    value = "  C:\\private\\env.json  "
    code, document, stderr, raw = _run(
        (),
        environment={"YASB_LIMITORA_CONFIG": " \t", "LOCALAPPDATA": value},
    )

    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert value not in raw.decode() + stderr


@pytest.mark.parametrize("localappdata", (None, "", " \t"))
def test_current_missing_or_blank_localappdata_is_configuration_invalid(localappdata):
    environment = {} if localappdata is None else {"LOCALAPPDATA": localappdata}
    code, document, stderr, raw = _run((), environment=environment)

    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert b"LOCALAPPDATA" not in raw + stderr.encode()


def test_current_selected_inaccessible_file_does_not_fall_back(monkeypatch):
    selected = r"C:\private\selected.json"
    fallback = r"C:\Users\user\AppData\Local"

    def read_config(path, context):
        raise PermissionError(selected)

    monkeypatch.setattr(cli, "read_config", read_config, raising=False)
    code, document, stderr, raw = _run(
        ("--config", selected),
        environment={"YASB_LIMITORA_CONFIG": r"C:\fallback.json", "LOCALAPPDATA": fallback},
    )
    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert selected not in raw.decode() + stderr


def test_current_config_deadline_expiry_emits_bounded_deadline_document(monkeypatch, tmp_path):
    def expired_config(path, context):
        raise DeadlineError("configuration deadline exhausted")

    monkeypatch.setattr(cli, "read_config", expired_config)
    path = tmp_path / "config.json"

    code, document, stderr, raw = _run(("--config", str(path)))

    assert code == 2
    assert document["execution_state"] == "execution_error"
    assert document["execution_error"] == {"code": "deadline_exhausted", "phase": "document"}
    assert all(provider["not_run_reason"] == "deadline_exhausted" for provider in document["providers"])
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"configuration deadline exhausted" not in raw


@pytest.mark.parametrize("value", (0, 121, True, "7", None, float("inf")))
def test_current_deadline_seconds_rejects_invalid_values(tmp_path, value):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"deadline_seconds": value}), encoding="utf-8")
    code, document, stderr, _ = _run(("--config", str(path)))
    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"


def test_current_deadline_defaults_to_seven_seconds(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {}, "opencode_go": {}}), encoding="utf-8")
    orchestrator = _Orchestrator(_disabled_document())
    code, _, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)
    assert code == 0 and stderr == ""
    assert orchestrator.calls[0][0].deadline_seconds == 7.0


@pytest.mark.parametrize("timeout", ("7", True, float("nan"), float("inf")))
def test_current_opencode_timeout_type_errors_are_configuration_invalid(tmp_path, timeout):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"opencode_go": {"timeout_seconds": timeout}}), encoding="utf-8")
    orchestrator = _Orchestrator(_disabled_document())

    code, document, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)

    if timeout in ("7", True):
        assert code == 1
        assert document["execution_error"] == {"code": "provider_failed", "phase": "provider"}
        assert stderr == "yasb-limitora: runtime_error\n"
        assert len(orchestrator.calls) == 1
    else:
        assert code == 2
        assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
        assert stderr == "yasb-limitora: configuration_invalid\n"
        assert orchestrator.calls == []


@pytest.mark.parametrize("timeout", (1, 7, 7.5, 10))
def test_current_opencode_numeric_timeout_is_accepted(tmp_path, timeout):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"opencode_go": {"timeout_seconds": timeout}}), encoding="utf-8")
    orchestrator = _Orchestrator(_disabled_document())

    code, document, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)

    assert code == 0 and stderr == "" and "version" not in document
    assert orchestrator.calls[0][0].opencode_go.timeout_seconds == float(timeout)


@pytest.mark.parametrize("legacy", ({"workspace_id": "legacy"}, {"cookie": "legacy"}))
def test_current_opencode_legacy_auth_fields_are_configuration_invalid(tmp_path, legacy):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"opencode_go": legacy}), encoding="utf-8")
    orchestrator = _Orchestrator(_disabled_document())

    code, document, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)

    if "workspace_id" in legacy:
        assert code == 1
        assert document["execution_error"] == {"code": "provider_failed", "phase": "provider"}
        assert stderr == "yasb-limitora: runtime_error\n"
        assert len(orchestrator.calls) == 1
    else:
        assert code == 2
        assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
        assert stderr == "yasb-limitora: configuration_invalid\n"
        assert orchestrator.calls == []


@pytest.mark.parametrize(
    "raw",
    (
        '{"deadline_seconds": 7, "deadline_seconds": 8}',
        '{"unknown": {}, "codex": {}, "opencode_go": {}}',
        '{"codex": {}, "opencode_go": {}} trailing',
    ),
)
def test_current_grammar_rejects_duplicate_unknown_and_trailing_data(tmp_path, raw):
    path = tmp_path / "config.json"
    path.write_text(raw, encoding="utf-8")
    code, document, stderr, _ = _run(("--config", str(path)))
    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"


def test_selector_free_loader_uses_current_grammar(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"deadline_seconds": 7}), encoding="utf-8")
    orchestrator = _Orchestrator(_disabled_document())
    code, document, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)
    assert code == 0
    assert "version" not in document
    assert all(provider["outcome"] == "not_run" for provider in document["providers"])
    assert stderr == ""

@pytest.mark.parametrize(
    ("peer_outcome", "expected_code", "expected_state"),
    (
        (ProviderOutcome.UNDETECTED, 0, "partial"),
        (ProviderOutcome.NOT_RUN, 1, "execution_error"),
    ),
)
def test_current_provider_configuration_error_is_scoped_to_the_invalid_provider(
    tmp_path, peer_outcome, expected_code, expected_state
):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"codex": {"enabled": True}, "opencode_go": {}}),
        encoding="utf-8",
    )
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, outcome=peer_outcome, not_run_reason="disabled" if peer_outcome is ProviderOutcome.NOT_RUN else None),
    )
    orchestrator = _Orchestrator(document)

    code, projected, stderr, _ = _run(("--config", str(path)), orchestrator=orchestrator)

    assert code == expected_code
    assert stderr == ("" if expected_code == 0 else "yasb-limitora: runtime_error\n")
    assert len(orchestrator.calls) == 1
    assert projected["execution_state"] == expected_state
    assert [provider["provider"] for provider in projected["providers"]] == ["codex", "opencode_go"]
    assert projected["providers"][0]["execution_error"] == {"code": "provider_failed", "phase": "provider"}
    assert projected["providers"][1]["outcome"] == peer_outcome.value
