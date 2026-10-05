"""S07-A PATH transaction contracts: record, ownership, append, remove — fakes only."""

from __future__ import annotations

import json

import pytest  # pyright: ignore[reportMissingImports]

cleanup = __import__("yasb_limitora._path_cleanup", fromlist=["_path_cleanup"])

NONCE = "0123456789abcdef" * 2
V1 = "gentle-ai.yasb-limitora.setup-assist-request/v1"


class FakeRegistry:
    def __init__(self, value: str | None, value_type: int = cleanup.REG_EXPAND_SZ, recorded: str | None = None):
        self.value, self.value_type, self.recorded = value, value_type, recorded
        self.writes: list[tuple[str, int]] = []
        self.notifications = 0
        self.compare_failures = 0
        self.record_failure = False
        self.clear_failure = False

    def compare_and_write_user_path(self, expected, value, value_type):
        if self.compare_failures:
            self.compare_failures -= 1
            self.value = "EXTERNAL;" + (self.value or "")
            return False
        if self.read_user_path() != expected:
            return False
        self.write_user_path(value, value_type)
        return True

    def read_user_path(self):
        return None if self.value is None else (self.value, self.value_type)

    def write_user_path(self, value, value_type):
        self.value, self.value_type = value, value_type
        self.writes.append((value, value_type))

    def read_recorded_element(self):
        return self.recorded

    def write_recorded_element(self, element):
        if self.record_failure:
            raise OSError("bookkeeping failed")
        self.recorded = element

    def clear_recorded_element(self):
        if self.clear_failure:
            raise OSError("bookkeeping failed")
        self.recorded = None

    def notify_environment_changed(self):
        self.notifications += 1


def test_path_append_is_verbatim_hkcu_only_and_preserves_expand_type():
    registry = FakeRegistry(r"A;;%USERPROFILE%\bin;B", cleanup.REG_EXPAND_SZ)
    result = cleanup.append_user_path(registry, r"C:\Program Files\yasb-limitora")
    assert result.changed and registry.value == r"A;;%USERPROFILE%\bin;B;C:\Program Files\yasb-limitora"
    assert registry.value_type == cleanup.REG_EXPAND_SZ
    assert json.loads(registry.recorded or "{}")["element"] == r"C:\Program Files\yasb-limitora"
    assert registry.notifications == 1


@pytest.mark.parametrize("value_type", [cleanup.REG_SZ, cleanup.REG_EXPAND_SZ])
def test_path_duplicate_is_noop_and_removal_only_touches_exact_owned_element(value_type):
    registry = FakeRegistry(r"A;;%VAR%", value_type)
    assert cleanup.append_user_path(registry, r"C:\bin").changed
    assert cleanup.append_user_path(registry, r"C:\bin").reason == "path-element-present"
    assert cleanup.remove_recorded_user_path(registry).changed is True
    assert registry.value == r"A;;%VAR%" and registry.value_type == value_type
    assert registry.recorded is None and registry.notifications == 2


def test_missing_bookkeeping_never_mutates_or_notifies():
    registry = FakeRegistry(r"A;;%VAR%", cleanup.REG_SZ)
    assert cleanup.remove_recorded_user_path(registry).reason == "path-record-missing"
    assert registry.writes == [] and registry.notifications == 0


def test_path_append_retries_without_losing_external_change_and_preserves_type():
    registry = FakeRegistry("A", cleanup.REG_SZ)
    registry.compare_failures = 1
    assert cleanup.append_user_path(registry, r"C:\bin").changed
    assert registry.value == r"EXTERNAL;A;C:\bin" and registry.value_type == cleanup.REG_SZ


def test_path_bookkeeping_failure_rolls_back_without_notification():
    registry = FakeRegistry(r"A;;%VAR%", cleanup.REG_EXPAND_SZ)
    registry.record_failure = True
    result = cleanup.append_user_path(registry, r"C:\bin")
    assert result.reason == "path-bookkeeping-failed"
    assert registry.value == r"A;;%VAR%" and registry.value_type == cleanup.REG_EXPAND_SZ
    assert registry.recorded is None and registry.notifications == 0


def test_path_removal_bookkeeping_failure_restores_owned_path_without_notification():
    registry = FakeRegistry("A")
    assert cleanup.append_user_path(registry, r"C:\bin").changed
    registry.clear_failure = True
    result = cleanup.remove_recorded_user_path(registry)
    assert result.reason == "path-bookkeeping-failed"
    assert registry.value == r"A;C:\bin" and registry.recorded is not None
    assert registry.notifications == 1


def test_removal_refuses_external_identical_element_after_owned_append():
    registry = FakeRegistry("A")
    assert cleanup.append_user_path(registry, r"C:\bin").changed
    registry.value = (registry.value or "") + r";C:\bin"  # external edit after the product append
    assert cleanup.remove_recorded_user_path(registry).reason == "path-ownership-changed"
    assert registry.value == r"A;C:\bin;C:\bin" and registry.notifications == 1


def _batch_registry():
    registry = FakeRegistry("A")
    assert cleanup.append_user_path(registry, r"C:\bin").changed
    return registry


