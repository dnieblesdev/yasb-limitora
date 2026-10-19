"""Public Limitora reset evidence through the adapter and JSON boundary."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from limitora import (
    Freshness, ProviderId, ProviderSnapshot, ProviderState, ProviderStatus,
    RateLimitResetCredit, RateLimitResetCreditsSummary, RateLimitResetCreditStatus,
    RateLimitResetType, SourceMetadata, StatusSnapshotResult,
)

from yasb_limitora.limitora_api import CodexLimitoraAdapter
from yasb_limitora.model import SafeErrorCode

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def credit(days=1, status=RateLimitResetCreditStatus.AVAILABLE):
    return RateLimitResetCredit(RateLimitResetType.CODEX_RATE_LIMITS, status, NOW,
                               None if days is None else NOW + timedelta(days=days),
                               "private title", "private description")


def read(summary, observed_now=NOW):
    provider = ProviderId("codex")
    snapshot = ProviderSnapshot(provider, ProviderStatus(provider, ProviderState.AVAILABLE, NOW),
                                NOW, NOW, SourceMetadata("codex-app-server-v2"),
                                rate_limit_reset_credits=summary)
    calls = []
    adapter = CodexLimitoraAdapter(
        activate=lambda _: SimpleNamespace(read_status=lambda _: StatusSnapshotResult(snapshot, Freshness.FRESH)),
        now=lambda: calls.append(1) or observed_now,
    )
    view = adapter.read(("codex",))
    assert calls == [1]
    return view


@pytest.mark.parametrize("count,details,expiry", [
    (0, None, None), (2, None, None), (0, (credit(1),), None),
    (1, (credit(1), credit(2)), None),
    (2, (credit(3), credit(1)), NOW + timedelta(days=1)),
    (2, (credit(1),), None),
    (2, (credit(1), credit(None)), None),
    (1, (credit(-1), credit(0), credit(2), credit(1, RateLimitResetCreditStatus.REDEEMED),
         credit(1, RateLimitResetCreditStatus.REDEEMING), credit(1, RateLimitResetCreditStatus.UNKNOWN)), NOW + timedelta(days=2)),
])
def test_reset_summary_derivation(count, details, expiry):
    view = read(RateLimitResetCreditsSummary(count, details))
    assert view.error is None
    pair = view.snapshot.rate_limit_reset_credits
    assert pair.available_count == count
    assert pair.next_expires_at == expiry
    assert "private" not in repr(view)
    from yasb_limitora.codex_helper import _decode, _payload
    from yasb_limitora.model import DocumentView, ProviderKey, ProviderState as ViewState, ProviderView
    from yasb_limitora.projection import ProjectionInput, project_document
    assert _decode(_payload(view)) == view
    document = project_document(ProjectionInput(DocumentView.ordered(
        view, ProviderView(ProviderKey.OPENCODE_GO, ViewState.UNAVAILABLE))),
        timestamp_formatter=lambda value: value.isoformat())
    item = document["providers"][0]
    assert item["rate_limit_reset_credits"] == {
        "available_count": count,
        "next_expires_at": None if expiry is None else expiry.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    lines = [f"Quota resets available: {count}"]
    if expiry is not None:
        lines.append(f"Next reset expiry: {expiry.isoformat()}")
    assert item["tooltip_text"].endswith("\n".join(lines))
    assert document["general"]["tooltip_text"] == item["tooltip_text"]
    assert item["compact_text"] == "—"
    assert item["alternate_text"] == "Quota unavailable"
    assert "private" not in str(document)


def test_future_is_relative_to_read_clock_not_old_fetch():
    view = read(RateLimitResetCreditsSummary(1, (credit(1),)), NOW + timedelta(days=2))
    assert view.snapshot.rate_limit_reset_credits.available_count == 1
    assert view.snapshot.rate_limit_reset_credits.next_expires_at is None


def test_missing_summary_is_not_zero():
    assert read(None).snapshot.rate_limit_reset_credits is None


@pytest.mark.parametrize("bad", [True, -1, 1.5, "1"])
def test_invalid_public_count_is_sanitized_even_when_constructor_bypassed(bad):
    summary = RateLimitResetCreditsSummary(1, None)
    object.__setattr__(summary, "available_count", bad)
    view = read(summary)
    assert view.snapshot is None
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA


@pytest.mark.parametrize("field,bad", [("status", "available"), ("expires_at", datetime(2026, 8, 2)), ("expires_at", "secret")])
def test_invalid_public_credit_is_sanitized(field, bad):
    detail = credit()
    object.__setattr__(detail, field, bad)
    view = read(RateLimitResetCreditsSummary(1, (detail,)))
    assert view.snapshot is None
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
