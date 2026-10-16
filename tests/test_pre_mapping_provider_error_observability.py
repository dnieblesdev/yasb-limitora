"""Pre-mapping ProviderError observability.

The adapter maps a provider failure to a safe code and redacts everything else, so the
original released ``ProviderError`` is destroyed inside the read boundary before any
observer can see it. This unit observes that object sanitized, at that boundary, using the
already-merged observer.

Scope limits, intentional:
  * no causal ordering and no timestamp comparison is asserted anywhere;
  * no cross-process correlation is claimed;
  * only ``error_type`` and the existing ``failure_stage`` projection are recorded.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from limitora.models import ProviderId

from yasb_limitora import _native_proof_observability as diagnostics
from yasb_limitora import limitora_api
from yasb_limitora.model import SafeErrorCode

import limitora


PRIVATE_MESSAGE = "private provider detail that must never be persisted"


def _provider_error() -> limitora.ProviderError:
    return limitora.ProviderError(
        limitora.ProviderErrorKind.TRANSPORT,
        ProviderId("codex"),
        PRIVATE_MESSAGE,
        retryable=False,
    )


def _read_with(monkeypatch, tmp_path: Path, root: Path | None, error: BaseException):
    """Drive the real Codex adapter with a fake client that raises ``error``."""
    if root is None:
        monkeypatch.delenv(diagnostics._ENV_ROOT, raising=False)
    else:
        monkeypatch.setenv(diagnostics._ENV_ROOT, str(root))

    def read_status(_request):
        raise error

    client = SimpleNamespace(read_status=read_status)
    adapter = limitora_api.CodexLimitoraAdapter(activate=lambda _config: client)
    return adapter.read(("C:\\codex.exe",))


def _helper_rows(root: Path) -> list[dict]:
    path = root / "helper.jsonl"
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


# --- The gap: today the original provider failure is observed by nobody -------------

def test_provider_error_is_observed_before_redaction(monkeypatch, tmp_path: Path) -> None:
    view = _read_with(monkeypatch, tmp_path, tmp_path, _provider_error())
    rows = _helper_rows(tmp_path)
    captured = [row for row in rows if row["event"] == "original_exception"]
    assert len(captured) == 1, rows
    assert captured[0]["error_type"] == "ProviderError"
    assert captured[0]["failure_stage"] == "response"
    # The mapping still produced the same safe outcome.
    assert view.error is not None and view.error.code is SafeErrorCode.PROVIDER_ERROR


def test_observation_is_sanitized(monkeypatch, tmp_path: Path) -> None:
    _read_with(monkeypatch, tmp_path, tmp_path, _provider_error())
    persisted = (tmp_path / "helper.jsonl").read_bytes()
    assert PRIVATE_MESSAGE.encode("utf-8") not in persisted
    assert b"private" not in persisted
    row = [r for r in _helper_rows(tmp_path) if r["event"] == "original_exception"][0]
    assert set(row) <= {"role", "event", "monotonic_ns", "error_type", "failure_stage"}
    assert row["role"] == "helper"


def test_mapping_and_public_result_are_unchanged(monkeypatch, tmp_path: Path) -> None:
    """Diagnostics on and off must produce an identical public view."""
    off = _read_with(monkeypatch, tmp_path, None, _provider_error())
    on = _read_with(monkeypatch, tmp_path, tmp_path, _provider_error())
    assert off == on
    assert off.error is not None and off.error.code is SafeErrorCode.PROVIDER_ERROR
    assert off.state is on.state and off.outcome is on.outcome


def test_disabled_diagnostics_write_nothing(monkeypatch, tmp_path: Path) -> None:
    _read_with(monkeypatch, tmp_path, None, _provider_error())
    assert not (tmp_path / "helper.jsonl").exists()


@pytest.mark.parametrize("kind", [limitora.ProviderErrorKind.UNAUTHORIZED,
                                  limitora.ProviderErrorKind.RATE_LIMITED,
                                  limitora.ProviderErrorKind.SOURCE_UNAVAILABLE])
def test_other_provider_kinds_keep_their_existing_mapping(monkeypatch, tmp_path: Path, kind) -> None:
    error = limitora.ProviderError(kind, ProviderId("codex"), PRIVATE_MESSAGE, retryable=False)
    view = _read_with(monkeypatch, tmp_path, tmp_path, error)
    assert view.error is not None and view.error.code is SafeErrorCode.PROVIDER_ERROR
    captured = [r for r in _helper_rows(tmp_path) if r["event"] == "original_exception"]
    assert len(captured) == 1 and captured[0]["error_type"] == "ProviderError"


def test_observer_failure_cannot_replace_the_provider_result(monkeypatch, tmp_path: Path) -> None:
    def explode(*_args, **_kwargs):
        raise KeyboardInterrupt("private observer failure")

    monkeypatch.setattr(diagnostics, "record_from_environment", explode)
    view = _read_with(monkeypatch, tmp_path, tmp_path, _provider_error())
    assert view.error is not None and view.error.code is SafeErrorCode.PROVIDER_ERROR


def test_unrelated_exceptions_still_map_without_observation(monkeypatch, tmp_path: Path) -> None:
    """Only the released ProviderError boundary is observed; nothing else changes."""
    view = _read_with(monkeypatch, tmp_path, tmp_path, TypeError("private type failure"))
    assert view.error is not None and view.error.code is SafeErrorCode.CONFIGURATION_INVALID
    assert _helper_rows(tmp_path) == []


def test_timeout_provider_error_keeps_timeout_mapping(monkeypatch, tmp_path: Path) -> None:
    """The existing TRANSPORT+timeout branch must be preserved exactly."""
    timeout_message = sorted(limitora_api._TRANSPORT_TIMEOUT_MESSAGES)[0]
    error = limitora.ProviderError(
        limitora.ProviderErrorKind.TRANSPORT, ProviderId("codex"),
        timeout_message, retryable=True,
    )
    view = _read_with(monkeypatch, tmp_path, tmp_path, error)
    assert view.error is not None and view.error.code is SafeErrorCode.TIMEOUT
    captured = [r for r in _helper_rows(tmp_path) if r["event"] == "original_exception"]
    assert len(captured) == 1