def test_batch_missing_record_refuses_before_path_or_native_cleanup(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = FakeRegistry("A")
    monkeypatch.setattr(nsc, "delete_directory", lambda _path: pytest.fail("native cleanup bypassed record gate"))
    path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

    assert path_result.reason == "path-record-missing"
    assert state_result.reason == "state-record-missing"
    assert registry.writes == [] and registry.notifications == 0


def test_batch_native_failure_restores_path_conditionally_and_keeps_record(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = _batch_registry()
    monkeypatch.setattr(nsc, "delete_directory", lambda _path: False)
    path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

    assert not path_result.changed and path_result.reason == "state-delete-failed"
    assert not state_result.changed and state_result.reason == "state-delete-failed"
    assert registry.value == r"A;C:\bin" and registry.recorded is not None
    assert registry.notifications == 3  # append, provisional remove, conditional restore


def test_batch_restore_failure_does_not_overwrite_external_path(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = _batch_registry()
    calls = 0
    compare = registry.compare_and_write_user_path

    def compare_with_external_restore(expected, value, value_type):
        nonlocal calls
        calls += 1
        if calls == 2:
            registry.value = "EXTERNAL"
            return False
        return compare(expected, value, value_type)

    registry.compare_and_write_user_path = compare_with_external_restore
    monkeypatch.setattr(nsc, "delete_directory", lambda _path: False)
    path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

    assert path_result.changed and state_result.reason == "path-restore-failed"
    assert registry.value == "EXTERNAL" and registry.recorded is not None
    assert registry.notifications == 2  # append and the only actual removal


def test_batch_revalidates_live_record_and_path_before_native_cleanup(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    class ReplacingRegistry(FakeRegistry):
        def __init__(self):
            super().__init__("A")
            self.replace_after_remove = False
            self.path_edit_after_remove = False

        def compare_and_write_user_path(self, expected, value, value_type):
            changed = super().compare_and_write_user_path(expected, value, value_type)
            if changed and self.replace_after_remove:
                self.recorded = cleanup._record(r"C:\other", "A;C:\other", value_type)
            if changed and self.path_edit_after_remove:
                self.value = value + ";EXTERNAL"
            return changed

    for replacement, path_edit in ((True, False), (False, True)):
        registry = ReplacingRegistry()
        assert cleanup.append_user_path(registry, r"C:\bin").changed
        registry.replace_after_remove = replacement
        registry.path_edit_after_remove = path_edit
        native_called = False

        def native_delete(_path):
            nonlocal native_called
            native_called = True
            return True

        monkeypatch.setattr(nsc, "delete_directory", native_delete)
        path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

        assert path_result.changed and state_result.reason == "path-ownership-changed"
        assert not native_called and registry.recorded is not None


def test_batch_cas_failure_refuses_without_native_cleanup(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = _batch_registry()
    registry.compare_failures = 1
    monkeypatch.setattr(nsc, "delete_directory", lambda _path: pytest.fail("native cleanup bypassed CAS"))
    path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

    assert path_result.reason == "path-concurrency-unsafe"
    assert state_result.reason == "path-remove-failed"
    assert registry.recorded is not None and registry.notifications == 1


def test_batch_clear_failure_reports_bookkeeping_without_restoring_deleted_state(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = _batch_registry()
    clear_calls = 0
    clear = registry.clear_recorded_element

    def clear_once():
        nonlocal clear_calls
        clear_calls += 1
        registry.clear_failure = True
        clear()

    registry.clear_recorded_element = clear_once
    monkeypatch.setattr(nsc, "delete_directory", lambda _path: True)
    path_result, state_result = cleanup._remove_path_and_cleanup_state(registry, r"C:\state")

    assert path_result.changed and state_result.reason == "state-bookkeeping-failed"
    assert clear_calls == 1 and registry.value == "A" and registry.recorded is not None
    assert registry.notifications == 2


# --- S07-B: literal-state cleanup through native delete with registry ownership proof ---


def test_cleanup_refuses_without_registry_record():
    registry = FakeRegistry("A")
    result = cleanup.cleanup_literal_state(registry, r"C:\state")
    assert result.reason == "state-record-missing" and not result.changed


def test_cleanup_refuses_non_absolute_state_path():
    registry = FakeRegistry("A")
    registry.write_recorded_element(cleanup._record(r"C:\bin", "A", cleanup.REG_SZ))
    result = cleanup.cleanup_literal_state(registry, "relative/path")
    assert result.reason == "state-path-unsafe" and not result.changed
    assert registry.recorded is not None  # record untouched


def test_cleanup_calls_native_delete_and_clears_record_on_success(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = FakeRegistry("A")
    registry.write_recorded_element(cleanup._record(r"C:\bin", "A", cleanup.REG_SZ))
    deleted: list[str] = []
    monkeypatch.setattr(nsc, "delete_directory", lambda p: (deleted.append(p), True)[1])
    result = cleanup.cleanup_literal_state(registry, r"C:\state")
    assert result.changed and deleted == [r"C:\state"] and registry.recorded is None


def test_cleanup_refuses_when_native_delete_fails(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = FakeRegistry("A")
    registry.write_recorded_element(cleanup._record(r"C:\bin", "A", cleanup.REG_SZ))
    monkeypatch.setattr(nsc, "delete_directory", lambda p: False)
    result = cleanup.cleanup_literal_state(registry, r"C:\state")
    assert result.reason == "state-delete-failed" and not result.changed
    assert registry.recorded is not None  # record preserved on failure


def test_cleanup_bookkeeping_failure_after_successful_delete(monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc

    registry = FakeRegistry("A")
    registry.write_recorded_element(cleanup._record(r"C:\bin", "A", cleanup.REG_SZ))
    registry.clear_failure = True
    monkeypatch.setattr(nsc, "delete_directory", lambda p: True)
    result = cleanup.cleanup_literal_state(registry, r"C:\state")
    assert result.reason == "state-bookkeeping-failed" and not result.changed
    assert registry.recorded is not None  # record preserved when clear fails
