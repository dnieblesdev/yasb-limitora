"""Private 04b Windows Job creation, borrowed assignment, and ownership."""

from enum import Enum
from typing import Any

from .isolation.windows_job import DEFAULT_CLEANUP_BUDGET_SECONDS, INVALID_HANDLE, JobError, JobErrorCode, JobState, NativeApi, WindowsJobBoundary

__all__: tuple[str, ...] = ()
_ACQUISITION = "job_acquisition_failed"
_ASSIGNMENT = "job_assignment_failed"
_CLEANUP = "job_cleanup_failed"
_OWNERSHIP = "ownership_error"

class _JobResourceError(RuntimeError):
    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"

class _JobAcquisitionFailure(_JobResourceError):
    def __init__(self, owner: "_JobHandleOwner | None") -> None:
        self.owner = owner
        super().__init__(_ACQUISITION)


class _JobAssignmentError(_JobResourceError):
    def __init__(self) -> None:
        super().__init__(_ASSIGNMENT)


class _JobCleanupError(_JobResourceError):
    def __init__(self) -> None:
        super().__init__(_CLEANUP)


class _OwnershipError(_JobResourceError):
    def __init__(self) -> None:
        super().__init__(_OWNERSHIP)


class _OwnerState(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSING = "closing"
    BROKEN = "broken"
    CLOSED = "closed"
    TRANSFERRED = "transferred"


class _JobHandleOwner:
    """Immediate owner for a newly created Job handle during configuration."""

    def __init__(self, api: NativeApi, handle: Any) -> None:
        self._api, self._handle, self._state = api, handle, _OwnerState.OPEN

    def __repr__(self) -> str:
        return "<_JobHandleOwner>"

    def close(self) -> None:
        if self._state is _OwnerState.CLOSED:
            return
        if self._state not in (_OwnerState.OPEN, _OwnerState.BROKEN):
            raise _OwnershipError from None
        self._state = _OwnerState.CLOSING
        try:
            if self._handle is None or not self._api.terminate(self._handle) or not self._api.close(self._handle):
                raise RuntimeError
        except Exception:
            self._state = _OwnerState.BROKEN
            raise _JobCleanupError from None
        self._handle, self._state = None, _OwnerState.CLOSED

    def _transfer_to_boundary(self) -> "_JobOwner":
        if self._state is not _OwnerState.OPEN or self._handle is None:
            raise _OwnershipError from None
        boundary = WindowsJobBoundary._from_owned_job(self._api, self._handle)
        self._handle, self._state = None, _OwnerState.TRANSFERRED
        return _JobOwner(boundary)

def _acquire_job_owner(api: NativeApi) -> "_JobOwner":
    try:
        handle = api.create_job()
        if not handle or handle == INVALID_HANDLE:
            raise RuntimeError
    except Exception:
        raise _JobAcquisitionFailure(None) from None
    owner = _JobHandleOwner(api, handle)
    try:
        if not api.make_non_inheritable(handle) or not api.enable_kill_on_close(handle):
            raise RuntimeError
    except Exception:
        try:
            owner.close()
        except _JobCleanupError:
            raise _JobAcquisitionFailure(owner) from None
        raise _JobAcquisitionFailure(None) from None
    return owner._transfer_to_boundary()


class _JobOwner:
    """Retryable Job/tree owner using the legacy-compatible boundary."""

    def __init__(self, boundary: WindowsJobBoundary) -> None:
        self._boundary, self._state = boundary, _OwnerState.OPEN

    def __repr__(self) -> str:
        return "<_JobOwner>"

    def assign_borrowed_handle(self, handle: Any, *, allow_nested: bool = False) -> None:
        if self._state is not _OwnerState.OPEN:
            raise _OwnershipError from None
        try:
            self._boundary.assign_borrowed_handle(handle, allow_nested=allow_nested)
        except JobError:
            self._state = _OwnerState.CLOSED if self._boundary.state.value == "closed" else _OwnerState.BROKEN
            raise _JobAssignmentError from None
        self._state = _OwnerState.ASSIGNED

    def close(self, timeout_seconds: object = DEFAULT_CLEANUP_BUDGET_SECONDS) -> None:
        if self._state is _OwnerState.CLOSED:
            return
        if self._state is _OwnerState.CLOSING:
            raise _OwnershipError from None
        self._state = _OwnerState.CLOSING
        try:
            self._boundary.close(timeout_seconds)
        except JobError as error:
            self._state = _OwnerState.CLOSED if self._boundary.state is JobState.CLOSED else _OwnerState.BROKEN
            if error.code is JobErrorCode.TIMEOUT:
                raise
            raise _JobCleanupError from None
        self._state = _OwnerState.CLOSED

    def close_with_deadline(self, context) -> None:
        """Close the real Job boundary using the shared v2 deadline."""
        if self._state is _OwnerState.CLOSED:
            return
        if self._state is _OwnerState.CLOSING:
            raise _OwnershipError from None
        self._state = _OwnerState.CLOSING
        try:
            self._boundary.close_with_deadline(context)
        except JobError as error:
            self._state = _OwnerState.CLOSED if self._boundary.state is JobState.CLOSED else _OwnerState.BROKEN
            if error.code is JobErrorCode.TIMEOUT:
                raise
            raise _JobCleanupError from None
        self._state = _OwnerState.CLOSED
