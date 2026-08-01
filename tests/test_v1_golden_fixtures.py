import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from yasb_limitora.model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderSnapshotView,
    ProviderState,
    ProviderView,
    PublicProviderState,
    QuotaAvailability,
    QuotaMetricKind,
    QuotaQuantity,
    QuotaWindowKind,
    QuotaWindowView,
    SafeError,
    SafeErrorCode,
    SnapshotFreshness,
)
from yasb_limitora.projection import project_bytes
from yasb_limitora.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


def _view(provider, state, error=None, label=None):
    return ProviderView(provider, state, error, label)


@pytest.mark.parametrize(
    ("fixture", "document"),
    (
        (
            "json_v1_success.json",
            DocumentView.ordered(
                _view(ProviderKey.CODEX, ProviderState.SUCCESS),
                _view(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS),
            ),
        ),
        (
            "json_v1_unavailable.json",
            DocumentView.ordered(
                _view(ProviderKey.CODEX, ProviderState.UNAVAILABLE),
                _view(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE),
            ),
        ),
        (
            "json_v1_safe_error.json",
            DocumentView.ordered(
                _view(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT)),
                _view(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS),
            ),
        ),
        (
            "json_v1_unicode_label.json",
            DocumentView.ordered(
                _view(ProviderKey.CODEX, ProviderState.SUCCESS, label="Quota café"),
                _view(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE, label="Quota 日本"),
            ),
        ),
    ),
)
def test_v1_projection_matches_golden_bytes(fixture, document):
    expected = (FIXTURES / fixture).read_bytes()

    assert expected.endswith(b"\n")
    assert not expected.endswith(b"\n\n")
    assert project_bytes(document) == expected


def test_v2_structural_support_is_valid_json():
    schema = json.loads((Path(__file__).parents[1] / "docs/specifications/json-v2.schema.json").read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["version"] == {"const": 2}


def test_v1_no_argument_behavior_is_the_frozen_all_disabled_document():
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main((), environment={"YASB_LIMITORA_CONFIG": "must-not-be-read"}, stdout=stdout, stderr=stderr) == 0
    assert stdout.getvalue() == (FIXTURES / "json_v1_unavailable.json").read_bytes()
    assert stderr.getvalue() == ""


def test_v1_projection_ignores_rich_snapshot_fields():
    timestamp = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    quantity = QuotaQuantity(Decimal("100"), QuotaMetricKind.COMMERCIAL_QUOTA, "percentage_points")
    window = QuotaWindowView(
        QuotaWindowKind.COMMERCIAL_QUOTA,
        "account",
        "five_hour",
        "plus",
        QuotaAvailability.KNOWN,
        "codex-app-server-v2",
        limit=quantity,
        reset_at=datetime(2026, 8, 1, 16, tzinfo=timezone.utc),
    )
    snapshot = ProviderSnapshotView(
        PublicProviderState.AVAILABLE,
        SnapshotFreshness.FRESH,
        timestamp,
        timestamp,
        timestamp,
        "codex-app-server-v2",
        (window,),
    )
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, outcome=ProviderOutcome.SNAPSHOT, snapshot=snapshot),
        ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SUCCESS),
    )

    assert project_bytes(document) == (FIXTURES / "json_v1_success.json").read_bytes()
