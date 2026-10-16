"""Hermetic connecting-bootstrap evidence; no provider or native process."""
import builtins
import json
import os
import runpy
import sys
from types import SimpleNamespace

import pytest

from yasb_limitora import codex_helper as helper

TARGET = "yasb_limitora._native_proof_observability"

ROOTS = ("expected_worktree", "other_source", "site_packages", "stdlib", "frozen_bundle", "unknown")


def connect(monkeypatch, root, error, frozen=False, enabled=True):
    original = builtins.__import__
    def importing(name, *args, **kwargs):
        if name in (TARGET, "_native_proof_observability"):
            raise error
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", importing)
    monkeypatch.setattr(os, "read", lambda *_: b"1")
    writes, calls = [], []
    monkeypatch.setattr(os, "write", lambda fd, data: writes.append(data) or len(data))
    monkeypatch.setattr(os, "close", lambda *_: None)
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(open_osfhandle=lambda h, f: h))
    monkeypatch.setattr(runpy, "run_module", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(helper, "_child_main", lambda: calls.append("child"))
    for key, value in ((helper._GATE, "10"), (helper._DATA, "11"), (helper._READY_NONCE, "nonce")):
        monkeypatch.setenv(key, value)
    if enabled:
        monkeypatch.setenv("_YASB_NATIVE_PROOF_DIAGNOSTICS_ROOT", str(root))
    else:
        monkeypatch.delenv("_YASB_NATIVE_PROOF_DIAGNOSTICS_ROOT", raising=False)
    before = list(sys.path)
    inherited = {key: value for key, value in os.environ.items() if key not in (helper._GATE, helper._DATA, helper._READY_NONCE, "_YASB_HELPER_NONCE")}
    if frozen:
        helper._run_frozen_helper_bootstrap()
    else:
        exec(helper._CHILD_BOOTSTRAP, {})
    assert writes == [b"READY:nonce"]
    assert calls == (["child"] if frozen else [(("yasb_limitora.codex_helper",), {"run_name": "__main__"})])
    assert sys.path == before
    assert {key: value for key, value in os.environ.items() if key not in (helper._GATE, helper._DATA, helper._READY_NONCE, "_YASB_HELPER_NONCE")} == inherited
    assert os.environ[helper._GATE] == "10"
    assert os.environ[helper._DATA] == "11"
    assert os.environ["_YASB_HELPER_NONCE"] == "nonce"
    if not enabled:
        return []
    path = root / "helper.jsonl"
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("name,category", [(TARGET, "target"), ("yasb_limitora", "package"), ("SENSITIVE_dependency", "other_dependency"), (None, "unknown")])
def test_missing_categories_connect(monkeypatch, tmp_path, frozen, name, category):
    rows = connect(monkeypatch, tmp_path, ModuleNotFoundError("SENSITIVE_message", name=name), frozen)
    row = rows[-1]
    assert row["target_module"] == TARGET
    assert row["missing_category"] == category
    assert row["error_type"] == "ModuleNotFoundError"
    assert row["expected_repo_available"] is True
    assert row["expected_package_available"] is True
    assert row["expected_recorder_available"] is True
    assert row["package_origin"] == "expected_worktree"
    assert isinstance(row["expected_root_on_path"], bool)
    assert "SENSITIVE" not in json.dumps(rows)
    assert all(len(json.dumps(r, separators=(",", ":")).encode()) + 1 <= 512 for r in rows)


def test_metadata_failure_is_unknown(monkeypatch, tmp_path):
    stat = os.stat
    def failing(path, *a, **k):
        if "_native_proof_observability.py" in str(path):
            raise PermissionError("SENSITIVE_path")
        return stat(path, *a, **k)
    monkeypatch.setattr(os, "stat", failing)
    row = connect(monkeypatch, tmp_path, ImportError("SENSITIVE"))[-1]
    assert row["expected_recorder_available"] == "unknown"
    assert row["missing_category"] == "unknown"


@pytest.mark.parametrize("frozen", [False, True])
def test_off_has_no_observer_metadata(monkeypatch, tmp_path, frozen):
    monkeypatch.setattr(os.path, "isdir", lambda *_: pytest.fail("observer metadata while OFF"))
    monkeypatch.setattr(os, "stat", lambda *_a, **_k: pytest.fail("observer stat while OFF"))
    monkeypatch.setattr(builtins, "open", lambda *_a, **_k: pytest.fail("observer open while OFF"))
    assert connect(monkeypatch, tmp_path, ImportError(), frozen, enabled=False) == []


@pytest.mark.parametrize("frozen", [False, True])
def test_all_roots_capacity_and_namespace(monkeypatch, tmp_path, frozen):
    import time
    expected = os.path.dirname(os.path.dirname(helper.__file__))
    paths = [expected, str(tmp_path / "SENSITIVE"), os.path.join(sys.base_prefix, "Lib", "site-packages"), os.path.join(sys.base_prefix, "Lib"), "frozen", None]
    monkeypatch.setattr(sys, "path", paths + paths)
    monkeypatch.setitem(sys.modules, "yasb_limitora", SimpleNamespace(__spec__=SimpleNamespace(origin=None), __file__=None, __path__=paths))
    monkeypatch.setattr(time, "monotonic_ns", lambda: 9999999999999999999)
    for _ in range(80):
        rows = connect(monkeypatch, tmp_path, ModuleNotFoundError("SENSITIVE", name="SENSITIVE"), frozen)
    evidence = next(row for row in rows if row.get("state") == "import_failed")
    assert evidence["search_root_mask"] == 63
    assert evidence["package_root_mask"] == 63
    assert evidence["package_origin"] == "unknown"
    assert evidence["target_module"] == TARGET
    assert evidence["missing_category"] == "other_dependency"
    assert evidence["error_type"] == "ModuleNotFoundError"
    assert evidence["expected_root_on_path"] is True
    assert all(evidence[k] is True for k in ("expected_repo_available", "expected_package_available", "expected_recorder_available"))
    data = (tmp_path / "helper.jsonl").read_bytes()
    assert len(data) <= 16384
    assert len(rows) <= 64
    assert all(len(line) + 1 <= 512 for line in data.splitlines())
    assert rows[-1]["event"] == "observer_truncated"
    assert b"SENSITIVE" not in data


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("index", range(6))
def test_each_origin_and_search_root(monkeypatch, tmp_path, frozen, index):
    expected = os.path.dirname(os.path.dirname(helper.__file__))
    paths = [os.path.join(expected, "yasb_limitora", "__init__.py"), str(tmp_path / "SENSITIVE.py"), os.path.join(sys.base_prefix, "Lib", "site-packages", "p.py"), os.path.join(sys.base_prefix, "Lib", "p.py"), "frozen", None]
    monkeypatch.setattr(sys, "path", [paths[index]])
    monkeypatch.setitem(sys.modules, "yasb_limitora", SimpleNamespace(__spec__=SimpleNamespace(origin=paths[index]), __file__=None, __path__=[]))
    row = connect(monkeypatch, tmp_path, ImportError("SENSITIVE"), frozen)[-1]
    assert row["package_origin"] == ROOTS[index]
    assert row["search_root_mask"] == 1 << index
    assert row["expected_root_on_path"] == (index == 0)
    assert "SENSITIVE" not in json.dumps(row)


@pytest.mark.parametrize("frozen", [False, True])
def test_attribute_failure_preserves_other_facts(monkeypatch, tmp_path, frozen):
    class Broken:
        def __getattribute__(self, key):
            raise RuntimeError("SENSITIVE")
    monkeypatch.setitem(sys.modules, "yasb_limitora", Broken())
    row = connect(monkeypatch, tmp_path, ModuleNotFoundError(name=TARGET), frozen)[-1]
    assert row["package_origin"] == "unknown"
    assert row["package_root_mask"] == 32
    assert row["missing_category"] == "target"
    assert row["expected_recorder_available"] is True


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("failure,value", [(FileNotFoundError, False), (PermissionError, "unknown")])
def test_availability_per_field(monkeypatch, tmp_path, frozen, failure, value):
    original = os.stat
    expected = os.path.dirname(os.path.dirname(helper.__file__))
    def stat(path, *a, **k):
        if str(path) in (os.path.dirname(expected), os.path.join(expected, "yasb_limitora"), os.path.join(expected, "yasb_limitora", "_native_proof_observability.py")):
            raise failure("SENSITIVE")
        return original(path, *a, **k)
    monkeypatch.setattr(os, "stat", stat)
    row = connect(monkeypatch, tmp_path, ImportError(), frozen)[-1]
    for key in ("expected_repo_available", "expected_package_available", "expected_recorder_available"):
        assert row[key] == value


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("operation", ["open", "read", "write"])
def test_sink_failures_silent(monkeypatch, tmp_path, frozen, operation):
    original = builtins.open
    class Sink:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def seek(self, *args):
            return 0
        def read(self, *args):
            if operation == "read":
                raise OSError("SENSITIVE")
            return b""
        def write(self, *args):
            raise OSError("SENSITIVE")
    def opening(path, *a, **k):
        if str(path).endswith("helper.jsonl"):
            if operation == "open":
                raise OSError("SENSITIVE")
            return Sink()
        return original(path, *a, **k)
    monkeypatch.setattr(builtins, "open", opening)
    assert connect(monkeypatch, tmp_path, ImportError(), frozen) == []


@pytest.mark.parametrize("frozen", [False, True])
def test_bundle_is_not_expected_worktree(monkeypatch, tmp_path, frozen):
    import time
    bundle = tmp_path / "bundle"
    package = bundle / "yasb_limitora"
    package.mkdir(parents=True)
    helper_file = package / "codex_helper.py"
    recorder = package / "_native_proof_observability.py"
    helper_file.touch()
    recorder.touch()
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "path", [str(bundle)])
    monkeypatch.setitem(sys.modules, "yasb_limitora", SimpleNamespace(__spec__=SimpleNamespace(origin=str(package / "__init__.py")), __file__=None, __path__=[str(package)]))
    monkeypatch.setattr(time, "monotonic_ns", lambda: 9999999999999999999)
    monkeypatch.setitem(helper._metadata_namespace, "_expected_helper_file", str(helper_file))
    monkeypatch.setattr(helper, "_CHILD_BOOTSTRAP", helper._CHILD_BOOTSTRAP.replace(repr(helper._expected_helper_file), repr(str(helper_file)), 1))
    direct = helper._import_evidence(ModuleNotFoundError(name=TARGET))
    row = connect(monkeypatch, tmp_path, ModuleNotFoundError(name=TARGET), frozen)[-1]
    assert all(row[key] == value for key, value in direct.items())
    assert row["expected_repo_available"] == "unknown"
    assert row["expected_root_on_path"] == "unknown"
    assert row["expected_package_available"] is True
    assert row["expected_recorder_available"] is True
    assert row["package_origin"] == "frozen_bundle"
    assert row["search_root_mask"] == 16
    assert row["package_root_mask"] == 16
    assert row["missing_category"] == "target"
    assert row["error_type"] == "ModuleNotFoundError"
    assert len(json.dumps(row, separators=(",", ":")).encode()) + 1 <= 512
    assert str(tmp_path) not in json.dumps(row)


