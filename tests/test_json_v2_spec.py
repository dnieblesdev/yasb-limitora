import json
import re
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "docs/specifications/json-v2.md"
SCHEMA = ROOT / "docs/specifications/json-v2.schema.json"

PROVIDER_FIELDS = {
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
}


def _schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _v2_examples():
    blocks = re.findall(r"```json\n(.*?)\n```", SPEC.read_text(encoding="utf-8"), re.S)
    return [json.loads(block) for block in blocks if json.loads(block)["version"] == 2]


def _is_success_outcome(outcome):
    return outcome in {"snapshot", "undetected"}


def _is_failed_outcome(outcome):
    return outcome in {"not_run", "execution_error"}


def _assert_provider(provider):
    assert set(provider) == PROVIDER_FIELDS
    outcome = provider["outcome"]
    assert outcome in {"snapshot", "undetected", "not_run", "execution_error"}
    assert isinstance(provider["windows"], list)

    if outcome == "snapshot":
        assert provider["public_state"] is not None
        assert provider["freshness"] in {"fresh", "stale"}
        assert all(provider[field] is not None for field in ("status_observed_at", "fetched_at", "data_at"))
        assert provider["execution_error"] is None
        assert provider["not_run_reason"] is None
    elif outcome == "undetected":
        assert provider["public_state"] is None
        assert provider["freshness"] is None
        assert all(provider[field] is None for field in ("status_observed_at", "fetched_at", "data_at", "source_id"))
        assert provider["windows"] == []
        assert provider["execution_error"] is None
        assert provider["not_run_reason"] is None
    elif outcome == "not_run":
        assert provider["public_state"] is None
        assert provider["freshness"] is None
        assert all(provider[field] is None for field in ("status_observed_at", "fetched_at", "data_at", "source_id"))
        assert provider["windows"] == []
        assert provider["execution_error"] is None
        assert provider["not_run_reason"] is not None
    else:
        assert provider["public_state"] is None
        assert provider["freshness"] is None
        assert all(provider[field] is None for field in ("status_observed_at", "fetched_at", "data_at", "source_id"))
        assert provider["windows"] == []
        assert provider["execution_error"] is not None
        assert provider["not_run_reason"] is None


def _assert_document(document):
    assert set(document) == {"version", "execution_state", "execution_error", "providers"}
    assert document["version"] == 2
    assert [provider["provider"] for provider in document["providers"]] == ["codex", "opencode_go"]
    for provider in document["providers"]:
        _assert_provider(provider)

    outcomes = [provider["outcome"] for provider in document["providers"]]
    state = document["execution_state"]
    if state == "complete":
        assert all(_is_success_outcome(outcome) for outcome in outcomes)
        assert document["execution_error"] is None
    elif state == "partial":
        assert any(_is_success_outcome(outcome) for outcome in outcomes)
        assert any(_is_failed_outcome(outcome) for outcome in outcomes)
        assert document["execution_error"] is None
    elif state == "not_run":
        assert all(outcome == "not_run" for outcome in outcomes)
        error = document["execution_error"]
        assert error is None or error["code"] in {"guard_wait_timeout", "deadline_exhausted"}
    else:
        assert document["execution_error"] is not None
        code = document["execution_error"]["code"]
        if code == "cleanup_failed":
            assert document["execution_error"]["phase"] == "cleanup"
            return
        if code == "deadline_exhausted":
            assert all(_is_failed_outcome(outcome) for outcome in outcomes)
            assert any(
                provider["outcome"] == "not_run"
                and provider["not_run_reason"] == "deadline_exhausted"
                for provider in document["providers"]
            )
        elif code == "provider_failed":
            assert all(_is_failed_outcome(outcome) for outcome in outcomes)
            assert any(provider["outcome"] == "execution_error" for provider in document["providers"])
            assert all(provider["not_run_reason"] != "deadline_exhausted" for provider in document["providers"])
        else:
            assert all(_is_failed_outcome(outcome) for outcome in outcomes)


def _significant_digits(value):
    digits = "".join(character for character in value if character.isdigit()).lstrip("0")
    return max(1, len(digits))


def _assert_decimal_bounds(value, definition):
    assert len(value) <= definition["maxLength"]
    assert _significant_digits(value) <= definition["x-maxSignificantDigits"]


def _valid_quantity_triplet(limit, used, remaining):
    if limit is not None and used is not None and used > limit:
        return False
    if limit is not None and remaining is not None and remaining > limit:
        return False
    if limit is not None and used is not None and remaining is not None:
        return used + remaining == limit
    return True


def _remaining_percentage(limit, remaining):
    if limit is None or remaining is None or limit <= 0:
        return None
    if remaining < 0 or remaining > limit:
        raise ValueError("invalid quota evidence")
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = remaining / limit * Decimal("100")
    if not Decimal("0") <= result <= Decimal("100"):
        raise ValueError("invalid derived percentage")
    return result


def test_all_embedded_v2_examples_obey_the_document_matrix():
    examples = _v2_examples()

    assert len(examples) == 16
    for example in examples:
        _assert_document(example)


