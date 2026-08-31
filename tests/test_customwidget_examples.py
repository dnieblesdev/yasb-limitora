import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples/customwidget"
FIXTURES = EXAMPLE / "fixtures"
BASELINE = {
    "complete": ("complete", ("snapshot", "available", "fresh"), (80, 60)),
    "partial": ("complete", ("snapshot", "partial", "fresh"), (None, None)),
    "stale": ("complete", ("snapshot", "available", "stale"), (40, 40)),
    "undetected": ("complete", ("undetected", None, None), (None, None)),
    "provider-unavailable": ("partial", ("execution_error", None, None), (None, 60)),
    "providers-disabled": ("not_run", ("not_run", None, None), (None, None)),
    "safe-error": ("execution_error", ("execution_error", None, None), (None, None)),
}
EDGE = {
    "guard-timeout": ("not_run", ("not_run", None, None), (None, None)),
    "deadline-not-run": ("not_run", ("not_run", None, None), (None, None)),
    "multiline-unicode": ("complete", ("snapshot", "available", "fresh"), (73, 73)),
    "missing-data": ("complete", ("snapshot", "partial", "stale"), (None, None)),
}
ALL_FIXTURES = {**BASELINE, **EDGE}
NOT_RUN_PRESENTATION = {
    "disabled": "provider disabled",
    "guard_wait_timeout": "guard wait timeout",
    "deadline_exhausted": "deadline exhausted",
}
WINDOW_TOOLTIP_SUFFIXES = {
    "complete": (
        "Window: kind=commercial_quota; scope=account; period=day; plan_id=null; "
        "unit=percentage_points; source_id=\"codex-app-server-v2\"; result=80% remaining\n"
        "Reset: 2026-08-02T00:00:00.000000Z",
        "Window: kind=commercial_quota; scope=account; period=day; plan_id=null; "
        "unit=percentage_points; source_id=\"opencode-go-api\"; result=60% remaining\n"
        "Reset: 2026-08-02T00:00:00.000000Z",
    ),
    "partial": (None, None),
    "stale": (
        "Window: kind=commercial_quota; scope=account; period=day; plan_id=null; "
        "unit=percentage_points; source_id=\"codex-app-server-v2\"; result=40% remaining\n"
        "Reset: 2026-08-02T00:00:00.000000Z",
        "Window: kind=commercial_quota; scope=account; period=day; plan_id=null; "
        "unit=percentage_points; source_id=\"opencode-go-api\"; result=40% remaining\n"
        "Reset: 2026-08-02T00:00:00.000000Z",
    ),
    "undetected": (None, None),
    "provider-unavailable": (
        None,
        "Window: kind=commercial_quota; scope=account; period=day; plan_id=null; "
        "unit=percentage_points; source_id=\"opencode-go-api\"; result=60% remaining\n"
        "Reset: 2026-08-02T00:00:00.000000Z",
    ),
    "providers-disabled": (None, None),
    "safe-error": (None, None),
    "guard-timeout": (None, None),
    "deadline-not-run": (None, None),
    "multiline-unicode": ("Note: résumé ✓", "Note: résumé ✓"),
    "missing-data": (None, None),
}
RUNTIME_METADATA = {
    "guard-timeout": {
        "exit_code": 1,
        "stderr": b"yasb-limitora: guard_wait_timeout" + bytes([0x0A]),
        "document": {"code": "guard_wait_timeout", "phase": "guard_wait"},
        "reason": "guard_wait_timeout",
        "tooltip": "Quota not run: guard wait timeout",
    },
    "deadline-not-run": {
        "exit_code": 1,
        "stderr": b"yasb-limitora: runtime_error" + bytes([0x0A]),
        "document": {"code": "deadline_exhausted", "phase": "document"},
        "reason": "deadline_exhausted",
        "tooltip": "Quota not run: deadline exhausted",
    },
}
V1_SHA256 = {
    "json_v1_success.json": "974957799f3729bb4ee66ad405f1cbd4594a1024592103338fa4ffa1a57d1013",
    "json_v1_unicode_label.json": "9ebca8f5675145771aedb0b821d16b021763df4842fabea8fa9576c7f3dbacec",
    "json_v1_unavailable.json": "7c68e64a98981bf0255cd7e7f039a2209f49f9d153127370d97df1038e1e11a3",
    "json_v1_safe_error.json": "f322351a2f4ce4d548adac6583592ab1d4483c2f20dc3c8284c4d8ede1cbb515",
}


def _json_document(path):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def _assert_safe_leaf(value, tooltip=False):
    assert isinstance(value, str)
    assert value
    assert len(value) <= (4096 if tooltip else 128)
    assert not any(ord(char) < 32 and (not tooltip or char != "\n") for char in value)
    assert "\r" not in value and "stderr" not in value.lower()


