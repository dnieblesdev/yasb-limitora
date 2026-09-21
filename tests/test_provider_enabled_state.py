"""D04 provider selection state and advisory readiness warnings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import ClassVar

import yasb_limitora.setup_assist as sa


def _apply(tmp_path, selection, raw, environment=None):
    local_appdata = tmp_path / "local"
    config_path = local_appdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)
    records = sa._execute(
        (("config-apply", selection),), environment or {}, str(local_appdata)
    )
    return records[0], json.loads(config_path.read_text(encoding="utf-8"))


def test_enabled_state_changes_only_from_explicit_selection_and_preserves_order(tmp_path):
    raw = (
        b'{"opencode_go":{"enabled":true,"timeout_seconds":5},'
        b'"deadline_seconds":7,"codex":{"enabled":false,"runner":null}}'
    )

    record, document = _apply(
        tmp_path,
        {"codex": {"runner": "C:\\missing.exe"}, "deadline_seconds": 12},
        raw,
    )

    assert record["status"] == "ok"
    assert document == {
        "opencode_go": {"enabled": True, "timeout_seconds": 5},
        "deadline_seconds": 12,
        "codex": {"enabled": False, "runner": "C:\\missing.exe"},
    }
    assert list(document) == ["opencode_go", "deadline_seconds", "codex"]


def test_readiness_uses_preserved_enabled_state(tmp_path):
    raw = b'{"opencode_go":{"enabled":true}}'

    record, document = _apply(tmp_path, {"deadline_seconds": 8}, raw)

    assert document["opencode_go"]["enabled"] is True
    assert record["warnings"] == [{
        "provider": "opencode_go",
        "reason": "missing-api-key",
        "requirement": "LIMITORA_OPENCODE_API_KEY",
    }]


def test_enabled_false_does_not_emit_readiness_warning(tmp_path):
    raw = b'{"opencode_go":{"enabled":true}}'

    record, document = _apply(
        tmp_path, {"opencode_go": {"enabled": False}}, raw
    )

    assert record == {"operation": "config-apply", "status": "ok"}
    assert document["opencode_go"]["enabled"] is False


def test_present_opencode_key_suppresses_warning_without_reading_secret_value(tmp_path):
    class KeyPresenceOnly(Mapping[str, str]):
        _values: ClassVar[dict[str, str]] = {"LIMITORA_OPENCODE_API_KEY": ""}

        def __contains__(self, key: object) -> bool:
            return key in self._values

        def __getitem__(self, key: str) -> str:
            raise AssertionError(f"secret value inspected: {key}")

        def __iter__(self):
            return iter(self._values)

        def __len__(self) -> int:
            return len(self._values)

    record, document = _apply(
        tmp_path,
        {"deadline_seconds": 8},
        b'{"opencode_go":{"enabled":true}}',
        KeyPresenceOnly(),
    )

    assert record == {"operation": "config-apply", "status": "ok"}
    assert document["opencode_go"]["enabled"] is True


def test_readiness_warnings_are_bounded_name_only_and_non_vetoing(tmp_path):
    runner = "C:\\not-a-real-codex-runner.exe"
    raw = json.dumps(
        {"codex": {"enabled": True, "runner": runner}, "opencode_go": {"enabled": True}}
    ).encode()

    record, document = _apply(tmp_path, {"deadline_seconds": 8}, raw, {})

    assert record == {
        "operation": "config-apply",
        "status": "ok",
        "warnings": [
            {
                "provider": "codex",
                "reason": "runner-not-file",
                "requirement": "codex-runner-file",
            },
            {
                "provider": "opencode_go",
                "reason": "missing-api-key",
                "requirement": "LIMITORA_OPENCODE_API_KEY",
            },
        ],
    }
    assert document["codex"]["runner"] == runner
    assert runner not in json.dumps(record)
    assert "secret" not in json.dumps(record).lower()
