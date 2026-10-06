"""HKCU PATH surgery and literal-state cleanup for the private setup assist.

Owned-user-PATH transaction surface: record, append, remove.
Literal-state cleanup: native handle-bound delete with registry ownership proof.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

REG_SZ, REG_EXPAND_SZ = 1, 2


@dataclass(frozen=True)
class Outcome:
    changed: bool
    reason: str | None = None


class UserPathRegistry(Protocol):
    def read_user_path(self) -> tuple[str, int] | None: ...
    def write_user_path(self, value: str, value_type: int) -> None: ...
    def compare_and_write_user_path(self, expected: tuple[str, int] | None, value: str, value_type: int) -> bool: ...
    def read_recorded_element(self) -> str | None: ...
    def write_recorded_element(self, element: str) -> None: ...
    def clear_recorded_element(self) -> None: ...
    def notify_environment_changed(self) -> None: ...


class WindowsUserPathRegistry:
    """HKCU-only adapter; it never opens or writes System PATH."""

    _ENVIRONMENT = r"Environment"
    _BOOKKEEPING = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1"
    _RECORD = "yasb-limitora-path-element"

    @staticmethod
    def _winreg():
        import winreg
        return winreg

    def _read(self, path: str, name: str) -> tuple[object, int] | None:
        registry = self._winreg()
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, path) as key:
                return registry.QueryValueEx(key, name)
        except FileNotFoundError:
            return None

    def _write(self, path: str, name: str, value: str, value_type: int) -> None:
        registry = self._winreg()
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, path, 0, registry.KEY_SET_VALUE) as key:
            registry.SetValueEx(key, name, 0, value_type, value)

    def read_user_path(self) -> tuple[str, int] | None:
        value = self._read(self._ENVIRONMENT, "Path")
        return (str(value[0]), value[1]) if value is not None and isinstance(value[0], str) else None

    def write_user_path(self, value: str, value_type: int) -> None:
        self._write(self._ENVIRONMENT, "Path", value, value_type)

    def compare_and_write_user_path(self, expected, value: str, value_type: int) -> bool:
        if self.read_user_path() != expected:
            return False
        self.write_user_path(value, value_type)
        return True

    def read_recorded_element(self) -> str | None:
        value = self._read(self._BOOKKEEPING, self._RECORD)
        return value[0] if value is not None and isinstance(value[0], str) else None

    def write_recorded_element(self, element: str) -> None:
        self._write(self._BOOKKEEPING, self._RECORD, element, self._winreg().REG_SZ)

    def clear_recorded_element(self) -> None:
        registry = self._winreg()
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, self._BOOKKEEPING, 0, registry.KEY_SET_VALUE) as key:
                registry.DeleteValue(key, self._RECORD)
        except FileNotFoundError:
            return

    def notify_environment_changed(self) -> None:
        ctypes = __import__("ctypes")
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0, 1000, None)


def _safe_path(value: object) -> tuple[str, int] | None:
    return value if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str) and value[1] in {REG_SZ, REG_EXPAND_SZ} else None


def _record(element: str, value: str, value_type: int) -> str:
    return json.dumps({"element": element, "path": value, "type": value_type}, sort_keys=True, separators=(",", ":"))


def _owned(recorded: str) -> tuple[str, str, int] | None:
    try:
        data = json.loads(recorded)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or set(data) != {"element", "path", "type"}:
        return None
    if (
        not isinstance(data["element"], str)
        or not data["element"]
        or not isinstance(data["path"], str)
        or type(data["type"]) is not int
        or data["type"] not in {REG_SZ, REG_EXPAND_SZ}
    ):
        return None
    return data["element"], data["path"], data["type"]


def append_user_path(
    registry: UserPathRegistry,
    element: str,
    *,
    correction_consent: bool = False,
) -> Outcome:
    """Add the selected route; replacing an owned old route requires separate consent."""
    for _attempt in range(2):
        current = registry.read_user_path()
        safe = _safe_path(current)
        if safe is None and current is not None:
            return Outcome(False, "path-value-unsafe")
        value, value_type = safe or ("", REG_EXPAND_SZ)
        if element in value.split(";"):
            return Outcome(False)

        recorded = registry.read_recorded_element()
        owned = _owned(recorded or "")
        if recorded is not None and owned is None:
            return Outcome(False, "path-record-invalid")
        if owned is not None:
            old_element, expected_value, expected_type = owned
            parts = value.split(";")
            if current != (expected_value, expected_type) or not parts or parts[-1] != old_element:
                return Outcome(False, "path-ownership-changed")
            if not correction_consent:
                return Outcome(False, "path-correction-consent-required")
            value = ";".join(parts[:-1])
        changed = value + ";" + element
        if not registry.compare_and_write_user_path(current, changed, value_type):
            continue
        try:
            registry.write_recorded_element(_record(element, changed, value_type))
        except OSError:
            if not registry.compare_and_write_user_path((changed, value_type), current[0] if current else "", value_type):
                return Outcome(False, "path-bookkeeping-rollback-failed")
            return Outcome(False, "path-bookkeeping-failed")
        registry.notify_environment_changed()
        return Outcome(True)
    return Outcome(False, "path-concurrency-unsafe")


def remove_recorded_user_path(registry: UserPathRegistry) -> Outcome:
    """Remove only a still-owned append; absent/unowned routes are successful no-ops."""
    owned = _owned(registry.read_recorded_element() or "")
    if owned is None:
        return Outcome(False)
    element, expected_value, expected_type = owned
    current = registry.read_user_path()
    if current is None:
        return Outcome(False)
    if current != (expected_value, expected_type):
        if element not in current[0].split(";"):
            return Outcome(False)
        return Outcome(False, "path-ownership-changed")
    parts = expected_value.split(";")
    if not parts or parts[-1] != element:
        return Outcome(False, "path-ownership-changed")
    changed = ";".join(parts[:-1])
    if not registry.compare_and_write_user_path(current, changed, expected_type):
        return Outcome(False, "path-concurrency-unsafe")
    try:
        registry.clear_recorded_element()
    except OSError:
        if not registry.compare_and_write_user_path((changed, expected_type), expected_value, expected_type):
            return Outcome(False, "path-bookkeeping-rollback-failed")
        return Outcome(False, "path-bookkeeping-failed")
    registry.notify_environment_changed()
    return Outcome(True)


def _remove_path_and_cleanup_state(registry: UserPathRegistry, state_dir: str) -> tuple[Outcome, Outcome]:
    """Compose the exact uninstall batch without consuming its shared ownership record early."""
    from . import _native_state_cleanup

    if not os.path.isabs(state_dir):
        refusal = Outcome(False, "state-path-unsafe")
        return Outcome(False, "path-transaction-aborted"), refusal
    recorded = registry.read_recorded_element()
    owned = _owned(recorded or "")
    if owned is None:
        return Outcome(False), Outcome(False, "state-record-missing")
    element, expected_value, expected_type = owned
    parts = expected_value.split(";")
    if not parts or parts[-1] != element:
        refusal = Outcome(False, "path-ownership-changed")
        return refusal, Outcome(False, "path-remove-failed")
    current = registry.read_user_path()
    if current != (expected_value, expected_type):
        route_present = current is not None and element in current[0].split(";")
        if not route_present:
            # PATH removal is a no-op; state cleanup separately rejects the stale snapshot.
            state_result = cleanup_literal_state(
                registry,
                state_dir,
                expected_record=recorded,
            )
            return Outcome(False), state_result
        refusal = Outcome(False, "path-ownership-changed")
        return refusal, Outcome(False, "path-remove-failed")
    changed = ";".join(parts[:-1])
    if not registry.compare_and_write_user_path(current, changed, expected_type):
        refusal = Outcome(False, "path-concurrency-unsafe")
        return refusal, Outcome(False, "path-remove-failed")
    registry.notify_environment_changed()

    # The record and the post-CAS PATH are both live proofs; neither cached proof may
    # authorize native deletion after a concurrent replacement.
    if registry.read_recorded_element() != recorded or registry.read_user_path() != (changed, expected_type):
        return Outcome(True), Outcome(False, "path-ownership-changed")
    try:
        deleted = _native_state_cleanup.delete_directory(state_dir)
    except OSError:
        deleted = False
    if not deleted:
        try:
            restored = registry.compare_and_write_user_path(
                (changed, expected_type), expected_value, expected_type
            )
        except OSError:
            restored = False
        if restored:
            registry.notify_environment_changed()
            refusal = Outcome(False, "state-delete-failed")
            return refusal, refusal
        return Outcome(True), Outcome(False, "path-restore-failed")
    try:
        registry.clear_recorded_element()
    except OSError:
        return Outcome(True), Outcome(False, "state-bookkeeping-failed")
    return Outcome(True), Outcome(True)


def cleanup_literal_state(
    registry: UserPathRegistry,
    state_dir: str,
    *,
    expected_record: str | None = None,
) -> Outcome:
    """Delete state with a live PATH record, without changing PATH."""
    from . import _native_state_cleanup

    if not os.path.isabs(state_dir):
        return Outcome(False, "state-path-unsafe")
    recorded = registry.read_recorded_element()
    if expected_record is not None and recorded != expected_record:
        return Outcome(False, "path-ownership-changed")
    owned = _owned(recorded or "")
    if owned is None:
        return Outcome(False, "state-record-missing")
    element, expected_value, expected_type = owned
    parts = expected_value.split(";")
    if not parts or parts[-1] != element:
        return Outcome(False, "path-ownership-changed")
    expected_path = (expected_value, expected_type)
    current = registry.read_user_path()
    if current != expected_path:
        return Outcome(False, "path-ownership-changed")
    if registry.read_recorded_element() != recorded or registry.read_user_path() != expected_path:
        return Outcome(False, "path-ownership-changed")
    try:
        deleted = _native_state_cleanup.delete_directory(state_dir)
    except OSError:
        deleted = False
    if not deleted:
        return Outcome(False, "state-delete-failed")
    try:
        registry.clear_recorded_element()
    except OSError:
        return Outcome(False, "state-bookkeeping-failed")
    return Outcome(True)
