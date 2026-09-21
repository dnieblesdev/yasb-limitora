"""S08 reject-and-preserve validation for the optional config wizard."""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading

import pytest  # pyright: ignore[reportMissingImports]

import yasb_limitora.setup_assist as sa
from yasb_limitora import _config_lock, cli
from yasb_limitora.config import ConfigError


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b'{"deadline_seconds":', "malformed-json"),
        (b'{"deadline_seconds": 7, "deadline_seconds": 8}', "duplicate-key"),
        (b'{"deadline_seconds": NaN}', "non-finite-number"),
        (b'{"unknown": true}', "unknown-field"),
        (b'{"token": "never-report-this"}', "credential-like-key"),
        (b'{"deadline_seconds": "seven"}', "wrong-type"),
        (b'\xff\xfe\x00', "undecodable-input"),
    ],
)
def test_invalid_config_is_rejected_byte_for_byte_before_any_mutation(tmp_path, raw, reason):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)
    before = hashlib.sha256(raw).hexdigest()

    records = sa._execute((("config-apply", True),), {}, str(local_appdata))

    assert records == [{
        "operation": "config-apply", "status": "refused", "reason": "configuration-invalid",
        "diagnostics": [{"field": "config", "reason": reason}],
    }]
    assert config_path.read_bytes() == raw
    assert hashlib.sha256(config_path.read_bytes()).hexdigest() == before
    assert sorted(path.name for path in config_path.parent.iterdir()) == ["config.json"]


def test_runtime_valid_config_stops_at_gate_one_without_creating_a_backup_or_temp(tmp_path):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    raw = b'{"deadline_seconds": 7}'
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)

    records = sa._execute((("config-apply", True),), {}, str(local_appdata))

    assert records == [{"operation": "config-apply", "status": "refused", "reason": "config-gate-2-unavailable"}]
    assert config_path.read_bytes() == raw
    assert sorted(path.name for path in config_path.parent.iterdir()) == ["config.json"]


def _run_config_apply(tmp_path, selection=None, raw=None):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    if raw is not None:
        config_path.parent.mkdir(parents=True)
        config_path.write_bytes(raw)
    return local_appdata, config_path, sa._execute((("config-apply", selection),), {}, str(local_appdata)) if selection is not None else None


def test_config_apply_merges_only_owned_fields_and_preserves_order(tmp_path):
    _, config_path, records = _run_config_apply(tmp_path, {"deadline_seconds": 12, "codex": {"enabled": True}}, b'{"opencode_go": {"timeout_seconds": 5}, "deadline_seconds": 7, "codex": {"runner": "C:\\\\codex.exe"}}')

    assert records == [{"operation": "config-apply", "status": "ok"}]
    assert list(__import__("json").loads(config_path.read_text(encoding="utf-8"))) == ["opencode_go", "deadline_seconds", "codex"]
    assert __import__("json").loads(config_path.read_text(encoding="utf-8")) == {
        "opencode_go": {"timeout_seconds": 5}, "deadline_seconds": 12,
        "codex": {"runner": "C:\\codex.exe", "enabled": True}, }
    backups = list(config_path.parent.joinpath("backups").glob("config.*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == b'{"opencode_go": {"timeout_seconds": 5}, "deadline_seconds": 7, "codex": {"runner": "C:\\\\codex.exe"}}'


def test_config_apply_rejects_unowned_selection_and_never_writes(tmp_path):
    _, config_path, records = _run_config_apply(tmp_path, {"custom": True}, b'{"deadline_seconds": 7}')

    assert records == [{"operation": "config-apply", "status": "refused", "reason": "config-selection-invalid"}]
    assert config_path.read_bytes() == b'{"deadline_seconds": 7}'
    assert not config_path.parent.joinpath("backups").exists()


def test_config_apply_creates_absent_config_only_for_explicit_selection(tmp_path):
    _, config_path, records = _run_config_apply(tmp_path, {"deadline_seconds": 12})

    assert records == [{"operation": "config-apply", "status": "ok"}]
    assert __import__("json").loads(config_path.read_text(encoding="utf-8")) == {"deadline_seconds": 12}
    assert len(list(config_path.parent.joinpath("backups").glob("config.*.json"))) == 0


def test_config_apply_failure_restores_original_after_replace_failure(tmp_path, monkeypatch):
    local_appdata, config_path, _ = _run_config_apply(tmp_path, None, b'{"deadline_seconds": 7}')
    monkeypatch.setattr(sa.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))
    records = sa._execute((("config-apply", {"deadline_seconds": 12}),), {}, str(local_appdata))

    assert records == [{"operation": "config-apply", "status": "refused", "reason": "config-write-failed"}]
    assert config_path.read_bytes() == b'{"deadline_seconds": 7}'
    assert not list(config_path.parent.glob(".config.*.tmp"))


@pytest.mark.parametrize(
    ("raw", "accepted", "providers"),
    [
        (b'{"codex":{"enabled":"not-a-bool"}}', True, {"codex"}),
        (b'{"opencode_go":{"timeout_seconds":"bad"}}', True, {"opencode_go"}),
        (b'{"unknown":true}', False, set()),
    ],
)
def test_gate_one_matches_runtime_acceptance_and_sanitizes_provider_diagnostics(tmp_path, raw, accepted, providers):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)

    try:
        _config, runtime_errors = cli._load_explicit(str(config_path))
        runtime_accepted = True
    except ConfigError:
        runtime_errors, runtime_accepted = frozenset(), False
    record = sa._execute((("config-apply", True),), {}, str(local_appdata))[0]
    diagnostics = record.get("diagnostics", [])

    assert runtime_accepted is accepted
    assert {key.value for key in runtime_errors} == providers
    assert (record["reason"] == "config-gate-2-unavailable") is accepted
    assert isinstance(diagnostics, list)
    if accepted:
        assert {item["provider"] for item in diagnostics if isinstance(item, dict)} == providers
        assert all(isinstance(item, dict) and set(item) == {"provider", "reason"} and item["reason"] == "provider-invalid" for item in diagnostics)
    else:
        assert diagnostics == [{"field": "config", "reason": "unknown-field"}]
    assert config_path.read_bytes() == raw


