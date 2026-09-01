"""Bounded, sanitized shared JSON quota cache."""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import re
import stat
import tempfile
import time
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Protocol, cast
from unicodedata import normalize

from .config import LocalConfig
from .deadline import DeadlineContext
from .guard import Guard, GuardError
from .model import (
    ProviderKey,
    ProviderSnapshotView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SnapshotFreshness,
)
from .path import DeadlineError, FileError, canonicalize_path, path_identity
from .projection import _presentation as _project_presentation
from .projection import _window_sort_key

CACHE_SCHEMA = 3
CACHE_TTL_SECONDS = 180
MAX_CACHE_BYTES = 131_072
MAX_CACHE_DOCUMENT_BYTES = 65_536
MAX_CACHE_FINGERPRINT_LENGTH = 64
CACHE_FILENAME = "quota-v2-cache.json"
REFRESH_MARKER_SUFFIX = ".refresh.json"
_PROCESS_MISSING = object()
MAX_REFRESH_MARKER_BYTES = 4_096
_REFRESH_WAIT_QUANTUM_NS = 10_000_000
_REFRESH_WAIT_QUANTUM_SECONDS = _REFRESH_WAIT_QUANTUM_NS / 1_000_000_000
_CACHE_TEMP_PREFIX = ".quota-v2-"
_CACHE_TEMP_SUFFIX = ".tmp"
_CACHE_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
_DECIMAL = re.compile(r"^(?:0|[1-9]\d*(?:\.\d+)?)$")
_PROVIDER_FIELDS = (
    "provider",
    "outcome",
    "public_state",
    "freshness",
    "status_observed_at",
    "fetched_at",
    "data_at",
    "source_id",
    "windows",
    "execution_error",
    "not_run_reason",
    "most_depleted_window",
    "compact_text",
    "alternate_text",
    "tooltip_text",
)
_WINDOW_FIELDS = (
    "kind",
    "scope",
    "period",
    "plan_id",
    "availability",
    "source_id",
    "limit",
    "used",
    "remaining",
    "reset_at",
)
_QUANTITY_FIELDS = ("value", "metric", "unit")
_DEPLETED_FIELDS = ("kind", "scope", "period", "plan_id", "unit", "source_id", "remaining_percentage")
_ERROR_FIELDS = ("code", "phase")
_PRESENTATION_FIELDS = ("most_depleted_window", "compact_text", "alternate_text", "tooltip_text")
_UNSAFE_KEY = re.compile(r"auth.?cookie|cookie|token|password|secret|credential|api.?key|authorization|traceback|stderr|workspace|runner", re.I)
_UNSAFE_VALUE = re.compile(
    r"auth.?cookie|cookie|password|secret|credential|api.?key|authorization|traceback|stderr|workspace|"
    r"(?:^/|^\\|^[A-Za-z]:[\\/])",
    re.I,
)

class CacheValidationError(ValueError):
    """Raised internally when a cache entry is not safe to consume."""


class _GuardLease(Protocol):
    def release(self) -> bool: ...

    def close(self) -> bool: ...


class _KeyGuard(Protocol):
    def acquire_key(self, key: bytes, context: DeadlineContext) -> _GuardLease: ...


