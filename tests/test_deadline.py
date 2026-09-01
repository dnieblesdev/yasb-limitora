import pytest

from yasb_limitora.deadline import DeadlineContext


def test_deadline_context_uses_one_absolute_endpoint_and_reserve():
    clock = iter((400, 700, 1_000))
    context = DeadlineContext.from_seconds(1, t0_ns=100, clock_ns=lambda: next(clock))

    assert context.deadline_ns == 1_000_000_100
    assert context.reserve_ns == 250_000_000
    assert context.remaining_ns() == 999_999_700
    assert context.usable_ns() == 749_999_400
    assert context.cleanup_ns() == 250_000_000


def test_deadline_context_reserve_is_a_quarter_for_short_deadlines():
    context = DeadlineContext.from_seconds(1, t0_ns=0, clock_ns=lambda: 0)
    assert context.reserve_ns == 250_000_000

    short = DeadlineContext(t0_ns=0, deadline_ns=100, reserve_ns=25, clock_ns=lambda: 100)
    assert short.remaining_ns() == 0
    assert short.usable_ns() == 0
    assert short.cleanup_ns() == 0


def test_deadline_context_rejects_non_finite_or_non_positive_duration():
    with pytest.raises(ValueError):
        DeadlineContext.from_seconds(0, t0_ns=0)
    with pytest.raises(ValueError):
        DeadlineContext.from_seconds(float("inf"), t0_ns=0)