def test_shared_definitions_are_metadata_only():
    import ast
    tree = ast.parse(helper._BOOTSTRAP_METADATA)
    assert all(isinstance(node, ast.FunctionDef) for node in tree.body)
    assert 'runpy.run_module("yasb_limitora.codex_helper", run_name="__main__")' in helper._CHILD_BOOTSTRAP


def test_flags_preserved(monkeypatch):
    monkeypatch.setattr(helper, "_is_frozen_runtime", lambda: False)
    assert helper._helper_command() == (sys.executable, "-I", "-E", "-c", helper._CHILD_BOOTSTRAP)

from yasb_limitora import _native_proof_observability as observer


def _observer_rows(directory, role="helper"):
    path = directory / f"{role}.jsonl"
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


def test_source_capable_state_and_capability_event_are_persisted(tmp_path):
    observer.record(tmp_path, "helper", "ready_emitted", pid=1, state="source_capable")
    observer.record(tmp_path, "helper", "helper_bootstrap_capability", state="source_capable")
    rows = _observer_rows(tmp_path)
    assert rows[0]["state"] == "source_capable"
    assert rows[1]["event"] == "helper_bootstrap_capability"
    assert rows[1]["state"] == "source_capable"


def test_unknown_event_state_and_fields_stay_rejected(tmp_path):
    observer.record(tmp_path, "helper", "not_a_real_event", state="source_capable")
    observer.record(tmp_path, "helper", "ready_emitted", state="not_a_state", secret="SENSITIVE")
    observer.record(tmp_path, "helper", "helper_bootstrap_capability", error_type="ModuleNotFoundError")
    rows = _observer_rows(tmp_path)
    assert [r["event"] for r in rows] == ["ready_emitted", "helper_bootstrap_capability"]
    assert "state" not in rows[0] and "secret" not in rows[0]
    assert "error_type" not in rows[1] and "state" not in rows[1]


