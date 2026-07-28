"""Private pure 04a primitives; 04b owns transaction orchestration."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

__all__: tuple[str, ...] = ()
_CLEANUP = "resource_cleanup_failed"
_INDETERMINATE = "resource_cleanup_indeterminate"
_OWNERSHIP = "ownership_error"
_STALE = "stale_generation"


class _OwnerToken:
    def __repr__(self) -> str:
        return "<_OwnerToken>"


class _GenerationToken:
    def __repr__(self) -> str:
        return "<_GenerationToken>"


class _CloseOutcome(str, Enum):
    CLOSED = "closed"
    RETRY = "retry"


class _EndpointState(str, Enum):
    OPEN = "open"
    CLOSING = "closing"
    BROKEN = "broken"
    TERMINAL = "terminal"
    CLOSED = "closed"


class _PairState(str, Enum):
    OPEN = "open"
    CLOSING = "closing"
    BROKEN = "broken"
    CLOSED = "closed"


class _ResourceError(RuntimeError):
    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class _CleanupError(_ResourceError):
    def __init__(self) -> None:
        super().__init__(_CLEANUP)


class _IndeterminateCleanupError(_ResourceError):
    def __init__(self) -> None:
        super().__init__(_INDETERMINATE)


class _OwnershipError(_ResourceError):
    def __init__(self) -> None:
        super().__init__(_OWNERSHIP)


class _StaleGenerationError(_ResourceError):
    def __init__(self) -> None:
        super().__init__(_STALE)


@dataclass(frozen=True, repr=False)
class _FdIdentity:
    _number: int
    _generation: _GenerationToken

    def __repr__(self) -> str:
        return "<_FdIdentity>"


@dataclass(frozen=True, repr=False)
class _EndpointSpec:
    _identity: _FdIdentity
    _closer: Callable[[_FdIdentity], Any]

    def __repr__(self) -> str:
        return "<_EndpointSpec>"


@dataclass(frozen=True, repr=False)
class _ResourceView:
    _phase: str

    def __repr__(self) -> str:
        return "<_ResourceView>"


class _GenerationRegistry:
    def __init__(self) -> None:
        self._current: dict[int, _FdIdentity] = {}
        self._retired: set[_FdIdentity] = set()

    def __repr__(self) -> str:
        return "<_GenerationRegistry>"

    def _can_register(self, identity: _FdIdentity) -> bool:
        return identity not in self._retired and self._current.get(identity._number) != identity

    def _register(self, identity: _FdIdentity) -> None:
        current = self._current.get(identity._number)
        if current is not None:
            self._retired.add(current)
        self._current[identity._number] = identity

    def _is_current(self, identity: _FdIdentity) -> bool:
        return self._current.get(identity._number) == identity

    def _retire(self, identity: _FdIdentity) -> None:
        if self._is_current(identity):
            self._current.pop(identity._number, None)
        self._retired.add(identity)

    def _close(self, spec: _EndpointSpec) -> _CloseOutcome:
        if not self._is_current(spec._identity):
            raise _StaleGenerationError from None
        try:
            outcome = spec._closer(spec._identity)
        except Exception:
            self._retire(spec._identity)
            raise _IndeterminateCleanupError from None
        if outcome is _CloseOutcome.CLOSED:
            self._retire(spec._identity)
            return outcome
        if outcome is _CloseOutcome.RETRY:
            return outcome
        self._retire(spec._identity)
        raise _IndeterminateCleanupError from None


class _OwnedEndpoint:
    """Private endpoint with no independent ownership authority."""

    def __init__(self, spec: _EndpointSpec, registry: _GenerationRegistry) -> None:
        self._spec: _EndpointSpec | None = spec
        self._registry = registry
        self._state = _EndpointState.OPEN
        self._terminal_error: _ResourceError | None = None

    def __repr__(self) -> str:
        return "<_OwnedEndpoint>"

    def _validate_transfer(self) -> None:
        if self._state is not _EndpointState.OPEN or self._spec is None or not self._registry._is_current(self._spec._identity):
            raise _OwnershipError from None

    def _close(self) -> None:
        if self._state is _EndpointState.CLOSED:
            return
        if self._state is _EndpointState.TERMINAL:
            assert self._terminal_error is not None
            raise self._terminal_error from None
        if self._state is _EndpointState.CLOSING:
            raise _OwnershipError from None
        self._state = _EndpointState.CLOSING
        assert self._spec is not None
        try:
            outcome = self._registry._close(self._spec)
        except _StaleGenerationError as error:
            self._state = _EndpointState.TERMINAL
            self._terminal_error = error
            raise
        except _IndeterminateCleanupError as error:
            self._state = _EndpointState.TERMINAL
            self._terminal_error = error
            raise
        if outcome is _CloseOutcome.RETRY:
            self._state = _EndpointState.BROKEN
            raise _CleanupError from None
        self._spec = None
        self._state = _EndpointState.CLOSED


class _IpcPair:
    """Aggregate-only owner of two privately constructed endpoints."""

    def __init__(self, read: _EndpointSpec, write: _EndpointSpec, owner: _OwnerToken, registry: _GenerationRegistry) -> None:
        self._read = _OwnedEndpoint(read, registry)
        self._write = _OwnedEndpoint(write, registry)
        self._owner = owner
        self._registry = registry
        self._state = _PairState.OPEN

    def __repr__(self) -> str:
        return "<_IpcPair>"

    def _transfer(self, previous: _OwnerToken, current: _OwnerToken) -> None:
        if self._state is not _PairState.OPEN or self._owner is not previous or current is None:
            raise _OwnershipError from None
        self._read._validate_transfer()
        self._write._validate_transfer()
        self._owner = current

    def _close(self, owner: _OwnerToken) -> None:
        if self._state is _PairState.CLOSED:
            return
        if self._state is _PairState.CLOSING or owner is not self._owner:
            raise _OwnershipError from None
        self._state = _PairState.CLOSING
        indeterminate: _IndeterminateCleanupError | None = None
        retry: _CleanupError | None = None
        other: _ResourceError | None = None
        for endpoint in (self._write, self._read):
            try:
                endpoint._close()
            except _IndeterminateCleanupError as error:
                indeterminate = indeterminate or error
            except _CleanupError as error:
                retry = retry or error
            except _ResourceError as error:
                other = other or error
        if indeterminate is not None:
            self._state = _PairState.BROKEN
            raise indeterminate
        if retry is not None:
            self._state = _PairState.BROKEN
            raise retry
        if other is not None:
            self._state = _PairState.BROKEN
            raise other
        self._owner = None
        self._state = _PairState.CLOSED


def _new_endpoint_spec(number: int, generation: _GenerationToken, closer: Callable[[_FdIdentity], Any]) -> _EndpointSpec:
    return _EndpointSpec(_FdIdentity(number, generation), closer)


def _new_ipc_pair(read: _EndpointSpec, write: _EndpointSpec, owner: _OwnerToken, registry: _GenerationRegistry) -> _IpcPair:
    if owner is None or read._identity._number == write._identity._number:
        raise _OwnershipError from None
    if not registry._can_register(read._identity) or not registry._can_register(write._identity):
        raise _OwnershipError from None
    registry._register(read._identity)
    registry._register(write._identity)
    return _IpcPair(read, write, owner, registry)