def test_gate_one_refuses_when_handle_verification_detects_a_config_swap(tmp_path, monkeypatch):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(b'{"deadline_seconds":7}')
    monkeypatch.setattr(sa, "_fd_reached_path", lambda *_args: False)

    assert sa._execute((("config-apply", True),), {}, str(local_appdata)) == [{
        "operation": "config-apply", "status": "refused", "reason": "configuration-invalid",
        "diagnostics": [{"field": "config", "reason": "unreadable-input"}],
    }]
    assert config_path.read_bytes() == b'{"deadline_seconds":7}'


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse coverage")
def test_gate_one_rejects_real_parent_replacement_before_open(tmp_path, monkeypatch):
    original = b'{"deadline_seconds":7}'
    substituted = b'{"deadline_seconds":99}'
    real_open = sa.os.open

    for attempt in range(3):
        local_appdata = tmp_path / f"local-{attempt}"
        state = local_appdata / "yasb-limitora"
        attacker = tmp_path / f"attacker-{attempt}"
        config_path = state / "config.json"
        state.mkdir(parents=True)
        config_path.write_bytes(original)
        attacker.mkdir()
        (attacker / "config.json").write_bytes(substituted)
        probe = tmp_path / f"junction-probe-{attempt}"
        probe_target = tmp_path / f"junction-target-{attempt}"
        junctions = []
        worker = None
        release = threading.Event()
        try:
            probe_target.mkdir()
            junctions.append(probe)
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(probe), str(probe_target)], capture_output=True, check=False)
            if result.returncode:
                pytest.skip("directory junction unavailable")

            opened = threading.Event()
            outcome = []
            normalized = os.path.normcase(os.fspath(config_path))

            def gated_open(path, flags, mode=0o777, *, dir_fd=None, expected=normalized,
                           opened_event=opened, release_event=release):
                if os.path.normcase(os.fspath(path)) == expected:
                    opened_event.set()
                    if not release_event.wait(5):
                        raise OSError("test synchronization timeout")
                if dir_fd is None:
                    return real_open(path, flags, mode)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            monkeypatch.setattr(sa.os, "open", gated_open)

            def read_config(path=str(local_appdata), result=outcome):
                result.append(sa._config_gate_one(path))

            worker = threading.Thread(target=read_config)
            worker.start()
            assert opened.wait(5), "reader did not reach the synchronized open boundary"
            os.rename(state, str(state) + "-original")
            junctions.append(state)
            link = subprocess.run(["cmd", "/c", "mklink", "/J", str(state), str(attacker)], capture_output=True, check=False)
            assert link.returncode == 0, link.stderr.decode(errors="replace")
            release.set()
            worker.join(5)
            assert not worker.is_alive()
            assert outcome == [{
                "operation": "config-apply", "status": "refused", "reason": "configuration-invalid",
                "diagnostics": [{"field": "config", "reason": "unreadable-input"}],
            }]
            assert (attacker / "config.json").read_bytes() == substituted
            assert (state.parent / "yasb-limitora-original" / "config.json").read_bytes() == original
        finally:
            release.set()
            if worker is not None:
                worker.join(5)
                assert not worker.is_alive()
            for junction in junctions:
                if os.path.lexists(junction):
                    os.rmdir(junction)
                assert not os.path.lexists(junction)


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse coverage")
@pytest.mark.parametrize("root_reparse", [False, True])
def test_gate_one_refuses_temp_only_file_or_root_reparse_without_reading_its_target(tmp_path, root_reparse):
    local_appdata, outside = tmp_path / "local", tmp_path / "outside"
    state, outside_config = local_appdata / "yasb-limitora", outside / "config.json"
    outside.mkdir()
    outside_config.write_bytes(b'{"deadline_seconds":7}')
    try:
        if root_reparse:
            local_appdata.mkdir()
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(state), str(outside)], capture_output=True, check=False)
            if result.returncode:
                pytest.skip("directory junction unavailable")
        else:
            state.mkdir(parents=True)
            (state / "config.json").symlink_to(outside_config)
    except OSError as error:
        pytest.skip(f"reparse unavailable: {error}")

    record = sa._execute((("config-apply", True),), {}, str(local_appdata))[0]

    assert record["reason"] == "configuration-invalid"
    assert outside_config.read_bytes() == b'{"deadline_seconds":7}'


