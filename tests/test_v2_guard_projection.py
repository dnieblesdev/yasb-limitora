import json

from yasb_limitora.model import DocumentView, ProviderKey, ProviderOutcome, ProviderState, ProviderView, SafeError, SafeErrorCode, V2SafeErrorCode
from yasb_limitora.projection_v2 import V2ProjectionInput, project_v2_bytes


def _not_run(provider, reason):
    return ProviderView(provider, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason)


def test_guard_wait_and_deadline_documents_are_not_run_matrices():
    for reason, code, phase, text in (("guard_wait_timeout", "guard_wait_timeout", "guard_wait", "guard wait timeout"), ("deadline_exhausted", "deadline_exhausted", "document", "deadline exhausted")):
        error = V2SafeErrorCode.GUARD_WAIT_TIMEOUT if reason == "guard_wait_timeout" else V2SafeErrorCode.DEADLINE_EXHAUSTED
        document = DocumentView.ordered(_not_run(ProviderKey.CODEX, reason), _not_run(ProviderKey.OPENCODE_GO, reason), SafeError(error))
        projected = json.loads(project_v2_bytes(V2ProjectionInput(document)))
        assert projected["execution_state"] == "not_run"
        assert projected["execution_error"] == {"code": code, "phase": phase}
        assert all(item["not_run_reason"] == reason and item["tooltip_text"] == f"Quota not run: {text}" for item in projected["providers"])


def test_cleanup_failure_preserves_mixed_provider_outcomes():
    document = DocumentView.ordered(
        ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.PROVIDER_ERROR), outcome=ProviderOutcome.EXECUTION_ERROR),
        _not_run(ProviderKey.OPENCODE_GO, "deadline_exhausted"), SafeError(V2SafeErrorCode.CLEANUP_FAILED),
    )
    projected = json.loads(project_v2_bytes(V2ProjectionInput(document)))
    assert projected["execution_error"] == {"code": "cleanup_failed", "phase": "cleanup"}
    assert projected["providers"][1]["not_run_reason"] == "deadline_exhausted"
