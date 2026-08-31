import importlib.util
import inspect
import json
import math
from pathlib import Path
from typing import Any, cast

import pytest

import yasb_limitora as package
from yasb_limitora import (
    ConfigError,
    DocumentView,
    LocalConfig,
    OpenCodeGoConfig,
    ProviderKey,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
    cli,
)
from yasb_limitora.config import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_CODEX_TIMEOUT_SECONDS,
    CodexConfig,
)
from yasb_limitora.model import ProviderOutcome
from yasb_limitora.projection import ProjectionInput, project_bytes


def test_v1_golden_artifacts_are_absent() -> None:
    root = Path(__file__).parents[1]

    assert not (root / "tests/test_v1_golden_fixtures.py").exists()
    assert not tuple((root / "tests/fixtures").glob("json_v1_*.json"))


def test_legacy_runtime_modules_and_exports_are_absent() -> None:
    root = Path(__file__).parents[1]
    legacy_modules = ("coord" + "inator", "projection_v2")
    for module_name in legacy_modules:
        assert not (root / "src/yasb_limitora" / f"{module_name}.py").exists()
        assert importlib.util.find_spec(f"yasb_limitora.{module_name}") is None

    legacy_symbols = (
        "Provider" + "Coordinator",
        "Runtime" + "Coordinator",
        "co" + "ordinate",
    )
    assert all(not hasattr(package, name) for name in legacy_symbols)

    current_projection = importlib.import_module("yasb_limitora.projection")
    assert hasattr(current_projection, "ProjectionInput")
    assert hasattr(current_projection, "project_document")
    assert hasattr(current_projection, "project_bytes")
    assert not hasattr(current_projection, "V2ProjectionInput")
    assert not hasattr(current_projection, "project_v2_document")
    assert not hasattr(current_projection, "project_v2_bytes")


def test_safe_error_codes_have_one_current_enum() -> None:
    model = importlib.import_module("yasb_limitora.model")
    removed_enum_name = "V2" + "SafeErrorCode"

    assert not hasattr(model, removed_enum_name)
    assert tuple(code.value for code in SafeErrorCode) == (
        "timeout",
        "provider_error",
        "internal_error",
        "configuration_invalid",
        "invocation_invalid",
        "invalid_provider_data",
        "unknown_provider_state",
        "guard_acquisition_failed",
        "guard_wait_timeout",
        "deadline_exhausted",
        "cleanup_failed",
    )
    assert SafeError("cleanup_failed").code is SafeErrorCode.CLEANUP_FAILED


@pytest.mark.parametrize("name", ("_failure", "_LEGACY_READ_CONFIG", "_read_config", "_load_explicit", "_load_path", "_load"))
def test_removed_cli_helpers_are_absent(name: str) -> None:
    assert not hasattr(cli, name)


def test_cli_main_has_no_legacy_coordinator_injection() -> None:
    assert "coordinator" not in inspect.signature(cli.main).parameters
    assert not hasattr(cli, "RuntimeCoordinator")


def test_config_is_immutable_and_repr_redacts_private_values() -> None:
    config = LocalConfig.from_mapping({
        "codex": {"enabled": True, "runner": r"C:\Tools\codex.exe"},
        "opencode_go": {"enabled": True},
    })
    assert config.codex.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert "private-workspace" not in repr(config)
    assert "codex.exe" not in repr(config.codex)
    with pytest.raises((AttributeError, TypeError)):
        cast(Any, config.codex).enabled = False


@pytest.mark.parametrize("runner", [r"C:\Tools\codex.exe", r"\\server\share\codex.exe"])
def test_config_accepts_only_fully_qualified_windows_runners(runner: str) -> None:
    assert LocalConfig.from_mapping({"codex": {"enabled": True, "runner": runner}}).codex.runner == runner


@pytest.mark.parametrize("value", [
    {"authCookie": "secret"}, {"codex": {"api_key": "secret"}},
    {"opencode_go": {"token": "secret"}},
    {"opencode_go": {"api_key": "secret"}},
    {"codex": {"runner": r"\Tools\codex.exe", "enabled": True}},
    {"codex": {"runner": r"C:Tools\codex.exe", "enabled": True}},
])
def test_config_rejects_credentials_and_non_absolute_runners(value: dict[str, object]) -> None:
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_mapping(value)
    assert "secret" not in str(error.value)


def test_current_rejects_nested_credential_keys_before_provider_isolation() -> None:
    private_value = "nested-private-value"
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_mapping(
            {"opencode_go": {"nested": [{"headers": {"api_key": private_value}}]}},
            provider_errors=set(),
        )
    assert private_value not in str(error.value)


def test_current_rejects_direct_provider_credential_keys_before_provider_isolation() -> None:
    private_value = "direct-private-value"
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_mapping(
            {"opencode_go": {"api_key": private_value}},
            provider_errors=set(),
        )
    assert private_value not in str(error.value)


@pytest.mark.parametrize("timeout", [0, -1, 10.1, math.nan, math.inf, 10**10000, "bad", None], ids=["zero", "negative", "oversized", "nan", "inf", "huge", "text", "none"])
def test_timeout_errors_are_finite_deterministic_and_safe(timeout: object) -> None:
    with pytest.raises(ConfigError) as error:
        OpenCodeGoConfig(timeout_seconds=cast(float, timeout))
    assert str(error.value) == "invalid timeout_seconds"


