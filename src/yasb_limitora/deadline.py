"""Absolute deadline primitives for the JSON contract execution path."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

NANOSECONDS_PER_SECOND = 1_000_000_000
MAX_RESERVE_NS = 250_000_000


@dataclass(frozen=True, slots=True)
class DeadlineContext:
    """A single immutable endpoint shared by all execution phases."""

    t0_ns: int
    deadline_ns: int
    reserve_ns: int
    clock_ns: Callable[[], int] = time.monotonic_ns

    def __post_init__(self) -> None:
        if self.t0_ns < 0 or self.deadline_ns < self.t0_ns:
            raise ValueError("invalid deadline endpoint")
        duration_ns = self.deadline_ns - self.t0_ns
        if not 0 <= self.reserve_ns <= min(MAX_RESERVE_NS, duration_ns):
            raise ValueError("invalid deadline reserve")

    @classmethod
    def from_seconds(
        cls,
        seconds: object,
        *,
        t0_ns: int | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> DeadlineContext:
        if isinstance(seconds, bool):
            raise ValueError("deadline must be a finite positive number")  # noqa: TRY004
        try:
            duration_seconds = float(cast(Any, seconds))
            if not math.isfinite(duration_seconds) or duration_seconds <= 0:
                raise ValueError("deadline must be a finite positive number")
            duration_ns = int(duration_seconds * NANOSECONDS_PER_SECOND)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("deadline must be a finite positive number") from None
        start_ns = clock_ns() if t0_ns is None else t0_ns
        return cls(
            t0_ns=start_ns,
            deadline_ns=start_ns + duration_ns,
            reserve_ns=min(MAX_RESERVE_NS, duration_ns // 4),
            clock_ns=clock_ns,
        )

    def remaining_ns(self) -> int:
        return max(0, self.deadline_ns - self.clock_ns())

    def usable_ns(self) -> int:
        return max(0, self.remaining_ns() - self.reserve_ns)

    def cleanup_ns(self) -> int:
        return min(self.reserve_ns, self.remaining_ns())


__all__ = ("DeadlineContext", "MAX_RESERVE_NS", "NANOSECONDS_PER_SECOND")  # noqa: RUF022
