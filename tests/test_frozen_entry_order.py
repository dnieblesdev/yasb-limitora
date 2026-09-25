"""Frozen entry order: platform gate -> freeze_support -> helper/assist sentinel dispatch -> argv validation (design section 2 rules 1/5)."""

from __future__ import annotations

import io
import json

from yasb_limitora import cli
from yasb_limitora.setup_assist import (
    _NONCE_ENV,
    _REQUEST_ENV,
    _SETUP_ASSIST_FLAG,
)

NONCE = "0123456789abcdef" * 2

def _invoke(monkeypatch, argv, *, windows=True, environment=None):
    events: list[str] = []
    monkeypatch.setattr(cli.multiprocessing, "freeze_support", lambda: events.append("freeze_support"))
    monkeypatch.setattr(cli, "_run_internal_helper", lambda: events.append("helper") or 0)
    monkeypatch.setattr(cli, "_run_setup_assist", lambda environment: events.append("assist") or 0)
    original = cli._resolve_config_path
    def observed(argv, environment):
        events.append("config_path")
        return original(argv, environment)
    monkeypatch.setattr(cli, "_resolve_config_path", observed)
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = cli.main(argv, environment={} if environment is None else environment, stdout=stdout, stderr=stderr, platform_is_windows=lambda: windows)
    return code, stdout, stderr, events

def test_platform_gate_precedes_freeze_support_and_sentinels(monkeypatch):
    code, stdout, stderr, events = _invoke(monkeypatch, (_SETUP_ASSIST_FLAG,), windows=False, environment={_NONCE_ENV: NONCE})
    assert (code, stdout.getvalue(), stderr.getvalue(), events) == (2, b"", "yasb-limitora: unsupported_platform\n", [])

def test_assist_sentinel_with_request_dispatches_before_config_path(monkeypatch):
    code, stdout, _, events = _invoke(monkeypatch, (_SETUP_ASSIST_FLAG,), environment={_REQUEST_ENV: "{}"})
    assert code == 0 and stdout.getvalue() == b"" and events == ["freeze_support", "assist"]  # no stdout contract

def test_helper_sentinel_still_precedes_assist_dispatch(monkeypatch):
    monkeypatch.setattr(cli, "_has_internal_helper_environment", lambda: True)
    code, _, _, events = _invoke(monkeypatch, (cli._INTERNAL_HELPER_FLAG,), environment={_NONCE_ENV: NONCE})
    assert code == 0 and events == ["freeze_support", "helper"]

def test_assist_sentinel_without_nonce_falls_through_to_invalid_argv_touching_nothing(monkeypatch, tmp_path):
    code, stdout, stderr, events = _invoke(monkeypatch, (_SETUP_ASSIST_FLAG,), environment={"LOCALAPPDATA": str(tmp_path)})
    document = json.loads(stdout.getvalue())
    assert (code, events, list(tmp_path.iterdir())) == (2, ["freeze_support", "config_path"], [])
    assert document["execution_state"] == "execution_error" and document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert stderr.getvalue() == "yasb-limitora: invocation_invalid\n"

def test_assist_sentinel_with_extra_arguments_is_not_dispatched(monkeypatch):
    code, _, _, events = _invoke(monkeypatch, (_SETUP_ASSIST_FLAG, "--config"), environment={_NONCE_ENV: NONCE})
    assert code == 2 and events == ["freeze_support", "config_path"]
