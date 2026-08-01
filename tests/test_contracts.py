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
from yasb_limitora.config import DEFAULT_TIMEOUT_SECONDS


def test_config_is_immutable_and_repr_redacts_private_values() -> None:
    config = LocalConfig.from_mapping({
        "codex": {"enabled": True, "runner": r"C:\Tools\codex.exe", "workspace_id": "private-workspace"},
        "opencode_go": {"enabled": True, "workspace_id": "other-private"},
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
    {"codex": {"runner": r"\Tools\codex.exe", "enabled": True}},
    {"codex": {"runner": r"C:Tools\codex.exe", "enabled": True}},
])
def test_config_rejects_credentials_and_non_absolute_runners(value: dict[str, object]) -> None:
    with pytest.raises(ConfigError) as error:
        LocalConfig.from_mapping(value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, 10**10000, "bad", None], ids=["zero", "negative", "nan", "inf", "oversized", "text", "none"])
def test_timeout_errors_are_finite_deterministic_and_safe(timeout: object) -> None:
    with pytest.raises(ConfigError) as error:
        OpenCodeGoConfig(timeout_seconds=timeout)
    assert str(error.value) == "invalid timeout_seconds"


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
