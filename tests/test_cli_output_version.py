import io
import json
import ntpath

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


def _disabled_config_path(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {}, "opencode_go": {}}), encoding="utf-8")
    return path


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


@pytest.mark.parametrize("selector", (("--output-version", "2"), ("--output-version=2",)))
def test_exact_v2_selectors_route_the_v2_projection(tmp_path, selector):
    path = _disabled_config_path(tmp_path)
    code, document, stderr, _ = _run((*selector, "--config", str(path)), coordinator=_Coordinator(_disabled_document()))
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

    def controlled_resolve(load_args, environment):
        events.append(("resolve", tuple(load_args), environment))
        raise cli.InvocationError

    monkeypatch.setattr(cli, "_resolve_config_path", controlled_resolve)
    coordinator = _Coordinator(_disabled_document())
    code, document, stderr, _ = _run(argv, coordinator=coordinator)
    assert code == 2
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: invocation_invalid\n"
    assert events == [("resolve", tuple(arg for arg in argv if arg not in {"--output-version", "2", "--output-version=2"}), {})]
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


def test_trusted_v2_routes_runtime_failure_to_v2(tmp_path):
    class FailingCoordinator:
        def run(self, config, environment):
            raise RuntimeError("private runtime detail")

    path = _disabled_config_path(tmp_path)
    code, document, stderr, raw = _run(("--output-version", "2", "--config", str(path)), coordinator=FailingCoordinator())
    assert code == 1
    assert document["version"] == 2
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private runtime detail" not in raw + stderr.encode()


def test_trusted_v2_routes_projection_failure_to_v2(monkeypatch, tmp_path):
    def fail_projection(input):
        raise ValueError("private projection detail")

    monkeypatch.setattr(cli, "project_v2_bytes", fail_projection)
    path = _disabled_config_path(tmp_path)
    code, document, stderr, raw = _run(("--output-version", "2", "--config", str(path)), coordinator=_Coordinator(_disabled_document()))
    assert code == 1
    assert document["execution_error"] == {"code": "internal_error", "phase": "document"}
    assert stderr == "yasb-limitora: runtime_error\n"
    assert b"private projection detail" not in raw


def test_trusted_v2_preserves_provider_error_exit_and_streams(tmp_path):
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT)),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
    )
    path = _disabled_config_path(tmp_path)
    code, projected, stderr, _ = _run(("--output-version=2", "--config", str(path)), coordinator=_Coordinator(document))
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


def test_v2_explicit_config_wins_over_environment_and_default(monkeypatch):
    paths = []

    def read_config(path):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "_read_config", read_config, raising=False)
    explicit = r"C:\explicit.json"
    environment = {
        "YASB_LIMITORA_CONFIG": r"C:\environment.json",
        "LOCALAPPDATA": r"C:\Users\user\AppData\Local",
    }
    code, document, stderr, _ = _run(("--output-version", "2", "--config", explicit), environment=environment)

    assert code == 0 and document["version"] == 2 and stderr == ""
    assert paths == [explicit]


def test_v2_environment_config_wins_over_default(monkeypatch):
    paths = []

    def read_config(path):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "_read_config", read_config, raising=False)
    environment_path = r"C:\environment.json"
    code, document, stderr, _ = _run(
        ("--output-version", "2"),
        environment={"YASB_LIMITORA_CONFIG": environment_path, "LOCALAPPDATA": r"C:\Users\user\AppData\Local"},
    )

    assert code == 0 and document["version"] == 2 and stderr == ""
    assert paths == [environment_path]


def test_v2_default_uses_injected_localappdata(monkeypatch):
    paths = []

    def read_config(path):
        paths.append(path)
        return json.dumps({"codex": {}, "opencode_go": {}})

    monkeypatch.setattr(cli, "_read_config", read_config, raising=False)
    localappdata = r"C:\Users\user\AppData\Local"
    code, document, stderr, _ = _run(("--output-version", "2"), environment={"LOCALAPPDATA": localappdata})

    assert code == 0 and document["version"] == 2 and stderr == ""
    assert paths == [ntpath.join(localappdata, "yasb-limitora", "config.json")]


def test_v2_empty_environment_config_is_configuration_invalid(monkeypatch):
    def unexpected_read(path):
        raise AssertionError("empty environment config fell back")

    monkeypatch.setattr(cli, "_read_config", unexpected_read, raising=False)
    value = "  C:\\private\\env.json  "
    code, document, stderr, raw = _run(
        ("--output-version", "2"),
        environment={"YASB_LIMITORA_CONFIG": " \t", "LOCALAPPDATA": value},
    )

    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert value not in raw.decode() + stderr


@pytest.mark.parametrize("localappdata", (None, "", " \t"))
def test_v2_missing_or_blank_localappdata_is_configuration_invalid(localappdata):
    environment = {} if localappdata is None else {"LOCALAPPDATA": localappdata}
    code, document, stderr, raw = _run(("--output-version", "2"), environment=environment)

    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert b"LOCALAPPDATA" not in raw + stderr.encode()


def test_v2_selected_inaccessible_file_does_not_fall_back(monkeypatch):
    selected = r"C:\private\selected.json"
    fallback = r"C:\Users\user\AppData\Local"

    def read_config(path):
        raise PermissionError(selected)

    monkeypatch.setattr(cli, "_read_config", read_config, raising=False)
    code, document, stderr, raw = _run(
        ("--output-version", "2", "--config", selected),
        environment={"YASB_LIMITORA_CONFIG": r"C:\fallback.json", "LOCALAPPDATA": fallback},
    )

    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"
    assert selected not in raw.decode() + stderr


@pytest.mark.parametrize("value", (0, 121, True, "7", None, float("inf")))
def test_v2_deadline_seconds_rejects_invalid_values(tmp_path, value):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"deadline_seconds": value}), encoding="utf-8")
    code, document, stderr, _ = _run(("--output-version", "2", "--config", str(path)))
    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"


def test_v2_deadline_defaults_to_seven_seconds(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"codex": {}, "opencode_go": {}}), encoding="utf-8")
    coordinator = _Coordinator(_disabled_document())
    code, _, stderr, _ = _run(("--output-version", "2", "--config", str(path)), coordinator=coordinator)
    assert code == 0 and stderr == ""
    assert coordinator.calls[0][0].deadline_seconds == 7.0


@pytest.mark.parametrize(
    "raw",
    (
        '{"deadline_seconds": 7, "deadline_seconds": 8}',
        '{"unknown": {}, "codex": {}, "opencode_go": {}}',
        '{"codex": {}, "opencode_go": {}} trailing',
    ),
)
def test_v2_grammar_rejects_duplicate_unknown_and_trailing_data(tmp_path, raw):
    path = tmp_path / "config.json"
    path.write_text(raw, encoding="utf-8")
    code, document, stderr, _ = _run(("--output-version", "2", "--config", str(path)))
    assert code == 2
    assert document["execution_error"] == {"code": "configuration_invalid", "phase": "configuration"}
    assert stderr == "yasb-limitora: configuration_invalid\n"


def test_v1_loader_keeps_deadline_seconds_out_of_its_grammar(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"deadline_seconds": 7}), encoding="utf-8")
    code, document, stderr, _ = _run(("--config", str(path)))
    assert code == 2
    assert document["version"] == 1
    assert stderr == "yasb-limitora: configuration_invalid\n"