def _assert_provider(provider, expected, percentage, display_state=None, tooltip_suffix=None):
    assert list(provider) == [
        "provider", "outcome", "public_state", "freshness", "status_observed_at",
        "fetched_at", "data_at", "source_id", "windows", "execution_error",
        "not_run_reason", "most_depleted_window", "compact_text", "alternate_text",
        "tooltip_text",
    ]
    outcome, state, freshness = expected
    expected_source = "codex-app-server-v2" if provider["provider"] == "codex" else "opencode-go-api"
    assert provider["source_id"] in {expected_source, None} and all(window["source_id"] in {expected_source, None} for window in provider["windows"])
    display_state = state if display_state is None else display_state
    assert provider["outcome"] == outcome
    assert provider["public_state"] == state
    assert provider["freshness"] == freshness
    if outcome != "execution_error":
        assert provider["execution_error"] is None
    if outcome != "not_run":
        assert provider["not_run_reason"] is None
    assert all(leaf in provider for leaf in ("compact_text", "alternate_text", "tooltip_text"))
    _assert_safe_leaf(provider["compact_text"])
    _assert_safe_leaf(provider["alternate_text"])
    _assert_safe_leaf(provider["tooltip_text"], tooltip=True)
    if percentage is not None:
        assert provider["compact_text"] == f"Quota {percentage}% remaining; state={display_state}; freshness={freshness}"
        assert provider["alternate_text"] == f"Quota account / {provider['most_depleted_window']['period']}: {percentage}% remaining; state={display_state}; freshness={freshness}"
        assert provider["tooltip_text"].startswith(f"State: {display_state}\nFreshness: {freshness}\nQuota: {percentage}% remaining")
        assert provider["most_depleted_window"]["remaining_percentage"] == str(percentage)
    elif outcome == "snapshot":
        assert provider["compact_text"] == f"Quota percentage unavailable; state={display_state}; freshness={freshness}"
        assert provider["alternate_text"] == provider["compact_text"]
        assert provider["tooltip_text"].startswith(f"State: {display_state}\nFreshness: {freshness}\nQuota: percentage unavailable\nNo eligible percentage basis")
        assert provider["most_depleted_window"] is None
    elif outcome == "undetected":
        assert provider["compact_text"] == provider["alternate_text"] == provider["tooltip_text"] == "Quota not detected"
    elif outcome == "not_run":
        reason_text = NOT_RUN_PRESENTATION[provider["not_run_reason"]]
        assert provider["compact_text"] == provider["alternate_text"] == "Quota not run"
        assert provider["tooltip_text"] == f"Quota not run: {reason_text}"
    else:
        assert provider["compact_text"] == provider["alternate_text"] == provider["tooltip_text"] == "Quota error"