@pytest.mark.parametrize("timeout", [1, 7, 7.5, 10])
def test_current_opencode_timeout_accepts_json_numbers(timeout: float) -> None:
    assert OpenCodeGoConfig.from_mapping({"timeout_seconds": timeout}).timeout_seconds == float(timeout)


@pytest.mark.parametrize("timeout", ["7", True, math.nan, math.inf, -math.inf])
def test_current_opencode_timeout_rejects_non_json_numbers(timeout: object) -> None:
    with pytest.raises(ConfigError, match="^invalid timeout_seconds$"):
        OpenCodeGoConfig.from_mapping({"timeout_seconds": timeout})


@pytest.mark.parametrize("timeout", [1, 7, 120])
def test_current_codex_timeout_accepts_json_numbers(timeout: float) -> None:
    assert CodexConfig.from_mapping({"timeout_seconds": timeout}).timeout_seconds == float(timeout)


@pytest.mark.parametrize("timeout", ["7", True, math.nan, math.inf, -math.inf])
def test_current_codex_timeout_rejects_non_json_numbers(timeout: object) -> None:
    with pytest.raises(ConfigError, match="^invalid timeout_seconds$"):
        CodexConfig.from_mapping({"timeout_seconds": timeout})





@pytest.mark.parametrize("invalid_provider", ("codex", "opencode_go"))
def test_current_provider_errors_are_captured_independently_and_substituted(invalid_provider: str) -> None:
    raw = {
        "codex": {"enabled": True, "runner": r"C:\\Tools\\codex.exe"},
        "opencode_go": {"enabled": True},
    }
    raw[invalid_provider]["timeout_seconds"] = 121 if invalid_provider == "codex" else 11
    errors: set[ProviderKey] = set()

    config = LocalConfig.from_mapping(raw, provider_errors=errors)

    assert {getattr(provider, "value", provider) for provider in errors} == {invalid_provider}
    assert getattr(config, invalid_provider).enabled is False
    peer = "opencode_go" if invalid_provider == "codex" else "codex"
    assert getattr(config, peer).enabled is True


def test_current_provider_error_markers_are_safe_and_atomic_without_isolation() -> None:
    errors: set[ProviderKey] = set()
    config = LocalConfig.from_mapping(
        {
            "opencode_go": {
                "enabled": True,
                "timeout_seconds": 11,
                "private_path": r"C:\\private\\secret.json",
            }
        },
        provider_errors=errors,
    )

    assert "secret.json" not in repr(config)
    assert "private_path" not in repr(errors)
    with pytest.raises(ConfigError):
        LocalConfig.from_mapping({"opencode_go": {"timeout_seconds": 11}})


def test_legacy_config_parser_names_are_absent() -> None:
    legacy_parser = "from_" + "v2_mapping"
    assert not hasattr(CodexConfig, legacy_parser)
    assert not hasattr(OpenCodeGoConfig, legacy_parser)
    assert not hasattr(LocalConfig, legacy_parser)


def test_current_projection_keeps_canonical_order_and_aggregate_partial() -> None:
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, outcome=ProviderOutcome.UNDETECTED),
        ProviderView(
            ProviderKey.OPENCODE_GO,
            ProviderState.SAFE_ERROR,
            SafeError(SafeErrorCode.CONFIGURATION_INVALID),
            outcome=ProviderOutcome.EXECUTION_ERROR,
        ),
    )

    projected = json.loads(
        project_bytes(
            ProjectionInput(document, frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO}))
        )
    )

    assert [provider["provider"] for provider in projected["providers"]] == ["codex", "opencode_go"]
    assert projected["execution_state"] == "partial"
    assert projected["providers"][1]["execution_error"] == {
        "code": "provider_failed",
        "phase": "provider",
    }


def test_codex_timeout_range_remains_independent_from_opencode_timeout_range() -> None:
    config = LocalConfig.from_mapping({"codex": {"enabled": True, "runner": r"C:\\Tools\\codex.exe", "timeout_seconds": 120}, "opencode_go": {"timeout_seconds": 10}})
    assert config.codex.timeout_seconds == MAX_CODEX_TIMEOUT_SECONDS
    with pytest.raises(ConfigError, match="^invalid timeout_seconds$"):
        LocalConfig.from_mapping({"codex": {"enabled": True, "runner": r"C:\\Tools\\codex.exe", "timeout_seconds": 120.1}, "opencode_go": {}})


def test_models_have_closed_states_codes_and_safe_validation() -> None:
    assert {code.value for code in SafeErrorCode} == {
        "timeout", "provider_error", "internal_error", "configuration_invalid", "invocation_invalid",
        "invalid_provider_data", "unknown_provider_state", "guard_acquisition_failed", "guard_wait_timeout",
        "deadline_exhausted", "cleanup_failed",
    }
    assert {state.value for state in ProviderState} == {"loading", "success", "unavailable", "safe_error"}
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.LOADING),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS),
    )
    assert tuple(view.provider.value for view in document.providers) == ("codex", "opencode_go")
    with pytest.raises(ValueError, match="^invalid provider key$"):
        ProviderView(cast(ProviderKey, "private-workspace"), ProviderState.SUCCESS)
    with pytest.raises(ValueError, match="^invalid provider state$"):
        ProviderView(ProviderKey.CODEX, cast(ProviderState, "secret-state"))
    with pytest.raises(ValueError, match="^invalid safe error code$"):
        SafeError(cast(SafeErrorCode, "secret-workspace-code"))
    with pytest.raises((TypeError, ValueError)):
        DocumentView(())
    with pytest.raises(ValueError, match="^safe_error requires"):
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR)
