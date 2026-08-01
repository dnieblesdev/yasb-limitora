"""Contained Codex worker; provider code runs only after supervisor READY."""

import json
import os
import struct
import sys
import threading
from collections.abc import Callable, Sequence

from .codex_supervisor import (
    _CodexSupervisor,
    _PipeTransport,
    _TransportError,
    _TransportTimeout,
)
from .model import ProviderKey, ProviderState, ProviderView, SafeError, SafeErrorCode

_MAX_REQUEST = 4096
_MAX_RESPONSE = 64 * 1024
_GATE = "_YASB_CODEX_GATE_HANDLE"
_DATA = "_YASB_CODEX_DATA_HANDLE"
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


def _payload(view: ProviderView) -> bytes:
    item = {"state": view.state.value}
    if view.state is ProviderState.SAFE_ERROR:
        item["error"] = {"code": view.error.code.value}  # type: ignore[union-attr]
    return json.dumps(item, separators=(",", ":")).encode("ascii")


def _child_main() -> None:
    gate, data = int(os.environ.pop(_GATE)), int(os.environ.pop(_DATA))
    try:
        size = struct.unpack(">I", _read_exact(gate, 4))[0]
        if not 0 < size <= _MAX_REQUEST:
            raise ValueError
        request = json.loads(_read_exact(gate, size).decode("utf-8"))
        if not isinstance(request, dict) or set(request) != {"runner", "nonce"}:
            raise ValueError
        if request["nonce"] != os.environ.pop("_YASB_HELPER_NONCE"):
            raise ValueError
        runner = request["runner"]
        if not isinstance(runner, list) or not all(isinstance(item, str) for item in runner):
            raise ValueError
        from .limitora_api import read_codex

        view = read_codex(runner)
        payload = _payload(view)
    except Exception:  # noqa: BLE001 - contain all worker failures
        payload = _payload(ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.INTERNAL_ERROR)))
    _write_all(data, struct.pack(">I", len(payload)) + payload)
    os.close(gate)
    os.close(data)


class _PersistentTransport(_PipeTransport):
    """The READY frame is a prefix; worker responses are length framed."""

    def read_frame(self, *, expected_size: int, timeout_seconds=2.0, max_size=4096, reject_trailing=True) -> bytes:
        if type(expected_size) is not int or not 0 < expected_size <= max_size:
            raise _TransportError("invalid_frame_size")
        deadline = self._deadline(timeout_seconds)
        result = bytearray()
        while len(result) < expected_size:
            available, eof = self._peek(self._read_fd)
            if eof:
                raise _TransportError("eof")
            if available:
                result.extend(self._read(self._read_fd, min(available, expected_size - len(result))))
            else:
                self._backoff(deadline)
        if reject_trailing and self._peek(self._read_fd)[0]:
            raise _TransportError("trailing_data")
        return bytes(result)

    def read_response(self, timeout_seconds=2.0) -> bytes:
        header = self.read_frame(expected_size=4, timeout_seconds=timeout_seconds, reject_trailing=False)
        size = struct.unpack(">I", header)[0]
        if not 0 < size <= _MAX_RESPONSE:
            raise _TransportError("response_oversize")
        payload = self.read_frame(expected_size=size, timeout_seconds=timeout_seconds, max_size=_MAX_RESPONSE, reject_trailing=False)
        deadline = self._deadline(timeout_seconds)
        while True:
            available, eof = self._peek(self._read_fd)
            if available:
                raise _TransportError("trailing_data")
            if eof:
                return payload
            self._backoff(deadline)


class CodexHelperExecutor:
    """Own one supervisor and dispatch only after its READY authorization."""

    def __init__(self, supervisor_factory: Callable[..., object] = _CodexSupervisor, timeout_seconds: float = 2.0) -> None:
        self._factory, self._timeout, self._pending_supervisor = supervisor_factory, timeout_seconds, None
        self._lifecycle, self._active, self._retrying = threading.Lock(), False, False

    def run(self, runner: Sequence[str]) -> ProviderView:
        if isinstance(runner, (str, bytes)) or not isinstance(runner, Sequence) or not all(isinstance(item, str) for item in runner):
            return _error(SafeErrorCode.INVOCATION_INVALID)
        if len(json.dumps({"nonce": "x" * 128, "runner": list(runner)}).encode("utf-8")) > _MAX_REQUEST:
            return _error(SafeErrorCode.INVOCATION_INVALID)
        with self._lifecycle:
            if self._pending_supervisor is not None or self._active or self._retrying:
                return _error(SafeErrorCode.INTERNAL_ERROR)
            self._active = True
        transport_box: list[_PersistentTransport] = []

        def transport_factory(read_fd, write_fd, *, nonblocking):
            transport = _PersistentTransport(read_fd, write_fd, nonblocking=nonblocking)
            transport_box.append(transport)
            return transport

        supervisor, result = None, ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.INTERNAL_ERROR))
        try:
            supervisor = self._factory(
                command=(sys.executable, "-I", "-E", "-c", _CHILD_BOOTSTRAP),
                transport_factory=transport_factory,
                timeout_seconds=self._timeout,
            )
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
    return ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(code))


def _decode(payload: bytes) -> ProviderView:
    try:
        value = json.loads(payload.decode("ascii"))
        if not isinstance(value, dict) or set(value) not in ({"state"}, {"state", "error"}):
            raise ValueError
        state = ProviderState(value["state"])
        if state is not ProviderState.SAFE_ERROR and set(value) != {"state"}:
            raise ValueError
        error = SafeError(value["error"]["code"]) if state is ProviderState.SAFE_ERROR else None
        return ProviderView(ProviderKey.CODEX, state, error)
    except Exception:  # noqa: BLE001 - malformed worker output is safe_error
        return _error(SafeErrorCode.INTERNAL_ERROR)


if __name__ == "__main__":
    _child_main()


__all__ = ("CodexHelperExecutor",)