class CustomWidgetExamplesTests(unittest.TestCase):
    def test_fixture_coverage_is_exact(self):
        expected = {"customwidget.yaml", "styles.css", "README.md"}
        assert expected <= {path.name for path in EXAMPLE.iterdir() if path.is_file()}
        assert {f"{name}.json" for name in ALL_FIXTURES} == {path.name for path in FIXTURES.iterdir()}

    def test_fixture_matrix_is_exact_and_strict_v2(self):
        for name, (execution_state, expected, percentages) in ALL_FIXTURES.items():
            raw = (FIXTURES / f"{name}.json").read_bytes()
            assert raw.endswith(bytes([0x0A])) and b"\r" not in raw
            value = _json_document(FIXTURES / f"{name}.json")
            assert list(value) == ["version", "execution_state", "execution_error", "providers"]
            assert value["version"] == 2 and value["execution_state"] == execution_state and len(value["providers"]) == 2
            assert [provider["provider"] for provider in value["providers"]] == ["codex", "opencode_go"]
            serialized = json.dumps(value).lower()
            assert all(key not in serialized for key in ("opencode-go-dashboard", "exit_code", "stderr", "stdout", "traceback", "password", "api_key", "cookie", "/home/", "c:\\"))
            expected_errors = {
                "provider-unavailable": [
                    {"code": "provider_failed", "phase": "provider"},
                    None,
                ],
                "safe-error": [
                    {"code": "invalid_provider_data", "phase": "provider"},
                    {"code": "invalid_provider_data", "phase": "provider"},
                ],
            }.get(name, [None, None])
            for index, (provider, percent) in enumerate(zip(value["providers"], percentages if name not in ("providers-disabled", "safe-error") else (None, None))):
                assert provider["execution_error"] == expected_errors[index]
                if provider["provider"] == "opencode_go" and provider["outcome"] == "snapshot" and provider["public_state"] in {"available", "partial"}:
                    commercial = [window for window in provider["windows"] if window["kind"] == "commercial_quota"]
                    assert [window["period"] for window in commercial] == ["five_hour", "monthly", "weekly"]
                    assert all(
                        window["source_id"] == "opencode-go-api"
                        if window["availability"] == "known"
                        else window["source_id"] is None
                        and all(window[field] is None for field in ("plan_id", "limit", "used", "remaining", "reset_at"))
                        for window in commercial
                    )
                _assert_provider(
                    provider,
                    expected if name not in ("provider-unavailable",) else ("execution_error", None, None) if provider["provider"] == "codex" else ("snapshot", "available", "fresh"),
                    percent,
                    None,
                )
            if name == "provider-unavailable":
                _assert_provider(
                    value["providers"][1],
                    ("snapshot", "available", "fresh"),
                    60,
                )
            if name == "safe-error":
                assert value["execution_error"] == {"code": "provider_failed", "phase": "provider"}
            if name in RUNTIME_METADATA:
                assert value["execution_error"] == RUNTIME_METADATA[name]["document"]

    def test_guard_and_deadline_runtime_metadata_is_separate_from_fixtures(self):
        for name, expected in RUNTIME_METADATA.items():
            value = _json_document(FIXTURES / f"{name}.json")
            assert expected["exit_code"] == 1
            expected_stderr = (
                b"yasb-limitora: guard_wait_timeout" + bytes([0x0A])
                if name == "guard-timeout"
                else b"yasb-limitora: runtime_error" + bytes([0x0A])
            )
            assert expected["stderr"] == expected_stderr
            assert value["execution_error"] == expected["document"]
            assert [provider["outcome"] for provider in value["providers"]] == ["not_run", "not_run"]
            assert [provider["not_run_reason"] for provider in value["providers"]] == [expected["reason"]] * 2
            assert [provider["tooltip_text"] for provider in value["providers"]] == [expected["tooltip"]] * 2
            serialized = json.dumps(value).lower()
            assert "exit_code" not in serialized and "stderr" not in serialized

    def test_yaml_uses_only_bounded_public_paths_and_verified_options(self):
        text = (EXAMPLE / "customwidget.yaml").read_text(encoding="utf-8")
        assert text.endswith("\n") and "providers][0]" in text
        assert text.startswith("widgets:\n  limitora_r9:\n    type: yasb.custom.CustomWidget\n    options:\n")
        assert "providers[1]" not in text and "callbacks" not in text and "keybindings" not in text
        assert 'run_cmd: "yasb-limitora --output-version 2"' in text
        assert not re.search(r"run_cmd:.*(?:;|&&|\|\||\||`|\$\(|>|<)", text)
        assert re.findall(r"^      ([a-z_]+):", text, re.MULTILINE) == ["class_name", "label", "label_alt", "tooltip", "tooltip_label", "exec_options"]
        assert re.findall(r"^        ([a-z_]+):", text, re.MULTILINE) == ["run_cmd", "run_once", "run_interval", "return_format", "hide_empty", "use_shell"]
        assert "execution_state" not in text and "windows" not in text and "most_depleted_window" not in text

    def test_css_is_static_and_matches_supported_descendants(self):
        css = (EXAMPLE / "styles.css").read_text(encoding="utf-8")
        assert ".custom-widget.limitora-r9" in css
        assert all(token not in css for token in ("[data-", ".state-", ".provider-", "refreshing", "execution_state"))
        assert {selector.rstrip() for selector in re.findall(r"\.custom-widget\.limitora-r9[^,{]*", css)} <= {
            ".custom-widget.limitora-r9", ".custom-widget.limitora-r9 .widget-container .label",
            ".custom-widget.limitora-r9 .widget-container .label.alt", ".custom-widget.limitora-r9 .widget-container .icon",
        }

    def test_missing_consumed_leaf_is_rejected_and_v1_bytes_remain_frozen(self):
        value = _json_document(FIXTURES / "complete.json")
        del value["providers"][0]["tooltip_text"]
        with self.assertRaises(AssertionError):
            _assert_provider(value["providers"][0], ("snapshot", "available", "fresh"), 80)
        for name, digest in V1_SHA256.items():
            assert hashlib.sha256((ROOT / "tests/fixtures" / name).read_bytes()).hexdigest() == digest

    def test_multiline_unicode_uses_utf8_and_lf_only(self):
        value = _json_document(FIXTURES / "multiline-unicode.json")
        for provider in value["providers"]:
            assert "Note: résumé ✓" in provider["tooltip_text"]
            assert bytes([0x0A]) in provider["tooltip_text"].encode("utf-8")
            assert b"\r" not in provider["tooltip_text"].encode("utf-8")

    def test_missing_data_never_becomes_zero_percent(self):
        value = _json_document(FIXTURES / "missing-data.json")
        serialized = json.dumps(value)
        assert "0%" not in serialized
        for provider in value["providers"]:
            assert provider["most_depleted_window"] is None
            assert provider["compact_text"] == "Quota percentage unavailable; state=partial; freshness=stale"
            assert provider["alternate_text"] == provider["compact_text"]
            assert "No eligible percentage basis" in provider["tooltip_text"]


if __name__ == "__main__":
    unittest.main()
