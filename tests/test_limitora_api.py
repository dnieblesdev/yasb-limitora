"""Public Limitora reset evidence through the adapter and JSON boundary."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from limitora import (
    Freshness, ProviderId, ProviderSnapshot, ProviderState, ProviderStatus,
    RateLimitResetCredit, RateLimitResetCreditsSummary, RateLimitResetCreditStatus,
    RateLimitResetType, SourceMetadata, StatusSnapshotResult,
)
from limitora.models import MetricKind, Quantity, QuotaWindow, ValueAvailability, WindowKind

from yasb_limitora.limitora_api import CodexLimitoraAdapter
from yasb_limitora.model import (
    DocumentView, ProviderKey, ProviderState as ViewState, ProviderView,
    PublicProviderState, RateLimitResetCreditsView, SafeErrorCode, SnapshotFreshness,
)
from yasb_limitora.projection import ProjectionInput, project_document

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
FIVE_HOUR_RESET = NOW + timedelta(hours=4)
WEEKLY_RESET = NOW + timedelta(days=3)
CODEX_SOURCE = "codex-app-server-v2"


def credit(days=1, status=RateLimitResetCreditStatus.AVAILABLE):
    return RateLimitResetCredit(RateLimitResetType.CODEX_RATE_LIMITS, status, NOW,
                               None if days is None else NOW + timedelta(days=days),
                               "private title", "private description")


def quantity(value):
    return Quantity(Decimal(value), MetricKind.COMMERCIAL_QUOTA, "percentage_points")


def window(period, remaining, reset_at):
    used = Decimal("100") - Decimal(remaining)
    return QuotaWindow(
        WindowKind.COMMERCIAL_QUOTA, "account", period, "plus", ValueAvailability.KNOWN,
        SourceMetadata(CODEX_SOURCE), quantity("100"), quantity(str(used)), quantity(remaining), reset_at,
    )


def windows():
    """Build fresh public quota evidence per snapshot; no object may be shared between reads."""
    return (window("five_hour", "75", FIVE_HOUR_RESET), window("weekly", "40", WEEKLY_RESET))


EXPECTED_WINDOWS = (
    ("commercial_quota", "account", "five_hour", "plus", "known", CODEX_SOURCE, "100", "25", "75", FIVE_HOUR_RESET),
    ("commercial_quota", "account", "weekly", "plus", "known", CODEX_SOURCE, "100", "60", "40", WEEKLY_RESET),
)
EXPECTED_TOOLTIP = "\n".join((
    "Codex",
    "State: Available · Fresh",
    "Quota remaining:",
    "5h: 75%",
    "  Renews: 2026-08-01T04:00:00+00:00",
    "Weekly: 40%",
    "  Renews: 2026-08-04T00:00:00+00:00",
))


def snapshot(summary):
    provider = ProviderId("codex")
    value = ProviderSnapshot(provider, ProviderStatus(provider, ProviderState.AVAILABLE, NOW),
                             NOW, NOW, SourceMetadata(CODEX_SOURCE), windows())
    # Bypass the constructor so untrusted or mistyped public reset evidence reaches the adapter.
    object.__setattr__(value, "rate_limit_reset_credits", summary)
    return value


def read(summary, observed_now=NOW):
    calls = []
    adapter = CodexLimitoraAdapter(
        activate=lambda _: SimpleNamespace(read_status=lambda _: StatusSnapshotResult(snapshot(summary), Freshness.FRESH)),
        now=lambda: calls.append(1) or observed_now,
    )
    view = adapter.read(("codex",))
    assert calls == [1]
    return view


def document(view):
    return project_document(ProjectionInput(DocumentView.ordered(
        view, ProviderView(ProviderKey.OPENCODE_GO, ViewState.UNAVAILABLE))),
        timestamp_formatter=lambda value: value.isoformat())


def assert_primary_snapshot_preserved(view, tooltip=EXPECTED_TOOLTIP):
    assert view.error is None
    assert view.outcome.value == "snapshot"
    assert view.snapshot is not None
    value = view.snapshot
    assert (value.public_state, value.freshness) == (PublicProviderState.AVAILABLE, SnapshotFreshness.FRESH)
    assert (value.status_observed_at, value.fetched_at, value.data_at) == (NOW, NOW, NOW)
    assert value.source_id == CODEX_SOURCE
    assert tuple(
        (item.kind.value, item.scope, item.period, item.plan_id, item.availability.value, item.source_id,
         str(item.limit.value), str(item.used.value), str(item.remaining.value), item.reset_at)
        for item in value.windows
    ) == EXPECTED_WINDOWS
    item = document(view)["providers"][0]
    assert item["most_depleted_window"] == {
        "kind": "commercial_quota", "scope": "account", "period": "weekly", "plan_id": "plus",
        "unit": "percentage_points", "source_id": CODEX_SOURCE, "remaining_percentage": "40",
    }
    assert item["compact_text"] == "40%"
    assert item["alternate_text"] == "Weekly: 40% left"
    assert item["tooltip_text"] == tooltip
    assert item["windows"][1]["remaining"] == {"value": "40", "metric": "commercial_quota", "unit": "percentage_points"}
    return item


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
    pair = view.snapshot.rate_limit_reset_credits
    assert pair.available_count == count
    assert pair.next_expires_at == expiry
    assert "private" not in repr(view)
    from yasb_limitora.codex_helper import _decode, _payload
    assert _decode(_payload(view)) == view
    lines = [f"Quota resets available: {count}"]
    if expiry is not None:
        lines.append(f"Next reset expiry: {expiry.isoformat()}")
    item = assert_primary_snapshot_preserved(view, "\n".join((EXPECTED_TOOLTIP, *lines)))
    assert item["rate_limit_reset_credits"] == {
        "available_count": count,
        "next_expires_at": None if expiry is None else expiry.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    assert document(view)["general"]["tooltip_text"] == item["tooltip_text"]
    assert "private" not in str(document(view))


def test_future_is_relative_to_read_clock_not_old_fetch():
    view = read(RateLimitResetCreditsSummary(1, (credit(1),)), NOW + timedelta(days=2))
    assert_primary_snapshot_preserved(view, EXPECTED_TOOLTIP + "\nQuota resets available: 1")
    assert view.snapshot.rate_limit_reset_credits.available_count == 1
    assert view.snapshot.rate_limit_reset_credits.next_expires_at is None


def test_missing_summary_is_not_zero_and_preserves_snapshot():
    view = read(None)
    item = assert_primary_snapshot_preserved(view)
    assert view.snapshot.rate_limit_reset_credits is None
    assert item["rate_limit_reset_credits"] is None
    assert "Quota resets available" not in item["tooltip_text"]
    assert "private" not in str(document(view))


def _bypassed_summary(**overrides):
    summary = RateLimitResetCreditsSummary(1, None)
    for field, value in {"available_count": 1, "credits": None, **overrides}.items():
        object.__setattr__(summary, field, value)
    return summary


@pytest.mark.parametrize("summary", [
    object(),
    "private summary",
    _bypassed_summary(available_count=True),
    _bypassed_summary(available_count=-1),
    _bypassed_summary(available_count=1.5),
    _bypassed_summary(available_count="1"),
], ids=["summary_type", "summary_text", "count_bool", "count_negative", "count_float", "count_string"])
def test_invalid_summary_or_count_omits_reset_pair_and_keeps_snapshot(summary):
    view = read(summary)
    item = assert_primary_snapshot_preserved(view)
    assert view.snapshot.rate_limit_reset_credits is None
    assert item["rate_limit_reset_credits"] is None
    assert "Quota resets available" not in item["tooltip_text"]
    assert "private" not in str(document(view))


@pytest.mark.parametrize("credits", [
    [credit(1)], "private details", (object(),),
], ids=["details_list", "details_text", "credit_type"])
def test_invalid_details_container_never_asserts_expiry(credits):
    view = read(_bypassed_summary(credits=credits))
    item = assert_primary_snapshot_preserved(view, EXPECTED_TOOLTIP + "\nQuota resets available: 1")
    pair = view.snapshot.rate_limit_reset_credits
    assert (pair.available_count, pair.next_expires_at) == (1, None)
    assert item["rate_limit_reset_credits"] == {"available_count": 1, "next_expires_at": None}
    assert "private" not in str(document(view))


def _invalid_credit(field, bad):
    detail = credit()
    object.__setattr__(detail, field, bad)
    return detail


# Malformed detail factories. A count is only preserved when a detail is genuinely
# invalid, not when the adapter aborts the whole detail scan on the first bad entry.
MALFORMED_DETAILS = {
    "object": lambda: object(),
    "status": lambda: _invalid_credit("status", "available"),
    "naive": lambda: _invalid_credit("expires_at", datetime(2026, 8, 2)),
    "text": lambda: _invalid_credit("expires_at", "secret"),
}


def _details(*kinds):
    """Build the named malformed details, or a valid credit, in order."""
    return tuple(credit() if kind == "valid" else MALFORMED_DETAILS[kind]() for kind in kinds)


def _reset_summary(count, credits, bypass=False):
    """Build the public summary; only a non-credit detail bypasses the constructor."""
    return _bypassed_summary(available_count=count, credits=credits) if bypass else RateLimitResetCreditsSummary(count, credits)


@pytest.mark.parametrize(("count", "details", "bypass"), [
    (1, (_invalid_credit("status", "available"),), False),
    (1, (_invalid_credit("expires_at", datetime(2026, 8, 2)),), False),
    (1, (_invalid_credit("expires_at", "secret"),), False),
    (2, (_invalid_credit("status", "available"), credit()), False),
    (0, (_invalid_credit("status", "available"),), False),
    (1, _details("status"), False),
    (1, _details("object", "valid"), True),
    (1, _details("status", "valid"), False),
    (1, _details("valid", "object"), True),
    (1, _details("valid", "status"), False),
    (1, _details("valid", "naive"), False),
    (1, _details("valid", "text"), False),
    (2, _details("object", "valid", "valid"), True),
    (2, _details("valid", "valid", "status"), False),
    (2, _details("valid", "naive", "valid"), False),
    (2, _details("valid", "valid", "text"), False),
    (2, _details("status", "valid", "valid"), False),
], ids=[
    "status_string", "naive_expiry", "expiry_text", "mixed_details", "zero_count",
    "bad_status_only", "count1_object_before_valid", "count1_status_before_valid",
    "count1_object_after_valid", "count1_status_after_valid", "count1_naive_after_valid",
    "count1_text_after_valid", "count2_object_before_two_valid", "count2_status_after_two_valid",
    "count2_naive_between_two_valid", "count2_text_after_two_valid", "count2_status_before_two_valid",
])
def test_invalid_credit_details_retain_valid_count_without_expiry(count, details, bypass):
    view = read(_reset_summary(count, details, bypass))
    item = assert_primary_snapshot_preserved(view, EXPECTED_TOOLTIP + f"\nQuota resets available: {count}")
    pair = view.snapshot.rate_limit_reset_credits
    assert pair.available_count == count
    assert pair.next_expires_at is None
    assert item["rate_limit_reset_credits"] == {"available_count": count, "next_expires_at": None}
    assert "secret" not in str(document(view)) and "private" not in str(document(view))


@pytest.mark.parametrize("mutate", [
    lambda result: object.__setattr__(result.snapshot, "provider_id", ProviderId("opencode-go")),
    lambda result: object.__setattr__(result.snapshot.status, "provider_id", ProviderId("opencode-go")),
    lambda result: object.__setattr__(result.snapshot, "quota_windows", list(result.snapshot.quota_windows)),
    lambda result: object.__setattr__(result.snapshot.quota_windows[1], "kind", "weekly"),
    lambda result: object.__setattr__(result.snapshot.quota_windows[1], "remaining",
                                      SimpleNamespace(value=Decimal("-1"), metric=MetricKind.COMMERCIAL_QUOTA, unit="percentage_points")),
], ids=["provider_identity", "status_identity", "windows_not_tuple", "window_kind", "window_quantity"])
def test_invalid_primary_provider_data_still_fails_closed(mutate):
    result = StatusSnapshotResult(snapshot(RateLimitResetCreditsSummary(1, (credit(),))), Freshness.FRESH)
    mutate(result)
    view = CodexLimitoraAdapter(
        activate=lambda _: SimpleNamespace(read_status=lambda _: result),
        now=lambda: NOW,
    ).read(("codex",))

    assert view.snapshot is None
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert "private" not in repr(view)


def test_invalid_primary_mutation_does_not_damage_later_valid_read():
    """A rejected snapshot must not mutate shared fixture evidence for the next read.

    Exercises one rejected primary read and one valid read directly, without
    invoking other parameterized tests as functions.
    """
    rejected = StatusSnapshotResult(snapshot(RateLimitResetCreditsSummary(1, (credit(),))), Freshness.FRESH)
    object.__setattr__(rejected.snapshot.quota_windows[1], "kind", "weekly")
    rejected_view = CodexLimitoraAdapter(
        activate=lambda _: SimpleNamespace(read_status=lambda _: rejected),
        now=lambda: NOW,
    ).read(("codex",))

    assert rejected_view.snapshot is None
    assert rejected_view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA

    # A fresh valid read must still report the exact known windows, state, and dates.
    view = read(RateLimitResetCreditsSummary(2, (credit(1), credit(2))))
    item = assert_primary_snapshot_preserved(
        view, EXPECTED_TOOLTIP + "\nQuota resets available: 2\nNext reset expiry: 2026-08-02T00:00:00+00:00")
    assert view.snapshot.rate_limit_reset_credits == RateLimitResetCreditsView(2, NOW + timedelta(days=1))
    assert item["rate_limit_reset_credits"] == {
        "available_count": 2,
        "next_expires_at": "2026-08-02T00:00:00.000000Z",
    }
    assert "private" not in str(document(view))


def test_adapter_clock_failure_is_not_silently_ignored():
    view = read(RateLimitResetCreditsSummary(1, (credit(),)), datetime(2026, 8, 1))
    assert view.snapshot is None
    assert view.outcome.value == "execution_error"
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert "private" not in repr(view)


def unorderable_clock(error=TypeError):
    """Return a sampled aware clock whose ordering against an expiry raises.

    `datetime` subclasses survive `astimezone`, so the adapter holds this exact
    clock instance when it compares a candidate expiry against it.
    """

    class Clock(datetime):
        def __lt__(self, other):
            raise error("clock ordering unavailable")

        __gt__ = __lt__

    return Clock(2026, 8, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("error", [TypeError, ValueError], ids=["type_error", "value_error"])
def test_unusable_comparison_clock_stays_a_sanitized_error(error):
    """A valid expiry compared against an unusable clock is not silently accepted.

    The clock is sampled once and UTC-normalized before reset evaluation, so a
    subclass whose ordering raises cannot be reported as a valid count without
    expiry; it must reach the sanitized `invalid_provider_data` boundary.
    """
    clock = unorderable_clock(error)
    view = read(RateLimitResetCreditsSummary(1, (credit(),)), clock)

    assert type(clock.astimezone(timezone.utc)) is type(clock)
    assert view.snapshot is None
    assert view.outcome.value == "execution_error"
    assert view.error.code is SafeErrorCode.INVALID_PROVIDER_DATA
    assert "clock ordering unavailable" not in repr(view)
    assert "private" not in repr(view)

    item = document(view)["providers"][0]
    assert item["outcome"] == "execution_error"
    assert item["rate_limit_reset_credits"] is None
    assert (item["compact_text"], item["alternate_text"]) == ("\u2014", "Quota unavailable \u00b7 request failed")
    assert item["tooltip_text"] == "Codex\nQuota unavailable \u00b7 request failed: invalid_provider_data"
    assert "clock ordering unavailable" not in str(document(view))
