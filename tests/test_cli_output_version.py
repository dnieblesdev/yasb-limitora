import io
import json

import pytest

import yasb_limitora.cli as cli
from yasb_limitora.cli import main
from yasb_limitora.model import DocumentView, ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode


def _run(argv, *, coordinator=None, environment=None):
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(argv, coordinator=coordinator, environment=environment or {}, stdout=stdout, stderr=stderr)
    return code, json.loads(stdout.getvalue()), stderr.getvalue(), stdout.getvalue()


def _disabled_document():
    return DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )


class _Coordinator:
    def __init__(self, document):
        self.document = document
        self.calls = []

    def run(self, config, environment):
        self.calls.append((config, environment))
        return self.document


@pytest.mark.parametrize("argv", (("--output-version", "1"), ("--output-version=1",)))
def test_explicit_v1_routes_the_frozen_projection(argv):
    code, document, stderr, raw = _run(argv, coordinator=_Coordinator(_disabled_document()))
    assert code == 0
    assert document == {"version": 1, "providers": [
        {"provider": "codex", "state": "unavailable"},
        {"provider": "opencode_go", "state": "unavailable"},
    ]}
    assert stderr == ""
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")


@pytest.mark.parametrize("argv", (("--output-version", "2"), ("--output-version=2",)))
def test_exact_v2_selectors_route_the_v2_projection(argv):
    code, document, stderr, _ = _run(argv, coordinator=_Coordinator(_disabled_document()))
    assert code == 0 and stderr == ""
    assert document["version"] == 2
    assert all(provider["outcome"] == "not_run" for provider in document["providers"])


@pytest.mark.parametrize(
    "argv",
    (
        ("--output-version",),
        ("--output-version=",),
        ("--output-version", "0"),
        ("--output-version=3",),
        ("--output-version", "integer"),
        ("--output-version", "2", "--output-version=1"),
        ("--output-version", "token"),
    ),
)
def test_untrusted_selectors_reject_before_config_or_coordinator(monkeypatch, argv):
    def unexpected_load(_):
        raise AssertionError("untrusted selector loaded configuration")

    monkeypatch.setattr(cli, "_load", unexpected_load)
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, raw = _run(argv, coordinator=coordinator)
    assert code == 2
    assert document["version"] == 1
    assert document["providers"][0]["error"]["code"] == "invocation_invalid"
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert b"token" not in raw
    assert coordinator.calls == []


@pytest.mark.parametrize("argv", (("--unknown",), ("positional",)))
def test_later_v1_invocation_rejection_loads_then_skips_coordinator(monkeypatch, argv):
    events = []

    def controlled_load(load_args):
        events.append(("load", tuple(load_args)))
        raise cli.InvocationError

    monkeypatch.setattr(cli, "_load", controlled_load)
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, _ = _run(argv, coordinator=coordinator)

    assert code == 2
    assert document["version"] == 1
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert events == [("load", argv)]
    assert coordinator.calls == []


@pytest.mark.parametrize("argv", (("--output-version", "2", "--unknown"), ("--output-version=2", "positional")))
def test_trusted_v2_loads_before_later_rejection_without_coordinator(monkeypatch, argv):
    events = []

    def controlled_load(load_args):
        events.append(("load", tuple(load_args)))
        raise cli.InvocationError

    monkeypatch.setattr(cli, "_load", controlled_load)
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, _ = _run(argv, coordinator=coordinator)
    assert code == 2
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert events == [("load", tuple(arg for arg in argv if arg not in {"--output-version", "2", "--output-version=2"}))]
    assert coordinator.calls == []


def test_trusted_v2_owns_secret_like_later_invocation_failure():
    code, document, stderr, _ = _run(("--output-version", "2", "--config", "token"))
    assert code == 2
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"


def test_trusted_v2_routes_configuration_failure_to_v2(tmp_path):
    missing = tmp_path / "missing.json"
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, _ = _run(
        ("--output-version", "2", "--config", str(missing)), coordinator=coordinator
    )
    assert code == 2
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert coordinator.calls == []


def test_trusted_v2_routes_runtime_failure_to_v2():
    class FailingCoordinator:
        def run(self, config, environment):
            raise RuntimeError("private runtime detail")

    code, document, stderr, raw = _run(("--output-version", "2"), coordinator=FailingCoordinator())
    assert code == 1
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private runtime detail" not in raw + stderr.encode()


def test_trusted_v2_routes_projection_failure_to_v2(monkeypatch):
    def fail_projection(input):
        raise ValueError("private projection detail")

    monkeypatch.setattr(cli, "project_v2_bytes", fail_projection)
    code, document, stderr, raw = _run(("--output-version", "2"), coordinator=_Coordinator(_disabled_document()))
    assert code == 1
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private projection detail" not in raw


def test_trusted_v2_preserves_provider_error_exit_and_streams():
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT)),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )
    code, projected, stderr, _ = _run(("--output-version=2",), coordinator=_Coordinator(document))
    assert code == 1 and stderr == "yasb-limitora: runtime_error\n"
    assert projected["providers"][0]["execution_error"] == {"code": "provider_timeout", "phase": "provider"}


def test_duplicate_config_flags_fail_safely(tmp_path):
    path = str(tmp_path / "config.json")
    for selector in ((), ("--output-version", "1"), ("--output-version", "2")):
        code, document, stderr, _ = _run((*selector, "--config", path, "-c", path))
        assert code == 2 and document["version"] == (2 if selector == ("--output-version", "2") else 1)
        assert stderr == "yasb-limitora: invocation_invalid\n"


@pytest.mark.parametrize("form", ("long", "short", "equals"))
def test_output_selector_preserves_existing_config_forms(tmp_path, form):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {"enabled": True, "runner": r"C:\\codex.exe"}}), encoding="utf-8")
    config_args = {"long": ("--config", str(path)), "short": ("-c", str(path)), "equals": (f"--config={path}",)}[form]
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, _ = _run(("--output-version", "2", *config_args), coordinator=coordinator)
    assert code == 0 and stderr == "" and document["version"] == 2
    assert coordinator.calls[0][0].codex.enabled is True