class OwnerState(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RefreshClaim:
    """The opaque authority for one cache-key refresh attempt."""

    generation: int
    owner_pid: int
    owner_token: str


@dataclass(frozen=True, slots=True)
class SingleFlightResult:
    """Result of a bounded cache lookup or refresh attempt."""

    value: object | None = None
    cached_public_bytes: bytes | None = None
    deadline_exhausted: bool = False
    produced: bool = False
    coordination_failed: bool = False
    coordination_error: str | None = None


@dataclass(slots=True)
class RefreshState:
    """One inspected cache-key state and its short-lived coordination lease."""

    cached_public_bytes: bytes | None = None
    marker: dict[str, object] | None = None
    owner_state: OwnerState | None = None
    lease: _GuardLease | None = None
    coordination_error: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshDecision:
    """The next action after inspecting one cache-key state."""

    claim: RefreshClaim | None = None
    wait: bool = False
    result: SingleFlightResult | None = None


def _validate_windows_path_identity(path: str) -> None:
    """Reject reparse-point components before cache reads or replacement writes."""
    if os.name != "nt":
        return
    current = os.path.abspath(path)
    for _ in range(128):
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            pass
        except OSError:
            raise FileError("cache identity unavailable") from None
        else:
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise FileError("cache identity unavailable")
        parent = os.path.dirname(current)
        if parent == current:
            return
        current = parent
    raise FileError("cache identity unavailable")


def _validate_windows_owner(path: str) -> None:
    """Require a usable SID and ACL-backed access to an existing cache object."""
    if os.name != "nt":
        return
    try:
        from .guard import _default_sid_bytes, _valid_sid_bytes

        expected = _default_sid_bytes()
        if not _valid_sid_bytes(expected):
            raise OSError
        if not os.access(path, os.R_OK):
            raise OSError
    except Exception:
        raise FileError("cache identity unavailable") from None


def _validate_cache_directory(directory: str) -> None:
    _validate_windows_path_identity(directory)
    if os.path.isdir(directory):
        _validate_windows_owner(directory)


def _validate_cache_target(path: str) -> None:
    _validate_windows_path_identity(path)
    if os.path.exists(path):
        _validate_windows_owner(path)


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _public_document_json(document: Mapping[str, object]) -> bytes:
    root = {key: document[key] for key in ("execution_state", "execution_error", "providers")}
    return (json.dumps(root, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _cache_envelope_json(envelope: Mapping[str, object]) -> bytes:
    root = {key: envelope[key] for key in ("schema", "cached_at", "fingerprint", "document")}
    return (json.dumps(root, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CacheValidationError("duplicate cache key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise CacheValidationError("non-finite cache number")


def _safe_mapping(value: object, fields: set[str] | tuple[str, ...]) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(fields):
        raise CacheValidationError("invalid cache object")
    if isinstance(fields, tuple) and tuple(value) != fields:
        raise CacheValidationError("noncanonical cache order")
    if any(not isinstance(key, str) or _UNSAFE_KEY.search(key) for key in value):
        raise CacheValidationError("unsafe cache key")
    return value


def _safe_text(value: object, maximum: int, *, multiline: bool = False) -> str:
    if type(value) is not str or len(value) > maximum:
        raise CacheValidationError("invalid cache text")
    if any((ord(char) < 32 and (not multiline or char != "\n")) or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise CacheValidationError("unsafe cache text")
    if normalize("NFC", value) != value:
        raise CacheValidationError("noncanonical cache text")
    if _UNSAFE_VALUE.search(value):
        raise CacheValidationError("unsafe cache text")
    return value


def _required_text(value: object) -> str:
    if type(value) is not str:
        raise CacheValidationError("invalid cache text")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _required_text(value)


def _timestamp(value: object) -> str:
    if type(value) is not str or not _CACHE_TIME.fullmatch(value):
        raise CacheValidationError("invalid cache timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise CacheValidationError("invalid cache timestamp") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise CacheValidationError("noncanonical cache timestamp")
    return value


def _quantity(value: object, expected_metric: str | None) -> QuotaQuantity:
    quantity = _safe_mapping(value, _QUANTITY_FIELDS)
    unit = _safe_text(quantity["unit"], 64)
    rendered = quantity["value"]

    if type(rendered) is not str or not _DECIMAL.fullmatch(rendered) or len(rendered) > 256:
        raise CacheValidationError("invalid cache quantity")
    try:
        metric = QuotaMetricKind(quantity["metric"])
        parsed = QuotaQuantity(Decimal(rendered), metric, unit)
    except (ArithmeticError, TypeError, ValueError):
        raise CacheValidationError("invalid cache quantity") from None
    if format(parsed.value, "f") != rendered or parsed.metric.value != quantity["metric"] or parsed.unit != quantity["unit"]:
        raise CacheValidationError("noncanonical cache quantity")
    if expected_metric is not None and parsed.metric.value != expected_metric:
        raise CacheValidationError("invalid cache metric")
    return parsed


def _window(value: object, provider: str) -> QuotaWindowView:
    window = _safe_mapping(value, _WINDOW_FIELDS)
    try:
        kind = QuotaWindowKind(window["kind"])
        availability = QuotaAvailability(window["availability"])
    except ValueError:
        raise CacheValidationError("invalid cache window vocabulary") from None
    scope = _safe_text(window["scope"], 64)
    period = _safe_text(window["period"], 64)
    plan_id = _optional_text(window["plan_id"])
    if plan_id is not None:
        _safe_text(plan_id, 64)
    source_id = _optional_text(window["source_id"])
    expected_source = "codex-app-server-v2" if provider == "codex" else "opencode-go-api"
    if source_id not in (None, expected_source):
        raise CacheValidationError("invalid cache source")
    expected_metric = None if kind is QuotaWindowKind.OTHER else kind.value
    quantities = (window["limit"], window["used"], window["remaining"])
    parsed_quantities = tuple(
        None if quantity is None else _quantity(quantity, expected_metric)
        for quantity in quantities
    )
    if availability is not QuotaAvailability.KNOWN and any(quantity is not None for quantity in quantities):
        raise CacheValidationError("non-known cache window has values")
    if availability is not QuotaAvailability.KNOWN and window["reset_at"] is not None:
        raise CacheValidationError("non-known cache window has reset")
    if availability is QuotaAvailability.KNOWN and not any(quantity is not None for quantity in quantities):
        raise CacheValidationError("known cache window has no quantity")
    if source_id is None and (
        availability is not QuotaAvailability.UNAVAILABLE
        or any(quantity is not None for quantity in quantities)
        or window["reset_at"] is not None
    ):
        raise CacheValidationError("untrusted cache window has values")
    try:
        reset_at = None if window["reset_at"] is None else datetime.strptime(
            _timestamp(window["reset_at"]), "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(tzinfo=timezone.utc)
        return QuotaWindowView(
            kind,
            scope,
            period,
            plan_id,
            availability,
            source_id,
            parsed_quantities[0],
            parsed_quantities[1],
            parsed_quantities[2],
            reset_at,
        )
    except (TypeError, ValueError):
        raise CacheValidationError("invalid cache window semantics") from None


def _parsed_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _presentation_candidate(
    root: dict[str, object],
    providers: list[tuple[dict[str, object], list[dict[str, object]]]],
    tooltip_limit: int,
) -> tuple[list[dict[str, object]], int]:
    expected_items: list[dict[str, object]] = []
    for item, windows in providers:
        outcome = _required_text(item["outcome"])
        public_state = _optional_text(item["public_state"])
        freshness = _optional_text(item["freshness"])
        not_run_reason = _optional_text(item["not_run_reason"])
        expected_items.append(
            _project_presentation(
                ProviderKey(_required_text(item["provider"])),
                outcome,
                windows,
                public_state,
                freshness,
                not_run_reason,
                tooltip_limit,
            )
        )
    canonical_providers = []
    for (item, _windows), expected in zip(providers, expected_items):
        canonical_item = dict(item)
        canonical_item.update(expected)
        canonical_providers.append(canonical_item)
    canonical_document = {
        "execution_state": root["execution_state"],
        "execution_error": root["execution_error"],
        "providers": canonical_providers,
    }
    return expected_items, len(_public_document_json(canonical_document))


def _presentation_matches(
    root: dict[str, object],
    providers: list[tuple[dict[str, object], list[dict[str, object]]]],
) -> None:
    low, high = 0, 4_096
    best: tuple[list[dict[str, object]], int] | None = None
    while low <= high:
        tooltip_limit = (low + high) // 2
        try:
            expected, size = _presentation_candidate(root, providers, tooltip_limit)
        except (KeyError, TypeError, ValueError):
            raise CacheValidationError("inconsistent cache presentation") from None
        if size <= MAX_CACHE_DOCUMENT_BYTES:
            best = (expected, tooltip_limit)
            low = tooltip_limit + 1
        else:
            high = tooltip_limit - 1
    if best is None:
        raise CacheValidationError("cache document exceeds presentation budget")
    expected_items, _tooltip_limit = best
    for (item, _windows), expected in zip(providers, expected_items):
        if any(item[field] != expected[field] for field in _PRESENTATION_FIELDS):
            raise CacheValidationError("inconsistent cache presentation")


def _validate_document(document: object) -> dict[str, object]:
    root = _safe_mapping(document, ("execution_state", "execution_error", "providers"))
    if root["execution_state"] not in {"complete", "partial", "not_run", "execution_error"}:
        raise CacheValidationError("invalid cache document")
    providers = root["providers"]
    if type(providers) is not list or len(providers) != 2:
        raise CacheValidationError("invalid cache providers")
    outcomes: list[str] = []
    usable = False
    provider_keys: list[str] = []
    presentation_inputs: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    for provider in providers:
        item = _safe_mapping(provider, _PROVIDER_FIELDS)
        key = _required_text(item["provider"])
        if key not in {"codex", "opencode_go"} or key in provider_keys:
            raise CacheValidationError("invalid cache provider order")
        provider_keys.append(key)
        outcome = _required_text(item["outcome"])
        if outcome not in {"snapshot", "undetected", "not_run", "execution_error"}:
            raise CacheValidationError("invalid cache provider outcome")
        outcomes.append(outcome)
        for field in ("public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id"):
            _optional_text(item[field])
        source_id = _optional_text(item["source_id"])
        expected_source = "codex-app-server-v2" if key == "codex" else "opencode-go-api"
        if source_id not in (None, expected_source):
            raise CacheValidationError("inconsistent cache provider source")

        windows: list[dict[str, object]]
        if outcome == "snapshot":
            public_state_value = _optional_text(item["public_state"])
            freshness_value = _optional_text(item["freshness"])
            if public_state_value is None or freshness_value is None:
                raise CacheValidationError("invalid cache snapshot metadata")
            try:
                public_state = PublicProviderState(public_state_value)
                freshness = SnapshotFreshness(freshness_value)
            except ValueError:
                raise CacheValidationError("invalid cache snapshot metadata") from None
            timestamps = tuple(_parsed_timestamp(_timestamp(item[field])) for field in ("status_observed_at", "fetched_at", "data_at"))
            raw_windows = item["windows"]
            if type(raw_windows) is not list or len(raw_windows) > 32:
                raise CacheValidationError("invalid cache windows")
            windows = []
            model_windows: list[QuotaWindowView] = []
            identities: set[tuple[str, str, str]] = set()
            for raw_window in raw_windows:
                window = _safe_mapping(raw_window, _WINDOW_FIELDS)
                model_window = _window(window, key)
                window_kind = _required_text(window["kind"])
                window_scope = _safe_text(window["scope"], 64)
                window_period = _safe_text(window["period"], 64)
                windows.append(window)
                identity = (window_kind, window_scope, window_period)
                if identity in identities:
                    raise CacheValidationError("duplicate cache window")
                identities.add(identity)
                model_windows.append(model_window)
            if windows != sorted(windows, key=_window_sort_key):
                raise CacheValidationError("unordered cache windows")
            if key == "opencode_go" and public_state in (PublicProviderState.AVAILABLE, PublicProviderState.PARTIAL):
                commercial_periods = [
                    _safe_text(window["period"], 64)
                    for window in windows
                    if _required_text(window["kind"]) == QuotaWindowKind.COMMERCIAL_QUOTA.value
                ]
                if sorted(commercial_periods) != ["five_hour", "monthly", "weekly"]:
                    raise CacheValidationError("invalid OpenCode commercial slots")
            try:
                ProviderSnapshotView(
                    public_state,
                    freshness,
                    timestamps[0],
                    timestamps[1],
                    timestamps[2],
                    source_id,
                    tuple(model_windows),
                )
            except (TypeError, ValueError):
                raise CacheValidationError("invalid cache snapshot semantics") from None
            if item["execution_error"] is not None or item["not_run_reason"] is not None:
                raise CacheValidationError("invalid cache snapshot markers")
            usable = True
        elif outcome == "undetected":
            if any(item[field] is not None for field in ("public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id")) or item["windows"] != [] or item["execution_error"] is not None or item["not_run_reason"] is not None:
                raise CacheValidationError("invalid cache undetected")
            windows = []
            usable = True
        elif outcome == "not_run":
            if any(item[field] is not None for field in ("public_state", "freshness", "status_observed_at", "fetched_at", "data_at", "source_id")) or item["windows"] != [] or item["execution_error"] is not None or item["not_run_reason"] not in {"disabled", "invalid_configuration", "invocation_invalid", "document_aborted", "deadline_exhausted", "guard_wait_timeout"}:
                raise CacheValidationError("invalid cache not-run")
            windows = []
        else:
            raise CacheValidationError("provider errors are not cacheable")
        for field, maximum, multiline in (("compact_text", 128, False), ("alternate_text", 128, False), ("tooltip_text", 4_096, True)):
            _safe_text(item[field], maximum, multiline=multiline)
        if item["most_depleted_window"] is not None:
            _safe_mapping(item["most_depleted_window"], _DEPLETED_FIELDS)
        presentation_inputs.append((item, windows))
    if provider_keys != ["codex", "opencode_go"] or not usable:
        raise CacheValidationError("cache has no usable provider")
    _presentation_matches(root, presentation_inputs)
    execution_error = root["execution_error"]
    if execution_error is None:
        if root["execution_state"] == "execution_error":
            raise CacheValidationError("missing cache document error")
    else:
        error = _safe_mapping(execution_error, _ERROR_FIELDS)
        if error != {"code": "cleanup_failed", "phase": "cleanup"} or root["execution_state"] != "execution_error":
            raise CacheValidationError("invalid cache document error")
    if root["execution_state"] == "complete" and (any(outcome not in {"snapshot", "undetected"} for outcome in outcomes) or execution_error is not None):
        raise CacheValidationError("invalid complete cache")
    if root["execution_state"] == "not_run" and any(outcome != "not_run" for outcome in outcomes):
        raise CacheValidationError("invalid not-run cache")
    if root["execution_state"] == "partial" and (not any(outcome in {"snapshot", "undetected"} for outcome in outcomes) or not any(outcome in {"not_run", "execution_error"} for outcome in outcomes) or execution_error is not None):
        raise CacheValidationError("invalid partial cache")
    return root


def _cache_read_child(path: str) -> bytes:
    descriptor = None
    try:
        _validate_cache_directory(os.path.dirname(path) or ".")
        _validate_cache_target(path)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CACHE_BYTES:
            raise OSError
        data = os.read(descriptor, MAX_CACHE_BYTES + 1)
        if len(data) > MAX_CACHE_BYTES:
            raise OSError
        return data
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _cache_write_child(path: str, data: bytes) -> None:
    directory = os.path.dirname(path) or "."
    descriptor = None
    temporary = None
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        if not stat.S_ISDIR(os.stat(directory).st_mode):
            raise OSError
        _validate_cache_directory(directory)
        _validate_cache_target(path)
        descriptor, temporary = tempfile.mkstemp(prefix=_CACHE_TEMP_PREFIX, suffix=_CACHE_TEMP_SUFFIX, dir=directory)
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise OSError
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        temporary = None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def _process_creation_token(pid: int) -> str | object | None:
    """Return a non-reusable process identity without persisting process data."""
    if type(pid) is not int or pid <= 0:
        return None
    if os.name != "nt":
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii") as source:
                fields = source.read().split()
            return fields[21] if len(fields) > 21 else None
        except FileNotFoundError:
            return _PROCESS_MISSING
        except (OSError, IndexError, ValueError):
            return None
    handle = None
    kernel32 = None
    close_handle: Callable[[object], object] | None = None
    try:
        import ctypes

        class _FileTime(ctypes.Structure):
            _fields_ = (("low", ctypes.c_uint32), ("high", ctypes.c_uint32))

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
        ]
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int

        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            try:
                error_code = ctypes.get_last_error()
            except Exception:
                return None
            return _PROCESS_MISSING if error_code == 87 else None
        created, exited, kernel, user = (_FileTime() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        value = (created.high << 32) | created.low
        return f"{value:x}"
    except Exception:
        return None
    finally:
        if handle and close_handle is not None:
            try:
                close_handle(handle)
            except Exception:
                pass


def _owner_token() -> str | None:
    token = _process_creation_token(os.getpid())
    return token if isinstance(token, str) else None


def _marker_document(marker: object) -> dict[str, object]:
    if type(marker) is not dict or set(marker) != {"generation", "owner_pid", "owner_token", "started_at"}:
        raise CacheValidationError("invalid refresh marker")
    value = marker
    if type(value["generation"]) is not int or value["generation"] <= 0:
        raise CacheValidationError("invalid refresh generation")
    if type(value["owner_pid"]) is not int or value["owner_pid"] < 0:
        raise CacheValidationError("invalid refresh owner")
    if type(value["owner_token"]) is not str or len(value["owner_token"]) > 128:
        raise CacheValidationError("invalid refresh token")
    _timestamp(value["started_at"])
    if value["owner_pid"] == 0 and value["owner_token"] != "":
        raise CacheValidationError("invalid inactive refresh marker")
    if value["owner_pid"] > 0 and not value["owner_token"]:
        raise CacheValidationError("invalid active refresh marker")
    return value


def _refresh_marker_read_child(path: str) -> bytes | None:
    try:
        data = _cache_read_child(path)
    except FileNotFoundError:
        return None
    if len(data) > MAX_REFRESH_MARKER_BYTES:
        raise OSError
    return data


def _refresh_marker_write_child(path: str, data: bytes) -> None:
    if len(data) > MAX_REFRESH_MARKER_BYTES:
        raise OSError
    _cache_write_child(path, data)


# Leave room for zlib's small worst-case framing overhead while keeping the
# child response bounded independently of its compressed expansion ratio.
_MAX_CACHE_TRANSPORT_BYTES = MAX_CACHE_BYTES + (MAX_CACHE_BYTES // 1_000) + 64


def _cache_read_transport(path: str) -> bytes:
    """Compress bounded cache reads before sending them across child IPC."""
    return zlib.compress(_cache_read_child(path), level=1)


def _decompress_cache_transport(value: object) -> bytes:
    """Bound child-controlled decompression and require one complete stream."""
    if not isinstance(value, bytes) or len(value) > _MAX_CACHE_TRANSPORT_BYTES:
        raise FileError("cache I/O failed")
    decompressor = zlib.decompressobj()
    try:
        data = decompressor.decompress(value, MAX_CACHE_BYTES + 1)
    except zlib.error:
        raise FileError("cache I/O failed") from None
    if (
        len(data) > MAX_CACHE_BYTES
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise FileError("cache I/O failed")
    return data


def _bounded_call(function, args: tuple[object, ...], context: DeadlineContext) -> object:
    """Run potentially blocking cache filesystem work in a bounded child."""
    if context.usable_ns() <= 0:
        raise DeadlineError("cache deadline exhausted")
    try:
        from .path import _bounded_file_call

        transport = _cache_read_transport if function is _cache_read_child else function
        value = _bounded_file_call(transport, args, context)
        if transport is _cache_read_transport:
            return _decompress_cache_transport(value)
        return value
    except (DeadlineError, FileError):
        raise
    except Exception:
        raise FileError("cache I/O failed") from None


def cache_path(
    config_path: object,
    environment: Mapping[str, str] | None = None,
    fingerprint: str | None = None,
) -> str:
    """Return a path-scoped cache file inside the default local Limitora directory."""
    source = os.fspath(config_path) if isinstance(config_path, os.PathLike) else config_path
    path_digest = hashlib.sha256(path_identity(source).encode("utf-8")).hexdigest()
    if fingerprint is not None and (
        type(fingerprint) is not str or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    ):
        raise ValueError("invalid cache fingerprint")
    identity = path_digest if fingerprint is None else fingerprint
    filename = f"{CACHE_FILENAME[:-5]}-{identity}.json"
    if environment is not None:
        directory = _cache_directory(environment)
        result = canonicalize_path(
            os.path.join(directory, filename)
            if os.name != "nt" and directory.startswith("/")
            else ntpath.join(directory, filename)
        )
        return result
    canonical = canonicalize_path(source)
    directory = ntpath.dirname(canonical) if ntpath.splitdrive(canonical)[0] or canonical.startswith("\\") else os.path.dirname(canonical)
    if not directory:
        raise ValueError("invalid cache directory")
    result = canonicalize_path(os.path.join(directory, filename) if os.name != "nt" and canonical.startswith("/") else ntpath.join(directory, filename))
    return result


def _cache_directory(environment: Mapping[str, str]) -> str:
    localappdata = environment.get("LOCALAPPDATA", "")
    if not isinstance(localappdata, str) or not localappdata.strip():
        raise FileError("missing cache directory")
    if os.name != "nt" and localappdata.startswith("/"):
        directory = os.path.join(localappdata, "yasb-limitora")
    else:
        directory = ntpath.join(localappdata, "yasb-limitora")
    return canonicalize_path(directory)


def _account_digest(environment: Mapping[str, str]) -> str:
    if os.name == "nt":
        try:
            from .guard import _default_sid_bytes, _valid_sid_bytes

            sid = _default_sid_bytes()
        except Exception:
            raise FileError("account identity unavailable") from None
        if (
            not _valid_sid_bytes(sid)
        ):
            raise FileError("account identity unavailable")
    else:
        sid = b""
    values = []
    for key in ("USERNAME", "USER", "USERDOMAIN", "LIMITORA_OPENCODE_API_KEY"):
        value = environment.get(key, "")
        values.append(value if isinstance(value, str) else "")
    return hashlib.sha256(sid + b"\0" + "\0".join(values).encode("utf-8", "surrogatepass")).hexdigest()


def config_fingerprint(config: LocalConfig, environment: Mapping[str, str], config_path: object) -> str:
    """Create a non-reversible identity for one effective provider context."""
    source = os.fspath(config_path) if isinstance(config_path, os.PathLike) else config_path
    canonical = path_identity(source)
    cache_directory = path_identity(_cache_directory(environment))
    payload = {
        "account": _account_digest(environment),
        "cache_directory": cache_directory,
        "path": canonical,
        "codex": {
            "enabled": config.codex.enabled,
            "runner": config.codex.runner,
            "timeout_seconds": format(config.codex.timeout_seconds, ".17g"),
        },
        "opencode_go": {
            "enabled": config.opencode_go.enabled,
            "timeout_seconds": format(config.opencode_go.timeout_seconds, ".17g"),
        },
        "deadline_seconds": format(config.deadline_seconds, ".17g"),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


class RefreshCoordinator:
    """Coordinate one cache key and authorize publication for its generation."""

    def __init__(
        self,
        config: LocalConfig,
        environment: Mapping[str, str],
        config_path: object,
        *,
        now=None,
        guard_factory=Guard,
        sleep=time.sleep,
        process_token=_process_creation_token,
    ) -> None:
        self.fingerprint = config_fingerprint(config, environment, config_path)
        self.path = cache_path(config_path, environment, self.fingerprint)
        self.marker_path = self.path + REFRESH_MARKER_SUFFIX
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._guard_factory = guard_factory
        self._sleep = sleep
        self._process_token = process_token

    def load(self, context: DeadlineContext) -> bytes | None:
        return self._load_unlocked(context)

    def _load_unlocked(self, context: DeadlineContext) -> bytes | None:
        try:
            raw = _bounded_call(_cache_read_child, (self.path,), context)
            if not isinstance(raw, bytes) or len(raw) > MAX_CACHE_BYTES:
                return None
            envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
            if raw != _cache_envelope_json(envelope):
                return None

            value = _safe_mapping(envelope, {"schema", "cached_at", "fingerprint", "document"})
            if value["schema"] != CACHE_SCHEMA or value["fingerprint"] != self.fingerprint or type(value["fingerprint"]) is not str or len(value["fingerprint"]) != MAX_CACHE_FINGERPRINT_LENGTH:
                return None
            cached_at = _timestamp(value["cached_at"])
            cached = datetime.strptime(cached_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            now = self._now()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                return None
            age = (now.astimezone(timezone.utc) - cached).total_seconds()
            if age < 0 or age > CACHE_TTL_SECONDS:
                return None
            document = _validate_document(value["document"])
            encoded = _public_document_json(document)
            if len(encoded) > MAX_CACHE_DOCUMENT_BYTES:
                return None
            return encoded
        except (CacheValidationError, UnicodeError, ValueError, TypeError, OSError, FileError, DeadlineError, json.JSONDecodeError):
            return None
        except Exception:
            return None

    def publish(self, document_bytes: bytes, context: DeadlineContext) -> bool:
        return self._publish_unlocked(document_bytes, context)

    def _read_marker_state(self, context: DeadlineContext) -> tuple[dict[str, object] | None, bool]:
        try:
            raw = _bounded_call(_refresh_marker_read_child, (self.marker_path,), context)
            if raw is None:
                return None, True
            if not isinstance(raw, bytes) or raw != _canonical_json(json.loads(
                raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
            )):
                return None, False
            return _marker_document(json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)), True
        except (CacheValidationError, UnicodeError, ValueError, TypeError, OSError, FileError, DeadlineError, json.JSONDecodeError):
            return None, False
        except Exception:
            return None, False

    def _read_marker(self, context: DeadlineContext) -> dict[str, object] | None:
        marker, readable = self._read_marker_state(context)
        return marker if readable else None

    def _write_marker(self, marker: dict[str, object], context: DeadlineContext) -> bool:
        try:
            data = _canonical_json(_marker_document(marker))
            _bounded_call(_refresh_marker_write_child, (self.marker_path, data), context)
            return True
        except Exception:
            return False

    @staticmethod
    def _same_claim(marker: Mapping[str, object] | None, claim: RefreshClaim) -> bool:
        return bool(
            marker is not None
            and marker.get("generation") == claim.generation
            and marker.get("owner_pid") == claim.owner_pid
            and marker.get("owner_token") == claim.owner_token
        )

    def _owner_state(self, marker: Mapping[str, object]) -> OwnerState:
        try:
            pid = marker["owner_pid"]
            token = marker["owner_token"]
            if type(pid) is not int or pid <= 0 or not isinstance(token, str) or not token:
                return OwnerState.UNKNOWN
            current = self._process_token(pid)
            if current is None:
                return OwnerState.UNKNOWN
            if current is _PROCESS_MISSING:
                return OwnerState.DEAD
            if not isinstance(current, str) or not current:
                return OwnerState.UNKNOWN
            return OwnerState.ALIVE if current == token else OwnerState.DEAD
        except Exception:
            return OwnerState.UNKNOWN

    def _owner_is_live(self, marker: Mapping[str, object]) -> bool:
        return self._owner_state(marker) is OwnerState.ALIVE

    def _coordination_lease(self, context: DeadlineContext) -> _GuardLease:
        guard: _KeyGuard = self._guard_factory()
        return guard.acquire_key(self.fingerprint.encode("ascii"), context)

    @staticmethod
    def _close_lease(lease: _GuardLease) -> bool:
        def marked(name: str) -> bool:
            try:
                value = getattr(lease, name)
                return type(value) is bool and value
            except Exception:
                return False

        def observed(name: str, value: bool) -> bool:
            try:
                return getattr(lease, name) is value
            except Exception:
                return False

        def mark(name: str) -> None:
            try:
                setattr(lease, name, True)
            except Exception:
                return

        finalized = marked("_yasb_finalized")
        released = finalized or marked("_yasb_release_complete") or observed("owned", False)
        closed = finalized or marked("_yasb_close_complete") or observed("closed", True)
        if not released:
            try:
                released = bool(lease.release())
            except Exception:
                released = False
            released = released or observed("owned", False)
        if released:
            mark("_yasb_release_complete")
        if released and not closed:
            try:
                closed = bool(lease.close())
            except Exception:
                closed = False
            closed = closed or observed("closed", True)
        if closed:
            mark("_yasb_close_complete")
        finalized = released and closed
        if finalized:
            mark("_yasb_finalized")
        return finalized

    def _retain_lease(self, lease: object) -> None:
        if hasattr(lease, "owned") and hasattr(lease, "closed"):
            self._pending_lease = lease

    @staticmethod
    def _coordination_result(code: str) -> SingleFlightResult:
        return SingleFlightResult(
            deadline_exhausted=code == "deadline_exhausted",
            coordination_failed=True,
            coordination_error=code,
        )

    def _recover_pending_claim(self, context: DeadlineContext) -> bool:
        claim = getattr(self, "_pending_claim", None)
        if claim is None:
            return True
        lease = None
        recovered = False
        try:
            lease = self._coordination_lease(context)
            marker, readable = self._read_marker_state(context)
            if readable and self._same_claim(marker, claim):
                recovered = self._write_marker(self._inactive_marker(claim.generation), context)
            else:
                recovered = readable
        except Exception:
            recovered = False
        finally:
            if lease is not None and not self._close_lease(lease):
                self._retain_lease(lease)
                recovered = False
        if recovered:
            self._pending_claim = None
        return recovered

    def _inactive_marker(self, generation: int) -> dict[str, object]:
        now = self._now()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            now = datetime.now(timezone.utc)
        return {
            "generation": generation,
            "owner_pid": 0,
            "owner_token": "",
            "started_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

    def _claim_locked(self, marker: Mapping[str, object] | None, context: DeadlineContext) -> RefreshClaim | None:
        generation = marker.get("generation", 0) if marker is not None else 0
        if type(generation) is not int or generation < 0:
            generation = 0
        token = self._process_token(os.getpid())
        if not isinstance(token, str) or not token:
            return None
        claim = RefreshClaim(generation + 1, os.getpid(), token)
        now = self._now()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return None
        active = {
            "generation": claim.generation,
            "owner_pid": claim.owner_pid,
            "owner_token": claim.owner_token,
            "started_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        return claim if self._write_marker(active, context) else None

    def inspect_state(self, context: DeadlineContext) -> RefreshState:
        """Read the cache and marker once while holding the key lease."""
        state = RefreshState()
        pending = getattr(self, "_pending_lease", None)
        if pending is not None:
            if not self._close_lease(pending):
                state.coordination_error = "internal_error"
                return state
            self._pending_lease = None
        if getattr(self, "_pending_claim", None) is not None and not self._recover_pending_claim(context):
            state.coordination_error = "internal_error"
            return state
        try:
            state.lease = self._coordination_lease(context)
            state.cached_public_bytes = self._load_unlocked(context)
            if state.cached_public_bytes is None:
                state.marker, readable = self._read_marker_state(context)
                if not readable:
                    state.coordination_error = "deadline_exhausted" if context.usable_ns() <= 0 else "internal_error"
                elif state.marker is not None:
                    owner_pid = state.marker.get("owner_pid", 0)
                    if type(owner_pid) is not int:
                        raise TypeError("invalid refresh owner")
                    if owner_pid > 0:
                        state.owner_state = self._owner_state(state.marker)
        except GuardError as error:
            state.coordination_error = error.code if error.code in {"guard_wait_timeout", "guard_acquisition_failed"} else "internal_error"
            if not self._release_inspection(state):
                state.coordination_error = "internal_error"
        except Exception:
            state.coordination_error = "deadline_exhausted" if context.usable_ns() <= 0 else "internal_error"
            if not self._release_inspection(state):
                state.coordination_error = "internal_error"
        return state

    def claim_or_wait(self, state: RefreshState, context: DeadlineContext) -> RefreshDecision:
        """Turn inspected state into a cache hit, bounded wait, or refresh claim."""
        if state.coordination_error is not None:
            self._release_inspection(state)
            return RefreshDecision(result=self._coordination_result(state.coordination_error))
        if state.cached_public_bytes is not None:
            if not self._release_inspection(state):
                return RefreshDecision(result=self._coordination_result("internal_error"))
            return RefreshDecision(result=SingleFlightResult(cached_public_bytes=state.cached_public_bytes))
        if state.owner_state is OwnerState.ALIVE:
            if not self._release_inspection(state):
                return RefreshDecision(result=self._coordination_result("internal_error"))
            return RefreshDecision(wait=True)
        if state.owner_state is OwnerState.UNKNOWN:
            if not self._release_inspection(state):
                return RefreshDecision(result=self._coordination_result("internal_error"))
            return RefreshDecision(result=self._coordination_result("deadline_exhausted" if context.usable_ns() <= 0 else "internal_error"))
        try:
            claim = self._claim_locked(state.marker, context)
            coordination_error = None if claim is not None else ("deadline_exhausted" if context.usable_ns() <= 0 else "internal_error")
        except GuardError as error:
            claim = None
            coordination_error = error.code if error.code in {"guard_wait_timeout", "guard_acquisition_failed"} else "internal_error"
        except Exception:
            claim = None
            coordination_error = "deadline_exhausted" if context.usable_ns() <= 0 else "internal_error"
        if not self._release_inspection(state, claim=claim):
            coordination_error = "internal_error"
        if coordination_error is not None:
            return RefreshDecision(result=self._coordination_result(coordination_error))
        return RefreshDecision(claim=claim)

    def _release_inspection(self, state: RefreshState, *, claim: RefreshClaim | None = None) -> bool:
        lease = state.lease
        state.lease = None
        if lease is None:
            return True
        if self._close_lease(lease):
            return True
        self._retain_lease(lease)
        if claim is not None:
            self._pending_claim = claim
        return False

    def cleanup_attempt(self, claim: RefreshClaim, context: DeadlineContext) -> None:
        """Release marker authority when an attempt exits before publication."""
        self.publish_if_authoritative(claim, None, context)

    def publish_if_authoritative(self, claim: RefreshClaim, document_bytes: bytes | None, context: DeadlineContext) -> bool:
        """Publish only while the claimed generation still owns the marker."""
        return self._finish_claim(claim, document_bytes, context)

    def get_or_refresh(self, context: DeadlineContext, producer) -> SingleFlightResult:
        """Inspect, claim or wait, run one attempt, clean it up, then publish."""
        if getattr(self, "_pending_claim", None) is None:
            pending = getattr(self, "_pending_lease", None)
            if pending is not None:
                if not self._close_lease(pending):
                    return self._coordination_result("internal_error")
                self._pending_lease = None
            cached_public_bytes = self.load(context)
            if cached_public_bytes is not None:
                return SingleFlightResult(cached_public_bytes=cached_public_bytes)
        initial_usable_ns = context.usable_ns()
        if initial_usable_ns <= 0:
            return SingleFlightResult(deadline_exhausted=True)
        max_wait_attempts = max(
            1,
            (initial_usable_ns + _REFRESH_WAIT_QUANTUM_NS - 1) // _REFRESH_WAIT_QUANTUM_NS,
        )
        for _ in range(max_wait_attempts):
            if context.usable_ns() <= 0:
                return SingleFlightResult(deadline_exhausted=True)
            state = self.inspect_state(context)
            decision = self.claim_or_wait(state, context)
            if decision.result is not None:
                if decision.result.coordination_error == "guard_wait_timeout":
                    cached_public_bytes = self.load(context)
                    if cached_public_bytes is not None:
                        return SingleFlightResult(cached_public_bytes=cached_public_bytes)
                return decision.result
            if decision.wait:
                if context.usable_ns() <= 0:
                    return SingleFlightResult(deadline_exhausted=True)
                self._sleep(min(_REFRESH_WAIT_QUANTUM_SECONDS, context.usable_ns() / 1_000_000_000))
                continue
            if decision.claim is None:
                return self._coordination_result("deadline_exhausted" if context.usable_ns() <= 0 else "internal_error")
            claim = decision.claim
            try:
                result = producer(context)
                if not isinstance(result, SingleFlightResult):
                    result = SingleFlightResult(value=result, produced=True)
            except BaseException:
                self.cleanup_attempt(claim, context)
                raise
            published = self.publish_if_authoritative(claim, result.cached_public_bytes, context)
            return result if published else SingleFlightResult(
                value=result.value,
                cached_public_bytes=None,
                deadline_exhausted=result.deadline_exhausted,
                produced=result.produced,
                coordination_failed=result.coordination_failed,
                coordination_error=result.coordination_error,
            )
        return self._coordination_result("deadline_exhausted" if context.usable_ns() <= 0 else "internal_error")

    def single_flight(self, context: DeadlineContext, producer) -> SingleFlightResult:
        """Compatibility name for the cache lifecycle API."""
        return self.get_or_refresh(context, producer)

    def _finish_claim(self, claim: RefreshClaim, document_bytes: bytes | None, context: DeadlineContext) -> bool:
        lease = None
        published = False
        try:
            lease = self._coordination_lease(context)
            marker, readable = self._read_marker_state(context)
            if readable and self._same_claim(marker, claim):
                if document_bytes is not None:
                    published = self._publish_unlocked(document_bytes, context)
                if not self._write_marker(self._inactive_marker(claim.generation), context):
                    self._pending_claim = claim
                    published = False
            else:
                published = False
        except Exception:
            self._pending_claim = claim
            published = False
        finally:
            if lease is not None and not self._close_lease(lease):
                self._retain_lease(lease)
                published = False
        return published

    def _publish_unlocked(self, document_bytes: bytes, context: DeadlineContext) -> bool:
        try:
            if not isinstance(document_bytes, bytes) or len(document_bytes) > MAX_CACHE_DOCUMENT_BYTES:
                return False
            document = json.loads(document_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
            if not document_bytes.endswith(b"\n"):
                return False
            document = _validate_document(document)
            if document["execution_error"] is not None:
                return False
            if any(
                cast(str, provider["outcome"]) == "not_run"
                and cast(str, provider["not_run_reason"]) in {"deadline_exhausted", "guard_wait_timeout"}
                for provider in cast(list[dict[str, object]], document["providers"])
            ):
                return False
            canonical_document = _public_document_json(document)
            if document_bytes != canonical_document or len(canonical_document) > MAX_CACHE_DOCUMENT_BYTES:
                return False

            now = self._now()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                return False
            cached_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            envelope = _cache_envelope_json({"schema": CACHE_SCHEMA, "cached_at": cached_at, "fingerprint": self.fingerprint, "document": document})
            if len(envelope) > MAX_CACHE_BYTES:
                return False
            try:
                _bounded_call(_cache_write_child, (self.path, envelope), context)
            except Exception:
                return False
            return True
        except (CacheValidationError, UnicodeError, ValueError, TypeError, OSError, FileError, DeadlineError, json.JSONDecodeError):
            return False
        except Exception:
            return False


__all__ = (
    "CACHE_FILENAME",
    "CACHE_SCHEMA",
    "CACHE_TTL_SECONDS",
    "MAX_CACHE_BYTES",
    "RefreshClaim",
    "RefreshCoordinator",
    "RefreshDecision",
    "RefreshState",
    "SingleFlightResult",
    "cache_path",
    "config_fingerprint",
)
