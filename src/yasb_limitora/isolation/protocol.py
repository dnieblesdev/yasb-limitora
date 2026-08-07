"""Bounded nonce-bound JSON-over-bytes protocol for the future helper."""

from collections.abc import Mapping
from enum import Enum
import json
import math
import struct
import time
from typing import Any, Protocol
from ..model import ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode
CONTROL_MAX_BYTES = 16 * 1024
RESPONSE_MAX_BYTES = 64 * 1024
_MAX_NONCE = 128
class ProtocolErrorCode(str, Enum):
    EOF = "eof"
    TRAILING_BYTES = "trailing_bytes"
    OVERSIZE = "oversize"
    INVALID_UTF8 = "invalid_utf8"
    INVALID_JSON = "invalid_json"
    DUPLICATE_KEY = "duplicate_key"
    UNKNOWN_FIELD = "unknown_field"
    INVALID_MESSAGE = "invalid_message"
    NONCE_MISMATCH = "nonce_mismatch"
    INVALID_TRANSITION = "invalid_transition"
    TRANSPORT_TIMEOUT = "transport_timeout"
    TRANSPORT_FAILURE = "transport_failure"
    TRANSPORT_EOF = "transport_eof"
    INVALID_TIMEOUT = "invalid_timeout"
class BoundedTransport(Protocol):
    """Unbuffered transport whose operations honor the supplied timeout."""
    def read(self, size: int, timeout_seconds: float) -> bytes: ...
    def write(self, data: bytes, timeout_seconds: float) -> int: ...
class ProtocolError(ValueError):
    """A deterministic error that never includes protocol input."""
    def __init__(self, code: ProtocolErrorCode) -> None:
        self.code = ProtocolErrorCode(code)
        super().__init__(self.code.value)
def _reject_constant(_: str) -> None:
    raise ProtocolError(ProtocolErrorCode.INVALID_JSON)
def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(ProtocolErrorCode.DUPLICATE_KEY)
        result[key] = value
    return result
def _canonical(message: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ProtocolError(ProtocolErrorCode.INVALID_JSON) from None
def _nonce(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_NONCE:
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    return value
def _validate(message: object) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    if not isinstance(message.get("type"), str) or not isinstance(message.get("nonce"), str):
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    kind, nonce = message["type"], _nonce(message["nonce"])
    allowed = {
        "contained": {"type", "nonce"}, "ready": {"type", "nonce"}, "go": {"type", "nonce"},
        "result": {"type", "nonce", "provider", "state", "display_label", "error"},
        "error": {"type", "nonce", "code"},
    }.get(kind)
    if allowed is None:
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    if set(message) - allowed:
        raise ProtocolError(ProtocolErrorCode.UNKNOWN_FIELD)
    required = {"type", "nonce"} | ({"provider", "state"} if kind == "result" else {"code"} if kind == "error" else set())
    if not required <= set(message):
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    result = dict(message)
    if kind == "result":
        try:
            provider = ProviderKey(result["provider"])
            state = ProviderState(result["state"])
        except (TypeError, ValueError):
            raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE) from None
        label = result.get("display_label")
        if label is not None and (not isinstance(label, str) or not label or len(label) > 64 or any(ord(c) < 32 for c in label)):
            raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
        raw_error = result.get("error")
        if state is ProviderState.SAFE_ERROR and raw_error is None:
            raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
        if state is not ProviderState.SAFE_ERROR and raw_error is not None:
            raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
        if raw_error is not None:
            if not isinstance(raw_error, Mapping) or set(raw_error) != {"code"}:
                raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
            try:
                SafeErrorCode(raw_error["code"])
            except (TypeError, ValueError):
                raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE) from None
    elif kind == "error":
        try:
            SafeErrorCode(result["code"])
        except (TypeError, ValueError):
            raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE) from None
    return result
def _limit_for(message: Mapping[str, Any]) -> int:
    return RESPONSE_MAX_BYTES if message["type"] in {"result", "error"} else CONTROL_MAX_BYTES
