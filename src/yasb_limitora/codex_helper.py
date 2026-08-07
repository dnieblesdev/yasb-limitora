"""Contained Codex worker; provider code runs only after supervisor READY."""

import json
import os
import re
import struct
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from .codex_supervisor import (
    _CONTROL_CAPACITY,
    _CodexSupervisor,
    _NONCE_LIMIT,
    _PipeTransport,
    _TransportError,
    _TransportTimeout,
    _fd_handle,
    _peek_named_pipe,
    _peek_named_pipe_handle,
)
from .model import (
    MAX_DISPLAY_LABEL_LENGTH,
    MAX_QUOTA_WINDOWS,
    _legacy_state_for_snapshot,
    _parse_canonical_decimal,
    SAFE_SOURCE_IDS,
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    ProviderView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SafeError,
    SafeErrorCode,
    SnapshotFreshness,
    canonical_identity,
)

_MAX_REQUEST = _CONTROL_CAPACITY
_MAX_RESPONSE = 64 * 1024
_CANONICAL_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")
_GATE = "_YASB_CODEX_GATE_HANDLE"
_DATA = "_YASB_CODEX_DATA_HANDLE"
_WIRE_FIELDS = frozenset(("provider", "state", "outcome", "display_label", "error", "snapshot"))
_SNAPSHOT_FIELDS = frozenset(
    ("public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id", "windows")
)
_WINDOW_FIELDS = frozenset(
    ("kind", "scope", "period", "plan_id", "availability", "source_id", "reset_at", "limit", "used", "remaining")
)
_QUANTITY_FIELDS = frozenset(("metric", "value", "unit"))
_ERROR_FIELDS = frozenset(("code",))
_CHILD_BOOTSTRAP = f"""import os,runpy
try:
    gate=int(os.environ.pop({_GATE!r})); data=int(os.environ.pop({_DATA!r}))
    if os.name == "nt":
        import msvcrt
        gate=msvcrt.open_osfhandle(gate, 0); data=msvcrt.open_osfhandle(data, 1)
    nonce=os.environ.pop("_YASB_CODEX_READY_NONCE").encode("ascii")
    if os.read(gate, 1) != b"1": raise ValueError
    os.write(data, b"READY:" + nonce)
    os.environ[{_GATE!r}]=str(gate); os.environ[{_DATA!r}]=str(data); os.environ["_YASB_HELPER_NONCE"]=nonce.decode("ascii")
    runpy.run_module("yasb_limitora.codex_helper", run_name="__main__")
except SystemExit:
    raise
except Exception:
    raise SystemExit(1)
"""


def _read_exact(fd: int, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = os.read(fd, size - len(result))
        if not chunk:
            raise ValueError
        result.extend(chunk)
    return bytes(result)


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if not 0 < written <= len(payload) - offset:
            raise ValueError
        offset += written


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("invalid JSON number")


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes or not 0 < len(payload) <= _MAX_RESPONSE:
        raise ValueError("invalid JSON payload")
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_json_constant,
    )


