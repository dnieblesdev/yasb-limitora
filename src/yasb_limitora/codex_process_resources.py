"""Private 04c Popen ownership and process/Job aggregate primitives."""

import math
from enum import Enum
from typing import Any

from .codex_job_resources import _JobOwner, _JobResourceError, _OwnerState
from .isolation.windows_job import DEFAULT_CLEANUP_BUDGET_SECONDS, EMERGENCY_CLEANUP_BUDGET_SECONDS, INVALID_HANDLE, MAX_CLEANUP_SECONDS

__all__: tuple[str, ...] = ()
_ADAPTATION = "popen_handle_adaptation_failed"
_CLEANUP = "popen_cleanup_failed"
_OWNERSHIP = "ownership_error"
_TIMEOUT = "timeout"


class _ProcessResourceError(RuntimeError):
    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class _PopenAdaptationError(_ProcessResourceError):
    def __init__(self) -> None:
        super().__init__(_ADAPTATION)


class _PopenCleanupError(_ProcessResourceError):
    def __init__(self) -> None:
        super().__init__(_CLEANUP)


class _PopenTimeoutError(_ProcessResourceError):
    def __init__(self) -> None:
        super().__init__(_TIMEOUT)


class _OwnershipError(_ProcessResourceError):
    def __init__(self) -> None:
        super().__init__(_OWNERSHIP)


class _PopenState(str, Enum):
    REGISTERED = "registered"
    ADAPTED = "adapted"
    CLOSING = "closing"
    BROKEN = "broken"
    CLOSED = "closed"


class _HelperState(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSING = "closing"
    BROKEN = "broken"
    CLOSED = "closed"


def _timeout(value: object) -> float:
    if type(value) not in (int, float):
        raise _PopenTimeoutError from None
    try: seconds = float(value)
    except (ValueError, OverflowError): raise _PopenTimeoutError from None
    if not math.isfinite(seconds) or seconds < 0:
        raise _PopenTimeoutError from None
    return min(seconds, MAX_CLEANUP_SECONDS)


def _compat_native_handle(popen: Any) -> Any:
    try:
        handle = getattr(popen, "_handle")
        if handle is None or handle == INVALID_HANDLE:
            raise RuntimeError
        return handle
    except Exception:
        raise _PopenAdaptationError from None


class _PopenProcessOwner:
    """Non-fallible Popen registration followed by isolated handle adaptation."""

    def __init__(self, popen: Any) -> None:
        self._popen = popen
        self._native_handle: Any | None = None
        self._state = _PopenState.REGISTERED

    def __repr__(self) -> str:
        return "<_PopenProcessOwner>"

    @classmethod
    def register(cls, popen: Any) -> "_PopenProcessOwner":
        return cls(popen)

    def adapt_native_handle(self) -> Any:
        if self._state is _PopenState.ADAPTED:
            return self._native_handle
        if self._state is not _PopenState.REGISTERED:
            raise _OwnershipError from None
        handle = _compat_native_handle(self._popen)
        self._native_handle = handle
        self._state = _PopenState.ADAPTED
        return handle

    def _release_handle(self) -> None:
        if self._native_handle is None:
            return
        release = getattr(self._native_handle, "Close", None) or getattr(self._native_handle, "close", None)
        if callable(release): release()

    def close(self, timeout_seconds: object = DEFAULT_CLEANUP_BUDGET_SECONDS) -> None:
        if self._state is _PopenState.CLOSED:
            return
        if self._state is _PopenState.CLOSING:
            raise _OwnershipError from None
        timeout_error = False
        try: timeout = _timeout(timeout_seconds)
        except _PopenTimeoutError:
            timeout, timeout_error = EMERGENCY_CLEANUP_BUDGET_SECONDS, True
        self._state = _PopenState.CLOSING
        try:
            if self._popen.poll() is None:
                self._popen.terminate()
                self._popen.wait(timeout=timeout)
            self._release_handle()
        except Exception:
            self._state = _PopenState.BROKEN
            raise _PopenCleanupError from None
        self._popen, self._native_handle, self._state = None, None, _PopenState.CLOSED
        if timeout_error:
            raise _PopenTimeoutError from None

    def close_with_deadline(self, context) -> None:
        if self._state is _PopenState.CLOSED:
            return
        if context.cleanup_ns() <= 0:
            raise _PopenTimeoutError from None
        self._state = _PopenState.CLOSING
        try:
            if self._popen.poll() is None:
                self._popen.terminate()
                remaining = context.cleanup_ns()
                if remaining <= 0:
                    raise _PopenTimeoutError from None
                self._popen.wait(timeout=remaining / 1_000_000_000)
            self._release_handle()
        except Exception:
            self._state = _PopenState.BROKEN
            raise _PopenCleanupError from None
        self._popen, self._native_handle, self._state = None, None, _PopenState.CLOSED


class _HelperProcessResources:
    """Job-first aggregate that retains both owners while Job cleanup is pending."""

    def __init__(self, popen: _PopenProcessOwner) -> None:
        self._popen, self._job = popen, None
        self._state, self._job_closed = _HelperState.OPEN, False

    def __repr__(self) -> str:
        return "<_HelperProcessResources>"

    def attach_job(self, job: _JobOwner) -> None:
        if self._state is not _HelperState.OPEN or self._job is not None or self._popen._state is not _PopenState.ADAPTED:
            raise _OwnershipError from None
        self._job = job
        try: job.assign_borrowed_handle(self._popen._native_handle)
        except _JobResourceError:
            self._state = _HelperState.BROKEN
            raise
        self._state = _HelperState.ASSIGNED

    def close(self, timeout_seconds: object = DEFAULT_CLEANUP_BUDGET_SECONDS) -> None:
        if self._state is _HelperState.CLOSED:
            return
        if self._state is _HelperState.CLOSING:
            raise _OwnershipError from None
        self._state = _HelperState.CLOSING
        if self._job is not None and not self._job_closed:
            try: self._job.close(timeout_seconds)
            except Exception:
                self._state = _HelperState.BROKEN
                raise
            self._job_closed = True
        try: self._popen.close(timeout_seconds)
        except _ProcessResourceError:
            self._state = _HelperState.CLOSED if self._popen._state is _PopenState.CLOSED else _HelperState.BROKEN
            raise
        self._state = _HelperState.CLOSED

    def close_with_deadline(self, context) -> None:
        if self._state is _HelperState.CLOSED:
            return
        if self._state is _HelperState.CLOSING:
            raise _OwnershipError from None
        self._state = _HelperState.CLOSING
        if self._job is not None and not self._job_closed:
            try:
                close = getattr(self._job, "close_with_deadline", None)
                if close is None:
                    raise _JobResourceError("deadline_adapter_missing")
                close(context)
            except Exception:
                self._state = _HelperState.BROKEN
                raise
            self._job_closed = True
        try:
            close = getattr(self._popen, "close_with_deadline", None)
            if close is None:
                raise _PopenCleanupError from None
            close(context)
        except _ProcessResourceError:
            self._state = _HelperState.CLOSED if self._popen._state is _PopenState.CLOSED else _HelperState.BROKEN
            raise
        self._state = _HelperState.CLOSED