def encode_frame(message: Mapping[str, Any]) -> bytes:
    validated = _validate(message)
    payload = _canonical(validated)
    if len(payload) > _limit_for(validated):
        raise ProtocolError(ProtocolErrorCode.OVERSIZE)
    return struct.pack(">I", len(payload)) + payload
def _decode_payload(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ProtocolError(ProtocolErrorCode.INVALID_UTF8) from None
    try:
        message = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except ProtocolError:
        raise
    except (TypeError, ValueError):
        raise ProtocolError(ProtocolErrorCode.INVALID_JSON) from None
    validated = _validate(message)
    if _canonical(validated) != payload:
        raise ProtocolError(ProtocolErrorCode.INVALID_JSON)
    if len(payload) > _limit_for(validated):
        raise ProtocolError(ProtocolErrorCode.OVERSIZE)
    return validated
def decode_frame(data: bytes, *, limit: int | None = None) -> dict[str, Any]:
    if not isinstance(data, bytes) or len(data) < 4:
        raise ProtocolError(ProtocolErrorCode.EOF)
    length = struct.unpack(">I", data[:4])[0]
    maximum = RESPONSE_MAX_BYTES if limit is None else limit
    if length > maximum:
        raise ProtocolError(ProtocolErrorCode.OVERSIZE)
    if len(data) < length + 4:
        raise ProtocolError(ProtocolErrorCode.EOF)
    if len(data) > length + 4:
        raise ProtocolError(ProtocolErrorCode.TRAILING_BYTES)
    return _decode_payload(data[4:])
def _deadline(value: object) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ProtocolError(ProtocolErrorCode.INVALID_TIMEOUT) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise ProtocolError(ProtocolErrorCode.INVALID_TIMEOUT)
    return time.monotonic() + timeout
def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProtocolError(ProtocolErrorCode.TRANSPORT_TIMEOUT)
    return remaining
def _transport_call(transport: BoundedTransport, method: str, value: Any, deadline: float) -> Any:
    remaining = _remaining(deadline)
    try:
        return getattr(transport, method)(value, remaining)
    except TimeoutError:
        raise ProtocolError(ProtocolErrorCode.TRANSPORT_TIMEOUT) from None
    except Exception:
        raise ProtocolError(ProtocolErrorCode.TRANSPORT_FAILURE) from None
def _read_exact(transport: BoundedTransport, length: int, deadline: float) -> bytes:
    result = bytearray()
    while len(result) < length:
        chunk = _transport_call(transport, "read", length - len(result), deadline)
        if not isinstance(chunk, bytes) or not chunk:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_EOF)
        result.extend(chunk)
    return bytes(result)
def read_frame(transport: BoundedTransport, timeout_seconds: float, *, limit: int | None = None) -> dict[str, Any]:
    deadline = _deadline(timeout_seconds)
    header = _read_exact(transport, 4, deadline)
    length = struct.unpack(">I", header)[0]
    maximum = RESPONSE_MAX_BYTES if limit is None else limit
    if length > maximum:
        raise ProtocolError(ProtocolErrorCode.OVERSIZE)
    return decode_frame(header + _read_exact(transport, length, deadline), limit=maximum)
def write_frame(transport: BoundedTransport, message: Mapping[str, Any], timeout_seconds: float) -> None:
    deadline = _deadline(timeout_seconds)
    frame = encode_frame(message)
    offset = 0
    while offset < len(frame):
        written = _transport_call(transport, "write", frame[offset:], deadline)
        if not isinstance(written, int) or written <= 0:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_FAILURE)
        offset += written


def _context_parts(context):
    try:
        return context.deadline_ns, context.clock_ns
    except AttributeError:
        raise ProtocolError(ProtocolErrorCode.INVALID_TIMEOUT) from None


def _remaining_context(context, deadline_ns, clock_ns) -> float:
    remaining = deadline_ns - clock_ns()
    if remaining <= 0:
        raise ProtocolError(ProtocolErrorCode.TRANSPORT_TIMEOUT)
    return remaining / 1_000_000_000


