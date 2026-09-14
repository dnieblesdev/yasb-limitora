"""D01a1/a2a — Guard domain, deadline, and marker codec.

Context-managed Guard lease keyed by the exact fixed config.json path,
retrying under one 5-second DeadlineContext; bounded release/close cleanup.
Canonical UTF-8 JSON marker with sorted keys, no whitespace, and strict
schema validation (D01a2a).  Win32 process identity is a separate sub-unit.
"""
from __future__ import annotations

import json
import ntpath
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .deadline import DeadlineContext
from .guard import Guard, GuardError, GuardLease

_CONFIG_DEADLINE_SECONDS = 5.0
_RELEASE_RETRIES = 3

_MARKER_KEYS = frozenset({"pid", "token", "version"})
_MARKER_VERSION = 1
_MARKER_MAX_BYTES = 256
_TOKEN_MAX_HEX = 64
_MARKER_ERROR = "marker-validation"


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


class MarkerValidationError(ValueError):
    """Marker failed validation — one stable public code, no cause leakage."""

    def __init__(self) -> None:
        super().__init__(_MARKER_ERROR)


def encode_marker(pid: int, token: str) -> bytes:
    """Encode canonical UTF-8 JSON marker (sorted keys, no whitespace)."""
    if not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 4294967295:
        raise MarkerValidationError()
    if not isinstance(token, str) or not token or len(token) > _TOKEN_MAX_HEX:
        raise MarkerValidationError()
    if not all(c in "0123456789abcdef" for c in token):
        raise MarkerValidationError()
    return json.dumps(
        {"pid": pid, "token": token, "version": _MARKER_VERSION},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def decode_marker(data: bytes) -> tuple[int, str, int]:
    """Decode canonical marker, rejecting invalid and noncanonical inputs."""
    if not data or len(data) > _MARKER_MAX_BYTES:
        raise MarkerValidationError()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise MarkerValidationError() from None
    # Reject noncanonical whitespace before parsing
    if any(c in text for c in " \t\n\r"):
        raise MarkerValidationError()

    def _check_dup_and_order(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise MarkerValidationError()
        if keys != sorted(keys):
            raise MarkerValidationError()
        return dict(pairs)

    try:
        obj = json.loads(text, object_pairs_hook=_check_dup_and_order)
    except json.JSONDecodeError:
        raise MarkerValidationError() from None
    if not isinstance(obj, dict):
        raise MarkerValidationError()
    if set(obj.keys()) != _MARKER_KEYS:
        raise MarkerValidationError()
    pid, token, version = obj["pid"], obj["token"], obj["version"]
    if not isinstance(pid, int) or isinstance(pid, bool) or not 1 <= pid <= 4294967295:
        raise MarkerValidationError()
    if not isinstance(token, str) or not token or len(token) > _TOKEN_MAX_HEX:
        raise MarkerValidationError()
    if not all(c in "0123456789abcdef" for c in token):
        raise MarkerValidationError()
    if not isinstance(version, int) or isinstance(version, bool) or version != _MARKER_VERSION:
        raise MarkerValidationError()
    # Roundtrip check: reject escaped/noncanonical byte spellings
    if data != encode_marker(pid, token):
        raise MarkerValidationError()
    return pid, token, version