def test_capability_event_does_not_widen_allowed_fields(tmp_path):
    observer.record(tmp_path, "helper", "helper_bootstrap_capability", state="source_capable",
                    missing_category="target", search_root_mask=1, package_origin="unknown",
                    expected_root_on_path=False, secret="SENSITIVE")
    row = _observer_rows(tmp_path)[0]
    assert row["state"] == "source_capable"
    assert set(row) == {"role", "event", "monotonic_ns", "state"}


def test_previously_admitted_c5_behavior_is_unchanged(tmp_path):
    observer.record(tmp_path, "helper", "ready_emitted", pid=7)
    observer.record(tmp_path, "helper", "request_received", pid=8)
    observer.record(tmp_path, "helper", "original_exception", error_type="ValueError")
    observer.record(tmp_path, "helper", "original_exception", error_type="NotAllowedType")
    rows = _observer_rows(tmp_path)
    assert [r["event"] for r in rows] == ["ready_emitted", "request_received", "original_exception", "original_exception"]
    assert rows[0]["pid"] == 7 and "state" not in rows[0]
    assert rows[2]["error_type"] == "ValueError" and rows[3]["error_type"] == "unknown"


def test_c6_only_events_are_rejected_and_their_states_are_not_represented(tmp_path):
    for event in ("persistence_temp_started", "persistence_replace_started", "fixture_failure"):
        observer.record(tmp_path, "helper", event)
    for state in ("write_failed", "root_present_extra"):
        observer.record(tmp_path, "helper", "ready_emitted", state=state)
    rows = _observer_rows(tmp_path)
    assert [r["event"] for r in rows] == ["ready_emitted", "ready_emitted"]
    assert all("state" not in r for r in rows)
