"""D01a1 — Guard domain and real deadline for config.json mutual exclusion.

Context-managed Guard lease keyed by the exact fixed config.json path,
retrying under one 5-second DeadlineContext; bounded release/close cleanup.
"""
from __future__ import annotations

import ntpath
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .deadline import DeadlineContext
from .guard import Guard, GuardError, GuardLease

_CONFIG_DEADLINE_SECONDS = 5.0
_RELEASE_RETRIES = 3


def _fixed_config_path(local_appdata: str) -> str:
    if not local_appdata or not local_appdata.strip():
        raise ValueError("blank LOCALAPPDATA")
    return ntpath.join(local_appdata, "yasb-limitora", "config.json")


@contextmanager
def config_lease(
    local_appdata: str,
    *,
    guard: Guard | None = None,
    deadline_seconds: float = _CONFIG_DEADLINE_SECONDS,
    clock_ns: Callable[[], int] | None = None,
) -> Iterator[GuardLease]:
    """Acquire and guarantee a Guard lease for the fixed config.json path."""
    config_path = _fixed_config_path(local_appdata)
    g = guard if guard is not None else Guard()
    ctx_kwargs: dict[str, Any] = {}
    if clock_ns is not None:
        ctx_kwargs["clock_ns"] = clock_ns
    ctx = DeadlineContext.from_seconds(deadline_seconds, **ctx_kwargs)
    lease: GuardLease | None = None
    try:
        while True:
            try:
                lease = g.acquire(config_path, ctx)
                break
            except GuardError as exc:
                if exc.code == "guard_wait_timeout":
                    if ctx.usable_ns() <= 0:
                        raise GuardError("config-lock-busy") from None
                    continue
                raise
        yield lease
    finally:
        if lease is not None:
            released = any(lease.release() for _ in range(_RELEASE_RETRIES))
            if not released:
                lease.owned = False
            closed = any(lease.close() for _ in range(_RELEASE_RETRIES))
            if not released:
                raise GuardError("config-lock-release-failed")
            if not closed:
                raise GuardError("config-lock-close-failed")