def _object(value: object, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != fields:
        raise ValueError("invalid JSON object")
    return value


def _enum_value(enum, value: object):
    if type(value) is not str:
        raise ValueError("invalid enum")
    try:
        return enum(value)
    except (TypeError, ValueError):
        raise ValueError("invalid enum") from None


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _decode_timestamp(value: object) -> datetime:
    if type(value) is not str or not _CANONICAL_TIMESTAMP.fullmatch(value):
        raise ValueError("invalid timestamp")
    try:
        parsed = datetime.strptime(value[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise ValueError("invalid timestamp") from None
    return parsed


def _wire_identity(value: object, message: str) -> str:
    return canonical_identity(value, message)


def _wire_source(value: object) -> str | None:
    if value is not None and (type(value) is not str or value not in SAFE_SOURCE_IDS):
        raise ValueError("invalid source id")
    return value


def _quantity_payload(quantity: QuotaQuantity) -> dict[str, str]:
    return {
        "metric": quantity.metric.value,
        "value": format(quantity.value, "f"),
        "unit": quantity.unit,
    }


def _window_payload(window: QuotaWindowView) -> dict[str, object]:
    return {
        "kind": window.kind.value,
        "scope": window.scope,
        "period": window.period,
        "plan_id": window.plan_id,
        "availability": window.availability.value,
        "source_id": window.source_id,
        "reset_at": None if window.reset_at is None else _timestamp(window.reset_at),
        "limit": None if window.limit is None else _quantity_payload(window.limit),
        "used": None if window.used is None else _quantity_payload(window.used),
        "remaining": None if window.remaining is None else _quantity_payload(window.remaining),
    }


def _snapshot_payload(snapshot: ProviderSnapshotView) -> dict[str, object]:
    return {
        "public_state": snapshot.public_state.value,
        "freshness": snapshot.freshness.value,
        "status_observed_at": _timestamp(snapshot.status_observed_at),
        "fetched_at": _timestamp(snapshot.fetched_at),
        "data_at": _timestamp(snapshot.data_at),
        "source_id": snapshot.source_id,
        "windows": [_window_payload(window) for window in snapshot.windows],
    }


def _payload(view: ProviderView) -> bytes:
    item = {
        "provider": view.provider.value,
        "state": view.state.value,
        "outcome": None if view.outcome is None else view.outcome.value,
        "display_label": view.display_label,
        "error": None if view.error is None else {"code": view.error.code.value},
        "snapshot": None if view.snapshot is None else _snapshot_payload(view.snapshot),
    }
    payload = json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > _MAX_RESPONSE:
        raise ValueError("response oversize")
    return payload


def _child_main() -> None:
    gate, data = int(os.environ.pop(_GATE)), int(os.environ.pop(_DATA))
    try:
        size = struct.unpack(">I", _read_exact(gate, 4))[0]
        if not 0 < size <= _MAX_REQUEST:
            raise ValueError
        request = _load_json(_read_exact(gate, size))
        if type(request) is not dict or set(request) != {"runner", "nonce"}:
            raise ValueError
        expected_nonce = os.environ.pop("_YASB_HELPER_NONCE")
        if type(request["nonce"]) is not str or request["nonce"] != expected_nonce:
            raise ValueError
        runner = request["runner"]
        if type(runner) is not list or not all(type(item) is str for item in runner):
            raise ValueError
        from .limitora_api import read_codex

        view = read_codex(runner)
        payload = _payload(view)
    except Exception:  # noqa: BLE001 - contain all worker failures
        payload = _payload(_error(SafeErrorCode.INTERNAL_ERROR))
    _write_all(data, struct.pack(">I", len(payload)) + payload)
    os.close(gate)
    os.close(data)


class _PersistentTransport(_PipeTransport):
    """The READY frame is a prefix; worker responses are length framed."""

    def read_response(self, timeout_seconds=2.0) -> bytes:
        header = self.read_frame(expected_size=4, timeout_seconds=timeout_seconds, reject_trailing=False)
        size = struct.unpack(">I", header)[0]
        if not 0 < size <= _MAX_RESPONSE:
            raise _TransportError("response_oversize")
        payload = self.read_frame(expected_size=size, timeout_seconds=timeout_seconds, max_size=_MAX_RESPONSE, reject_trailing=False)
        available, _ = self._peek(self._read_fd)
        if available:
            raise _TransportError("trailing_data")
        return payload

    def read_response_with_deadline(self, context) -> bytes:
        header = self.read_frame_with_deadline(expected_size=4, context=context)
        size = struct.unpack(">I", header)[0]
        if not 0 < size <= _MAX_RESPONSE:
            raise _TransportError("response_oversize")
        payload = self.read_frame_with_deadline(expected_size=size, context=context, max_size=_MAX_RESPONSE, reject_trailing=False)
        available, _ = self._peek(self._read_fd)
        if available:
            raise _TransportError("trailing_data")
        return payload


class CodexHelperExecutor:
    """Own one supervisor and dispatch only after its READY authorization."""

    def __init__(self, supervisor_factory: Callable[..., object] = _CodexSupervisor, timeout_seconds: float = 2.0) -> None:
        self._factory, self._timeout, self._pending_supervisor = supervisor_factory, timeout_seconds, None
        self._lifecycle, self._active, self._retrying = threading.Lock(), False, False
        self._last_supervisor = None

    def run(self, runner: Sequence[str]) -> ProviderView:
        if isinstance(runner, (str, bytes)) or not isinstance(runner, Sequence) or not all(isinstance(item, str) for item in runner):
            return _error(SafeErrorCode.INVOCATION_INVALID)
        if len(json.dumps({"nonce": "x" * _NONCE_LIMIT, "runner": list(runner)}).encode("utf-8")) > _MAX_REQUEST:
            return _error(SafeErrorCode.INVOCATION_INVALID)
        if not self.retry_cleanup():
            return _error(SafeErrorCode.INTERNAL_ERROR)
        with self._lifecycle:
            if self._pending_supervisor is not None or self._active or self._retrying:
                return _error(SafeErrorCode.INTERNAL_ERROR)
            self._active = True
        transport_box: list[_PersistentTransport] = []

        def transport_factory(read_fd, write_fd, *, nonblocking):
            peek = _peek_named_pipe
            if os.name == "nt":
                read_handle = _fd_handle(read_fd)
                peek = lambda _fd: _peek_named_pipe_handle(read_handle)
            transport = _PersistentTransport(read_fd, write_fd, peek=peek, nonblocking=nonblocking)
            transport_box.append(transport)
            return transport

        supervisor, result = None, _error(SafeErrorCode.INTERNAL_ERROR)
        try:
            supervisor = self._factory(
                command=(sys.executable, "-I", "-E", "-c", _CHILD_BOOTSTRAP),
                transport_factory=transport_factory,
                timeout_seconds=self._timeout,
            )
            self._last_supervisor = supervisor
            supervisor.acquire()
            transport = transport_box[0]
            nonce = getattr(supervisor, "_nonce", b"")
            if not isinstance(nonce, bytes):
                raise TypeError
            request = json.dumps(
                {"nonce": nonce.decode("ascii"), "runner": list(runner)},
                separators=(",", ":"),
            ).encode("utf-8")
            if len(request) > _MAX_REQUEST:
                return _error(SafeErrorCode.INVOCATION_INVALID)
            transport.write_control(struct.pack(">I", len(request)) + request, timeout_seconds=self._timeout)
            result = _decode(transport.read_response(self._timeout))
        except (_TransportTimeout, TimeoutError):
            result = _error(SafeErrorCode.TIMEOUT)
        except Exception:  # noqa: BLE001 - map unknown worker failures safely
            result = _error(SafeErrorCode.PROVIDER_ERROR)
        finally:
            if supervisor is not None:
                try:
                    supervisor.close(self._timeout)
                except Exception:  # noqa: BLE001 - cleanup failure is a safe error
                    with self._lifecycle:
                        self._pending_supervisor = supervisor
                    result = _error(SafeErrorCode.INTERNAL_ERROR)
            with self._lifecycle:
                self._active = False
        return result

    def run_with_deadline(self, runner: Sequence[str], context) -> ProviderView:
        """V2-only execution path consuming one shared absolute endpoint."""
        if isinstance(runner, (str, bytes)) or not isinstance(runner, Sequence) or not all(isinstance(item, str) for item in runner):
            return _error(SafeErrorCode.INVOCATION_INVALID)
        if len(json.dumps({"nonce": "x" * _NONCE_LIMIT, "runner": list(runner)}).encode("utf-8")) > _MAX_REQUEST:
            return _error(SafeErrorCode.INVOCATION_INVALID)
        if not self._retry_cleanup_with_deadline(context):
            return _error(SafeErrorCode.INTERNAL_ERROR)
        with self._lifecycle:
            if self._pending_supervisor is not None or self._active or self._retrying:
                return _error(SafeErrorCode.INTERNAL_ERROR)
            self._active = True
        transport_box: list[_PersistentTransport] = []

        def transport_factory(read_fd, write_fd, *, nonblocking):
            peek = _peek_named_pipe
            if os.name == "nt":
                read_handle = _fd_handle(read_fd)
                peek = lambda _fd: _peek_named_pipe_handle(read_handle)
            transport = _PersistentTransport(read_fd, write_fd, peek=peek, nonblocking=nonblocking)
            transport_box.append(transport)
            return transport

        supervisor, result = None, _error(SafeErrorCode.INTERNAL_ERROR)
        try:
            supervisor = self._factory(
                command=(sys.executable, "-I", "-E", "-c", _CHILD_BOOTSTRAP),
                transport_factory=transport_factory,
                timeout_seconds=self._timeout,
            )
            self._last_supervisor = supervisor
            supervisor.acquire_with_deadline(context)
            transport = transport_box[0]
            nonce = getattr(supervisor, "_nonce", b"")
            if not isinstance(nonce, bytes):
                raise TypeError
            request = json.dumps({"nonce": nonce.decode("ascii"), "runner": list(runner)}, separators=(",", ":")).encode("utf-8")
            if len(request) > _MAX_REQUEST:
                return _error(SafeErrorCode.INVOCATION_INVALID)
            transport.write_control_with_deadline(struct.pack(">I", len(request)) + request, context=context)
            result = _decode(transport.read_response_with_deadline(context))
        except (_TransportTimeout, TimeoutError):
            result = _error(SafeErrorCode.TIMEOUT)
        except Exception:
            result = _error(SafeErrorCode.PROVIDER_ERROR)
        finally:
            if supervisor is not None:
                try:
                    supervisor.close_with_deadline(context)
                except Exception:
                    with self._lifecycle:
                        self._pending_supervisor = supervisor
                    result = _error(SafeErrorCode.INTERNAL_ERROR)
            with self._lifecycle:
                self._active = False
        return result

    def _retry_cleanup_with_deadline(self, context) -> bool:
        with self._lifecycle:
            if self._pending_supervisor is None:
                return True
            if self._active or self._retrying:
                return False
            self._retrying, supervisor = True, self._pending_supervisor
        try:
            supervisor.close_with_deadline(context)
        except Exception:
            with self._lifecycle:
                self._retrying = False
            return False
        with self._lifecycle:
            self._retrying = False
            released = self._pending_supervisor is supervisor
            if released:
                self._pending_supervisor = None
        return released

    def retry_cleanup(self) -> bool:
        with self._lifecycle:
            if self._pending_supervisor is None: return True
            if self._active or self._retrying: return False
            self._retrying, supervisor = True, self._pending_supervisor
        try: supervisor.close(self._timeout)
        except Exception:  # noqa: BLE001 - retain owner for another retry
            with self._lifecycle: self._retrying = False
            return False
        with self._lifecycle:
            self._retrying = False
            released = self._pending_supervisor is supervisor
            if released: self._pending_supervisor = None
        return released


def _error(code: SafeErrorCode) -> ProviderView:
    return ProviderView(
        ProviderKey.CODEX,
        ProviderState.SAFE_ERROR,
        SafeError(code),
        outcome=ProviderOutcome.EXECUTION_ERROR,
    )


def _decode(payload: bytes) -> ProviderView:
    try:
        value = _object(_load_json(payload), _WIRE_FIELDS)
        provider = _enum_value(ProviderKey, value["provider"])
        if provider is not ProviderKey.CODEX:
            raise ValueError("invalid helper provider")
        state = _enum_value(ProviderState, value["state"])
        outcome = None if value["outcome"] is None else _enum_value(ProviderOutcome, value["outcome"])
        label = value["display_label"]
        if label is not None:
            if (
                type(label) is not str
                or len(label) > MAX_DISPLAY_LABEL_LENGTH
                or any(ord(char) < 32 for char in label)
            ):
                raise ValueError("invalid display label")
            label.encode("utf-8")
        raw_error = value["error"]
        error = None
        if state is ProviderState.SAFE_ERROR:
            error_item = _object(raw_error, _ERROR_FIELDS)
            error = SafeError(_enum_value(SafeErrorCode, error_item["code"]))
        elif raw_error is not None:
            raise ValueError("unexpected helper error")
        raw_snapshot = value["snapshot"]
        snapshot = None if raw_snapshot is None else _decode_snapshot(raw_snapshot)
        if outcome is ProviderOutcome.SNAPSHOT:
            if snapshot is None or state is ProviderState.SAFE_ERROR or error is not None:
                raise ValueError("contradictory helper snapshot")
            if state is not _legacy_state_for_snapshot(snapshot):
                raise ValueError("contradictory helper snapshot state")
        elif snapshot is not None:
            raise ValueError("unexpected helper snapshot")
        if outcome in (ProviderOutcome.UNDETECTED, ProviderOutcome.NOT_RUN) and state is not ProviderState.UNAVAILABLE:
            raise ValueError("contradictory helper outcome")
        if outcome is ProviderOutcome.EXECUTION_ERROR and state is not ProviderState.SAFE_ERROR:
            raise ValueError("contradictory helper error")
        return ProviderView(provider, state, error, label, outcome, snapshot)
    except Exception:  # noqa: BLE001 - malformed worker output is safe_error
        return _error(SafeErrorCode.INTERNAL_ERROR)


def _decode_quantity(value: object) -> QuotaQuantity:
    item = _object(value, _QUANTITY_FIELDS)
    metric = _enum_value(QuotaMetricKind, item["metric"])
    unit = _wire_identity(item["unit"], "invalid quota unit")
    return QuotaQuantity(_parse_canonical_decimal(item["value"]), metric, unit)


def _decode_window(value: object) -> QuotaWindowView:
    item = _object(value, _WINDOW_FIELDS)
    plan_id = item["plan_id"]
    if plan_id is not None:
        plan_id = _wire_identity(plan_id, "invalid quota plan id")
    reset_at = None if item["reset_at"] is None else _decode_timestamp(item["reset_at"])
    return QuotaWindowView(
        kind=_enum_value(QuotaWindowKind, item["kind"]),
        scope=_wire_identity(item["scope"], "invalid quota scope"),
        period=_wire_identity(item["period"], "invalid quota period"),
        plan_id=plan_id,
        availability=_enum_value(QuotaAvailability, item["availability"]),
        source_id=_wire_source(item["source_id"]),
        reset_at=reset_at,
        limit=None if item["limit"] is None else _decode_quantity(item["limit"]),
        used=None if item["used"] is None else _decode_quantity(item["used"]),
        remaining=None if item["remaining"] is None else _decode_quantity(item["remaining"]),
    )


def _decode_snapshot(value: object) -> ProviderSnapshotView:
    item = _object(value, _SNAPSHOT_FIELDS)
    windows = item["windows"]
    if type(windows) is not list or len(windows) > MAX_QUOTA_WINDOWS:
        raise ValueError("invalid quota windows")
    decoded_windows = tuple(_decode_window(window) for window in windows)
    identities = tuple((window.kind, window.scope, window.period) for window in decoded_windows)
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate quota window")
    return ProviderSnapshotView(
        public_state=_enum_value(PublicProviderState, item["public_state"]),
        freshness=_enum_value(SnapshotFreshness, item["freshness"]),
        status_observed_at=_decode_timestamp(item["status_observed_at"]),
        fetched_at=_decode_timestamp(item["fetched_at"]),
        data_at=_decode_timestamp(item["data_at"]),
        source_id=_wire_source(item["source_id"]),
        windows=decoded_windows,
    )


if __name__ == "__main__":
    _child_main()


__all__ = ("CodexHelperExecutor",)
