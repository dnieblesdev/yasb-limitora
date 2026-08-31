import json
import re
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "docs/specifications/json-v2.md"
SCHEMA = ROOT / "docs/specifications/json-v2.schema.json"

DOCUMENT_FIELD_ORDER = ("version", "execution_state", "execution_error", "providers")
PROVIDER_FIELD_ORDER = (
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
WINDOW_FIELD_ORDER = (
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
DEPLETED_WINDOW_FIELD_ORDER = (
    "kind",
    "scope",
    "period",
    "plan_id",
    "unit",
    "source_id",
    "remaining_percentage",
)
QUANTITY_FIELD_ORDER = ("value", "metric", "unit")
PROVIDER_FIELDS = set(PROVIDER_FIELD_ORDER)
WINDOW_KIND_ORDER = {"commercial_quota": 0, "technical_rate_limit": 1, "other": 2}


def _window_identity(window):
    return tuple(window[field] for field in ("kind", "scope", "period", "plan_id", "source_id"))


def _window_sort_key(window):
    return (
        WINDOW_KIND_ORDER[window["kind"]],
        window["scope"],
        window["period"],
        window["plan_id"] is not None,
        window["plan_id"] or "",
        window["source_id"] is not None,
        window["source_id"] or "",
    )


def _expected_snapshot_presentation(provider):
    basis = provider["most_depleted_window"]
    if basis is None:
        value = "percentage unavailable"
        alternate_base = "Quota percentage unavailable"
        basis_identity = None
    else:
        value = f"{basis['remaining_percentage']}% remaining"
        alternate_base = f"Quota {basis['scope']} / {basis['period']}: {value}"
        basis_identity = _window_identity(basis)

    qualifier = f"; state={provider['public_state']}; freshness={provider['freshness']}"
    compact = f"Quota {value}{qualifier}"
    alternate = f"{alternate_base}{qualifier}"
    lines = [
        f"State: {provider['public_state']}",
        f"Freshness: {provider['freshness']}",
        f"Quota: {value}",
    ]
    if basis is None:
        lines.append("No eligible percentage basis")
    for window in sorted(provider["windows"], key=_window_sort_key):
        units = {
            quantity["unit"]
            for quantity in (window["limit"], window["used"], window["remaining"])
            if quantity is not None
        }
        unit = next(iter(units)) if len(units) == 1 else "null"
        if _window_identity(window) == basis_identity:
            result = f"{basis['remaining_percentage']}% remaining"
        elif window["availability"] == "known":
            result = "percentage unavailable"
        else:
            result = f"availability={window['availability']}"
        lines.append(
            f"Window: kind={window['kind']}; scope={window['scope']}; period={window['period']}; "
            f"plan_id={json.dumps(window['plan_id'], ensure_ascii=False)}; unit={unit}; "
            f"source_id={json.dumps(window['source_id'], ensure_ascii=False)}; result={result}"
        )
        if window["reset_at"] is not None:
            lines.append(f"Reset: {window['reset_at']}")
    return compact, alternate, "\n".join(lines)


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
    expected_source = {"codex": "codex-app-server-v2", "opencode_go": "opencode-go-api"}[provider["provider"]]
    assert provider["source_id"] in (expected_source, None)
    assert all(window["source_id"] in (expected_source, None) and (window["source_id"] is not None or (window["availability"] == "unavailable" and all(window[field] is None for field in ("limit", "used", "remaining", "reset_at")))) for window in provider["windows"])
    assert provider["most_depleted_window"] is None or provider["most_depleted_window"]["source_id"] in (expected_source, None)

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


def test_r6_examples_use_the_exact_snapshot_presentation_grammar():
    examples = _v2_examples()

    codex = examples[0]["providers"][0]
    assert codex["compact_text"] == "Quota 75% remaining; state=available; freshness=fresh"
    assert codex["alternate_text"] == "Quota account / five_hour: 75% remaining; state=available; freshness=fresh"
    assert codex["tooltip_text"] == (
        'State: available\nFreshness: fresh\nQuota: 75% remaining\n'
        'Window: kind=commercial_quota; scope=account; period=five_hour; plan_id="plus"; '
        'unit=percentage_points; source_id="codex-app-server-v2"; result=75% remaining\n'
        "Reset: 2026-08-01T16:00:00.000000Z"
    )

    stale = examples[1]["providers"][0]
    assert stale["compact_text"] == "Quota 10% remaining; state=partial; freshness=stale"
    assert stale["alternate_text"] == "Quota account / five_hour: 10% remaining; state=partial; freshness=stale"
    assert "State: partial\nFreshness: stale\nQuota: 10% remaining\n" in stale["tooltip_text"]
    assert "result=availability=unavailable" in stale["tooltip_text"]
    assert (
        'period=weekly; plan_id="plus"; unit=null; '
        'source_id="codex-app-server-v2"; result=availability=unavailable'
    ) in stale["tooltip_text"]

    for example_index, state in ((4, "rate_limited"), (14, "unavailable")):
        provider = examples[example_index]["providers"][1 if example_index == 4 else 0]
        expected = f"Quota percentage unavailable; state={state}; freshness=fresh"
        assert provider["compact_text"] == expected
        assert provider["alternate_text"] == expected
        assert provider["tooltip_text"] == (
            f"State: {state}\nFreshness: fresh\n"
            "Quota: percentage unavailable\nNo eligible percentage basis"
        )


def test_r6_parsed_snapshot_examples_lock_every_presentation_string():
    for example in _v2_examples():
        for provider in example["providers"]:
            if provider["outcome"] != "snapshot":
                continue
            assert (provider["compact_text"], provider["alternate_text"], provider["tooltip_text"]) == (
                _expected_snapshot_presentation(provider)
            )


def test_r6_parsed_examples_lock_all_non_snapshot_fallbacks_and_mappings():
    not_run_text = {
        "disabled": "provider disabled",
        "invalid_configuration": "configuration invalid",
        "invocation_invalid": "invocation invalid",
        "document_aborted": "document aborted",
    }

    for example in _v2_examples():
        for provider in example["providers"]:
            outcome = provider["outcome"]
            if outcome == "undetected":
                expected = "Quota not detected"
            elif outcome == "not_run":
                expected = "Quota not run"
                reason_text = not_run_text.get(provider["not_run_reason"])
                if reason_text is None:
                    continue
                assert provider["tooltip_text"] == f"{expected}: {reason_text}"
            else:
                if outcome != "execution_error":
                    continue
                expected = "Quota error"
            assert provider["compact_text"] == expected
            assert provider["alternate_text"] == expected


def test_r6_parsed_examples_lock_canonical_window_order_and_nullable_identities():
    for example in _v2_examples():
        for provider in example["providers"]:
            if provider["outcome"] != "snapshot":
                continue
            windows = provider["windows"]
            assert windows == sorted(windows, key=_window_sort_key)
            tooltip_windows = [line for line in provider["tooltip_text"].splitlines() if line.startswith("Window: ")]
            assert len(tooltip_windows) == len(windows)
            for window, line in zip(windows, tooltip_windows):
                assert f"plan_id={json.dumps(window['plan_id'], ensure_ascii=False)}" in line
                assert f"source_id={json.dumps(window['source_id'], ensure_ascii=False)}" in line


def test_r6_tied_parsed_windows_choose_the_canonical_sort_winner():
    provider = deepcopy(_v2_examples()[0]["providers"][0])
    first = provider["windows"][0]
    tied = deepcopy(first)
    tied["period"] = "weekly"
    tied["reset_at"] = None

    assert [window["period"] for window in sorted((tied, first), key=_window_sort_key)] == ["five_hour", "weekly"]
    assert min((tied, first), key=_window_sort_key)["period"] == "five_hour"


def test_r6_parsed_examples_obey_presentation_scalar_bounds():
    for example in _v2_examples():
        for provider in example["providers"]:
            assert len(provider["compact_text"]) <= 128
            assert len(provider["alternate_text"]) <= 128
            assert len(provider["tooltip_text"]) <= 4096


def test_r6_fallback_mappings_and_exclusions_are_normative():
    text = SPEC.read_text(encoding="utf-8")

    for fragment in (
        "`not_run` uses `Quota not run` in compact/alternate",
        "`execution_error` uses\n`Quota error` in the trio and tooltip",
        "`disabled -> provider disabled`",
        "`invalid_configuration -> configuration\ninvalid`",
        "`invocation_invalid -> invocation invalid`",
        "`document_aborted ->\ndocument aborted`",
        "`timeout -> provider_timeout`",
        "`invalid_provider_data -> invalid_provider_data`",
        "`unknown_provider_state -> unknown_provider_state`",
        "the aggregate remains `provider_failed`",
        "Missing evidence remains missing: no\nsynthetic value, zero, reset, identity, or raw error",
        "Partial snapshots preserve `state=partial`; stale snapshots preserve",
        "R6 changes no existing v2 fields,\nschema, model, object-key order",
        "no new\nsynthetic windows, percentages, resets, plans, periods, severity, CSS/classes",
    ):
        assert fragment in text

    examples = _v2_examples()
    assert examples
    assert examples[2]["providers"][0]["tooltip_text"] == "Quota not detected"
    assert examples[5]["providers"][0]["tooltip_text"] == "Quota not run: provider disabled"
    assert examples[6]["providers"][0]["tooltip_text"] == "Quota not run: configuration invalid"
    assert examples[7]["providers"][0]["tooltip_text"] == "Quota not run: invocation invalid"
    assert examples[9]["providers"][0]["tooltip_text"] == "Quota not run: document aborted"
    assert examples[4]["providers"][0]["tooltip_text"] == "Quota error"


def test_pr2b_schema_and_spec_declare_provider_bound_api_sources():
    schema = _schema()
    assert schema["$defs"]["sourceId"]["enum"] == ["codex-app-server-v2", "opencode-go-api", None]
    assert {
        "credential_invalid",
        "provider_timeout",
        "provider_rate_limited",
        "provider_unavailable",
    } <= set(schema["$defs"]["executionError"]["properties"]["code"]["enum"])
    text = SPEC.read_text(encoding="utf-8")
    assert "`credential_invalid`" in text
    assert "`provider_rate_limited`" in text
    assert "`provider_unavailable`" in text
    assert "the aggregate remains `provider_failed`" in text
    assert "OpenCode accepts only `opencode-go-api`" in text
    assert "numeric quantities from a window" in text
    codex_rules = schema["$defs"]["codexProvider"]["allOf"]
    codex_source_rule = codex_rules[2]["properties"]
    assert codex_source_rule["source_id"] == {"enum": ["codex-app-server-v2", None]}
    codex_window_source_rule = codex_source_rule["windows"]["items"]["allOf"][1]["properties"]
    assert codex_window_source_rule["source_id"] == {"enum": ["codex-app-server-v2", None]}; assert codex_source_rule["most_depleted_window"]["anyOf"][1]["properties"]["source_id"] == {"enum": ["codex-app-server-v2", None]}
    assert "opencode-go-api" not in codex_source_rule["source_id"]["enum"]
    opencode_rules = schema["$defs"]["opencodeProvider"]["allOf"]
    source_rule = opencode_rules[2]["properties"]
    assert source_rule["source_id"] == {"enum": ["opencode-go-api", None]}
    window_source_rule = source_rule["windows"]["items"]["allOf"][1]["properties"]
    assert window_source_rule["source_id"] == {"enum": ["opencode-go-api", None]}
    source_null_rule = next(rule for rule in schema["$defs"]["window"]["allOf"] if rule.get("if", {}).get("properties", {}).get("source_id", {}).get("type") == "null")
    assert source_null_rule["then"]["properties"]["plan_id"] == {"type": "null"}
    assert source_rule["most_depleted_window"]["anyOf"][1]["properties"]["source_id"] == {"enum": ["opencode-go-api", None]}
    invalid = deepcopy(_v2_examples()[0]["providers"][0])
    invalid["windows"][0]["source_id"] = None
    with pytest.raises(AssertionError): _assert_provider(invalid)
    invalid["windows"][0]["source_id"] = "opencode-go-api"
    with pytest.raises(AssertionError): _assert_provider(invalid)
    invalid["windows"][0]["source_id"] = "codex-app-server-v2"; invalid["most_depleted_window"]["source_id"] = "opencode-go-api"
    with pytest.raises(AssertionError): _assert_provider(invalid)


def test_r6_tooltip_identity_escaping_rule_is_normative():
    text = SPEC.read_text(encoding="utf-8")

    for fragment in (
        "identity is rendered as its existing raw text. An identity containing `;`, `=`,",
        "or backslash is instead rendered as a JSON string using the same",
        "Unicode-preserving escaping as canonical JSON",
        "making every `key=value;` boundary\nunambiguous",
        "same escaped representation is used for those identities in",
        "does not alter the underlying identity or invent a replacement\nvalue",
    ):
        assert fragment in text


def test_r6_near_cap_presentation_budget_and_boundary_fallback_are_normative():
    text = SPEC.read_text(encoding="utf-8")

    for fragment in (
        "The 65,536-byte document limit is applied after the complete canonical JSON v2",
        "one deterministic,\ndocument-local tooltip scalar budget shared by all snapshot providers",
        "MUST NOT remove or alter canonical `windows` evidence",
        "The largest budget whose encoded document fits MUST be selected",
        "valid near-cap document remains a provider snapshot at exactly 65,535 and\n65,536 bytes",
        "only a genuinely over-cap document becomes a document failure",
    ):
        assert fragment in text


def test_r6_preserves_schema_and_canonical_field_order():
    schema = _schema()
    assert tuple(schema["properties"]) == DOCUMENT_FIELD_ORDER
    assert tuple(schema["$defs"]["providerBase"]["properties"]) == PROVIDER_FIELD_ORDER
    assert tuple(schema["$defs"]["window"]["properties"]) == WINDOW_FIELD_ORDER
    assert tuple(schema["$defs"]["quantity"]["properties"]) == QUANTITY_FIELD_ORDER
    assert tuple(schema["$defs"]["depletedWindow"]["properties"]) == DEPLETED_WINDOW_FIELD_ORDER

    for document in _v2_examples():
        assert tuple(document) == DOCUMENT_FIELD_ORDER
        for provider in document["providers"]:
            assert tuple(provider) == PROVIDER_FIELD_ORDER
            for window in provider["windows"]:
                assert tuple(window) == WINDOW_FIELD_ORDER
            if provider["most_depleted_window"] is not None:
                assert tuple(provider["most_depleted_window"]) == DEPLETED_WINDOW_FIELD_ORDER


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