def _read_exact_context(transport: BoundedTransport, length: int, context) -> bytes:
    deadline_ns, clock_ns = _context_parts(context)
    result = bytearray()
    while len(result) < length:
        remaining = _remaining_context(context, deadline_ns, clock_ns)
        try:
            chunk = transport.read(length - len(result), remaining)
        except TimeoutError:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_TIMEOUT) from None
        except Exception:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_FAILURE) from None
        if not isinstance(chunk, bytes) or not chunk:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_EOF)
        result.extend(chunk)
    return bytes(result)


def read_frame_with_deadline(transport: BoundedTransport, context, *, limit: int | None = None) -> dict[str, Any]:
    header = _read_exact_context(transport, 4, context)
    length = struct.unpack(">I", header)[0]
    maximum = RESPONSE_MAX_BYTES if limit is None else limit
    if length > maximum:
        raise ProtocolError(ProtocolErrorCode.OVERSIZE)
    return decode_frame(header + _read_exact_context(transport, length, context), limit=maximum)


def write_frame_with_deadline(transport: BoundedTransport, message: Mapping[str, Any], context) -> None:
    deadline_ns, clock_ns = _context_parts(context)
    frame = encode_frame(message)
    offset = 0
    while offset < len(frame):
        remaining = _remaining_context(context, deadline_ns, clock_ns)
        try:
            written = transport.write(frame[offset:], remaining)
        except TimeoutError:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_TIMEOUT) from None
        except Exception:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_FAILURE) from None
        if not isinstance(written, int) or written <= 0:
            raise ProtocolError(ProtocolErrorCode.TRANSPORT_FAILURE)
        offset += written
def _state(kind: str, nonce: str) -> dict[str, str]:
    _nonce(nonce)
    return {"type": kind, "nonce": nonce}
def contained_message(nonce: str) -> dict[str, str]: return _state("contained", nonce)
def ready_message(nonce: str) -> dict[str, str]: return _state("ready", nonce)
def go_message(nonce: str) -> dict[str, str]: return _state("go", nonce)
def result_message(nonce: str, view: ProviderView) -> dict[str, Any]:
    if not isinstance(view, ProviderView):
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    message: dict[str, Any] = {"type": "result", "nonce": _nonce(nonce), "provider": view.provider.value, "state": view.state.value}
    if view.display_label is not None:
        message["display_label"] = view.display_label
    if view.error is not None:
        message["error"] = {"code": view.error.code.value}
    return _validate(message)
def error_message(nonce: str, code: SafeErrorCode) -> dict[str, str]:
    try:
        safe_code = SafeErrorCode(code).value
    except (TypeError, ValueError):
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE) from None
    return {"type": "error", "nonce": _nonce(nonce), "code": safe_code}
def message_view(message: Mapping[str, Any]) -> ProviderView:
    validated = _validate(message)
    if validated["type"] != "result":
        raise ProtocolError(ProtocolErrorCode.INVALID_MESSAGE)
    error = validated.get("error")
    return ProviderView(validated["provider"], validated["state"], SafeError(error["code"]) if error is not None else None, validated.get("display_label"))
class ProtocolSession:
    """Enforces contained → ready → go → result/error for one nonce."""
    def __init__(self, nonce: str) -> None:
        self.nonce = _nonce(nonce)
        self._state = "start"
    def accept(self, message: Mapping[str, Any]) -> dict[str, Any]:
        validated = _validate(message)
        if validated["nonce"] != self.nonce:
            raise ProtocolError(ProtocolErrorCode.NONCE_MISMATCH)
        expected = {"start": {"contained"}, "contained": {"ready"}, "ready": {"go"}, "go": {"result", "error"}}
        if validated["type"] not in expected.get(self._state, set()):
            raise ProtocolError(ProtocolErrorCode.INVALID_TRANSITION)
        self._state = validated["type"] if validated["type"] in {"contained", "ready", "go"} else "terminal"
        return validated
