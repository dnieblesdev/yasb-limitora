import json
import math

import pytest

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
    project_bytes,
)
from yasb_limitora.config import CodexConfig, DEFAULT_TIMEOUT_SECONDS, MAX_CODEX_TIMEOUT_SECONDS
from yasb_limitora.model import ProviderOutcome
from yasb_limitora.projection_v2 import V2ProjectionInput, project_v2_bytes


def test_config_is_immutable_and_repr_redacts_private_values() -> None:
    config = LocalConfig.from_mapping({
        "codex": {"enabled": True, "runner": r"C:\Tools\codex.exe"},
        "opencode_go": {"enabled": True},
    })
    assert config.codex.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert "private-workspace" not in repr(config)
    assert "codex.exe" not in repr(config.codex)
    with pytest.raises((AttributeError, TypeError)):
        config.codex.enabled = False


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


def test_v2_rejects_nested_credential_keys_before_provider_isolation() -> None:
    secret = "nested-private-value"
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_v2_mapping(
            {"opencode_go": {"nested": [{"headers": {"api_key": secret}}]}},
            provider_errors=set(),
        )
    assert secret not in str(error.value)


def test_v2_rejects_direct_provider_credential_keys_before_provider_isolation() -> None:
    secret = "direct-private-value"
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_v2_mapping(
            {"opencode_go": {"api_key": secret}},
            provider_errors=set(),
        )
    assert secret not in str(error.value)


@pytest.mark.parametrize("timeout", [0, -1, 10.1, math.nan, math.inf, 10**10000, "bad", None], ids=["zero", "negative", "oversized", "nan", "inf", "huge", "text", "none"])
def test_timeout_errors_are_finite_deterministic_and_safe(timeout: object) -> None:
    with pytest.raises(ConfigError) as error:
        OpenCodeGoConfig(timeout_seconds=timeout)
    assert str(error.value) == "invalid timeout_seconds"


@pytest.mark.parametrize("timeout", [1, 7, 7.5, 10])
def test_opencode_timeout_accepts_json_numbers(timeout: int | float) -> None:
    assert OpenCodeGoConfig.from_v2_mapping({"timeout_seconds": timeout}).timeout_seconds == float(timeout)


@pytest.mark.parametrize("timeout", ["7", True, math.nan, math.inf, -math.inf])
def test_opencode_timeout_rejects_non_json_numbers(timeout: object) -> None:
    with pytest.raises(ConfigError, match="^invalid timeout_seconds$"):
        OpenCodeGoConfig.from_v2_mapping({"timeout_seconds": timeout})


@pytest.mark.parametrize("timeout", [1, 7, 120])
def test_codex_timeout_accepts_json_numbers(timeout: int | float) -> None:
    assert CodexConfig.from_v2_mapping({"timeout_seconds": timeout}).timeout_seconds == float(timeout)


@pytest.mark.parametrize("timeout", ["7", True, math.nan, math.inf, -math.inf])
def test_codex_timeout_rejects_non_json_numbers(timeout: object) -> None:
    with pytest.raises(ConfigError, match="^invalid timeout_seconds$"):
        CodexConfig.from_v2_mapping({"timeout_seconds": timeout})


def test_v1_timeout_retains_string_coercion_compatibility() -> None:
    assert LocalConfig.from_mapping({"codex": {"timeout_seconds": "7"}}).codex.timeout_seconds == 7.0
    assert LocalConfig.from_mapping({"opencode_go": {"timeout_seconds": "7"}}).opencode_go.timeout_seconds == 7.0


@pytest.mark.parametrize("invalid_provider", ("codex", "opencode_go"))
def test_v2_provider_errors_are_captured_independently_and_substituted(invalid_provider: str) -> None:
    raw = {
        "codex": {"enabled": True, "runner": r"C:\\Tools\\codex.exe"},
        "opencode_go": {"enabled": True},
    }
    raw[invalid_provider]["timeout_seconds"] = 121 if invalid_provider == "codex" else 11
    errors: set[object] = set()

    config = LocalConfig.from_v2_mapping(raw, provider_errors=errors)

    assert {getattr(provider, "value", provider) for provider in errors} == {invalid_provider}
    assert getattr(config, invalid_provider).enabled is False
    peer = "opencode_go" if invalid_provider == "codex" else "codex"
    assert getattr(config, peer).enabled is True


def test_v2_provider_error_markers_are_safe_and_v1_remains_atomic() -> None:
    errors: set[object] = set()
    config = LocalConfig.from_v2_mapping(
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


def test_v2_projection_keeps_canonical_order_and_aggregate_partial() -> None:
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
        project_v2_bytes(
            V2ProjectionInput(document, frozenset({ProviderKey.CODEX, ProviderKey.OPENCODE_GO}))
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
        "invalid_provider_data", "unknown_provider_state",
    }
    assert {state.value for state in ProviderState} == {"loading", "success", "unavailable", "safe_error"}
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.LOADING),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS),
    )
    assert tuple(view.provider.value for view in document.providers) == ("codex", "opencode_go")
    with pytest.raises(ValueError, match="^invalid provider key$"):
        ProviderView("private-workspace", ProviderState.SUCCESS)
    with pytest.raises(ValueError, match="^invalid provider state$"):
        ProviderView(ProviderKey.CODEX, "secret-state")
    with pytest.raises(ValueError, match="^invalid safe error code$"):
        SafeError("secret-workspace-code")


def test_projection_is_exact_utf8_unicode_deterministic_and_redacted() -> None:
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, display_label="成功 ✓"),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, SafeError("provider_error")),
    )
    expected = ('{"version":1,"providers":[{"provider":"codex","state":"success",'
                '"display_label":"成功 ✓"},{"provider":"opencode_go","state":"safe_error",'
                '"error":{"code":"provider_error"}}]}\n').encode("utf-8")
    result = project_bytes(document)
    assert result == expected == project_bytes(document)
    assert json.loads(result.decode("utf-8"))["providers"][0]["display_label"] == "成功 ✓"
    assert result.decode("utf-8").encode("utf-8") == result
    assert "private-workspace" not in result.decode("utf-8")
    with pytest.raises(TypeError):
        project_bytes({"version": 1})  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        DocumentView([])
    with pytest.raises(ValueError, match="^safe_error requires"):
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR)
    with pytest.raises(ValueError, match="^safe_error requires"):
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR)