def test_document_matrix_rejects_illegal_state_combinations():
    complete = deepcopy(_v2_examples()[0])
    complete["execution_state"] = "not_run"
    with pytest.raises(AssertionError):
        _assert_document(complete)

    cleanup = deepcopy(_v2_examples()[10])
    cleanup["execution_error"] = {"code": "internal_error", "phase": "document"}
    with pytest.raises(AssertionError):
        _assert_document(cleanup)

    wrong_cleanup_phase = deepcopy(_v2_examples()[10])
    wrong_cleanup_phase["execution_error"]["phase"] = "provider"
    with pytest.raises(AssertionError):
        _assert_document(wrong_cleanup_phase)

    for index, error in (
        (4, {"code": "provider_failed", "phase": "provider"}),
        (12, {"code": "provider_failed", "phase": "provider"}),
        (14, {"code": "deadline_exhausted", "phase": "document"}),
    ):
        mixed = deepcopy(_v2_examples()[index])
        mixed["execution_state"] = "execution_error"
        mixed["execution_error"] = error
        with pytest.raises(AssertionError):
            _assert_document(mixed)


def test_document_matrix_accepts_all_documented_mixed_outcomes():
    examples = _v2_examples()

    for index in (4, 10, 11, 12, 13, 14, 15):
        _assert_document(examples[index])


def test_schema_declares_root_cross_field_rules():
    schema = _schema()
    root_rules = schema["allOf"]

    states = {
        rule["if"]["properties"]["execution_state"]["const"]
        for rule in root_rules
    }
    assert states == {"complete", "partial", "not_run", "execution_error"}
    partial_rule = next(
        rule for rule in root_rules
        if rule["if"]["properties"]["execution_state"]["const"] == "partial"
    )
    assert "contains" in partial_rule["then"]["properties"]["providers"]["allOf"][0]
    assert "cleanup_failed" in schema["$defs"]["executionError"]["properties"]["code"]["enum"]


def test_presentation_schema_matches_control_character_rules():
    properties = _schema()["$defs"]["providerBase"]["properties"]
    compact = re.compile(properties["compact_text"]["pattern"])
    alternate = re.compile(properties["alternate_text"]["pattern"])
    tooltip = re.compile(properties["tooltip_text"]["pattern"])

    for codepoint in (*range(0x20), 0x7F):
        character = chr(codepoint)
        assert compact.search(f"a{character}b") is None
        assert alternate.search(f"a{character}b") is None
        if codepoint != 0x0A:
            assert tooltip.search(f"a{character}b") is None
    assert compact.search("a\n") is None
    assert alternate.search("a\n") is None
    assert tooltip.search("a\nb") is not None
    assert tooltip.search("a\n") is not None


def test_original_quantity_and_derived_percentage_bounds_are_distinct():
    definitions = _schema()["$defs"]
    quantity = definitions["quantityDecimal"]
    percentage = definitions["percentageDecimal"]

    assert quantity["x-maxSignificantDigits"] == 128
    assert quantity["maxLength"] == 256
    assert percentage["x-maxSignificantDigits"] == 34
    assert percentage["maxLength"] == 128
    assert _significant_digits("9" * 128) == 128
    assert _significant_digits("9" * 129) == 129
    assert _significant_digits("9" * 34) == 34
    assert _significant_digits("9" * 35) == 35
    _assert_decimal_bounds("9" * 128, quantity)
    _assert_decimal_bounds("9" * 34, percentage)
    with pytest.raises(AssertionError):
        _assert_decimal_bounds("9" * 129, quantity)
    with pytest.raises(AssertionError):
        _assert_decimal_bounds("9" * 35, percentage)


def test_quantity_invariants_and_remaining_percentage_formula():
    assert _valid_quantity_triplet(Decimal("100"), Decimal("25"), Decimal("75"))
    assert not _valid_quantity_triplet(Decimal("100"), Decimal("101"), Decimal("0"))
    assert not _valid_quantity_triplet(Decimal("100"), Decimal("0"), Decimal("101"))
    assert not _valid_quantity_triplet(Decimal("100"), Decimal("25"), Decimal("76"))
    assert _remaining_percentage(Decimal("40"), Decimal("25")) == Decimal("62.500")
    assert _remaining_percentage(Decimal("0"), Decimal("0")) is None
    assert _remaining_percentage(None, Decimal("1")) is None
    try:
        _remaining_percentage(Decimal("40"), Decimal("41"))
    except ValueError:
        pass
    else:
        raise AssertionError("remaining above limit must fail closed")


def test_v2_config_grammar_is_explicit_and_v1_deadline_is_not_a_key():
    text = SPEC.read_text(encoding="utf-8")

    assert "The v2 configuration is one UTF-8 JSON object." in text
    assert "`deadline_seconds`, `codex`, and `opencode_go`" in text
    assert "`deadline_seconds` is not a v1 key" in text
    assert "`--output-version 2` or `=2`" in text
    assert "32,767 UTF-16 code units" in text
    assert "16,384 UTF-8 bytes" in text


def test_invalid_json_customwidget_fallback_is_copy_ready_and_stock_only():
    text = SPEC.read_text(encoding="utf-8")

    assert 'label: "Quota: {data}"' in text
    assert 'tooltip_label: "Quota: {data}"' in text
    assert 'return_format: json' in text
    assert 'hide_empty: true' in text
    assert "Active label | Tooltip | Visibility" in text
    assert "`Quota: None`" in text
    assert "Previous tooltip remains unchanged" in text
    assert "it does not promise dynamic CSS" in text