def test_invalid_optional_config_is_nonfatal_but_runtime_stays_fail_closed(tmp_path):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    raw = b'{"unknown": true}'
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)

    records = sa._execute((("config-apply", True),), {}, str(local_appdata))

    assert records[0]["status"] == "refused"  # installer program transaction may continue
    with pytest.raises(ConfigError):
        cli._load_explicit(str(config_path))
    assert config_path.read_bytes() == raw


def test_config_assist_never_creates_config_without_a_completed_wizard_flow(tmp_path):
    local_appdata = tmp_path / "local"

    records = sa._execute((("config-apply", True),), {}, str(local_appdata))

    assert records == [{"operation": "config-apply", "status": "refused", "reason": "config-absent"}]
    assert not local_appdata.exists()


def test_config_parent_has_present_absent_unsafe_tri_state(tmp_path):
    local_appdata = tmp_path / "local"
    parent = local_appdata / "yasb-limitora"
    assert sa._config_parent_state(str(parent)) == "absent"
    parent.mkdir(parents=True)
    assert sa._config_parent_state(str(parent)) == "present"
    parent.rmdir()
    parent.write_bytes(b"not-a-directory")
    assert sa._config_parent_state(str(parent)) == "unsafe"


def test_absent_parent_returns_snapshot_without_lock_or_state_root(tmp_path):
    local_appdata = tmp_path / "local"
    events = []

    def fail_if_acquired(*_args, **_kwargs):
        events.append("acquired")
        raise AssertionError("lock must not be acquired for an absent parent")

    snapshot = sa._config_snapshot(local_appdata=str(local_appdata), lease_factory=fail_if_acquired)

    assert snapshot.state == "absent"
    assert snapshot.raw_bytes is None and snapshot.local_config is None
    assert snapshot.provider_errors == frozenset()
    assert events == []
    assert not local_appdata.exists()


def test_snapshot_reads_fixed_path_and_validates_once_while_lease_is_owned(tmp_path, monkeypatch):
    local_appdata = tmp_path / "local"
    parent = local_appdata / "yasb-limitora"
    parent.mkdir(parents=True)
    raw = b'{"codex":{"enabled":"bad"}}'
    path = parent / "config.json"
    path.write_bytes(raw)
    calls = []
    lease_states = []

    class Lease:
        owned = True

    class LeaseContext:
        def __enter__(self):
            lease_states.append(Lease.owned)
            return Lease()

        def __exit__(self, *_args):
            Lease.owned = False

    def lease_factory(local_appdata):
        assert local_appdata == str(tmp_path / "local")
        assert _config_lock._fixed_config_path(local_appdata).replace("\\", "/").endswith("/yasb-limitora/config.json")
        return LeaseContext()

    original = sa.config.validate_config_document

    def validate_once(raw_bytes, provider_errors):
        calls.append((raw_bytes, Lease.owned))
        return original(raw_bytes, provider_errors)

    monkeypatch.setattr(sa.config, "validate_config_document", validate_once)
    snapshot = sa._config_snapshot(local_appdata=str(local_appdata), lease_factory=lease_factory)

    assert calls == [(raw, True)]
    assert lease_states == [True]
    assert snapshot.raw_bytes == raw
    assert snapshot.local_config is not None
    assert {key.value for key in snapshot.provider_errors} == {"codex"}


def test_snapshot_is_deeply_immutable(tmp_path):
    local_appdata = tmp_path / "local"
    parent = local_appdata / "yasb-limitora"
    parent.mkdir(parents=True)
    parent.joinpath("config.json").write_bytes(b'{"deadline_seconds":7}')

    snapshot = sa._config_snapshot(local_appdata=str(local_appdata))

    with pytest.raises((AttributeError, TypeError)):
        snapshot.state = "absent"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        snapshot.provider_errors.add("codex")  # type: ignore[attr-defined]
    assert isinstance(snapshot.raw_bytes, bytes)


def test_assist_consumes_snapshot_before_lease_release(tmp_path, monkeypatch):
    local_appdata = tmp_path / "local"
    parent = local_appdata / "yasb-limitora"
    parent.mkdir(parents=True)
    parent.joinpath("config.json").write_bytes(b'{"deadline_seconds":7}')
    observed = []

    monkeypatch.setattr(sa, "_consume_config_snapshot", lambda snapshot, lease: observed.append((snapshot.state, lease.owned)))
    result = sa._config_gate_one(str(local_appdata))

    assert result is None
    assert observed == [("present", True)]
