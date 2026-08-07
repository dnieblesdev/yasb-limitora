import math

import pytest

import yasb_limitora.codex_job_resources as r
from yasb_limitora.isolation.windows_job import DEFAULT_CLEANUP_BUDGET_SECONDS, PROCESS_ACCESS, JobError, JobErrorCode, WAIT_OBJECT_0
from yasb_limitora.isolation.windows_job import WindowsJobBoundary
from yasb_limitora.v2_deadline import DeadlineContext

class Api:
    def __init__(self, **flags: object) -> None:
        self.flags, self.calls, self.closed = flags, [], []
        self.active = list(flags.get("active", [1, 0]))
    def create_job(self): self.calls.append("create"); return "job"
    def make_non_inheritable(self, handle): self.calls.append("inherit"); return not self.flags.get("inherit_fail")
    def enable_kill_on_close(self, handle): self.calls.append("limit"); return not self.flags.get("limit_fail")
    def open_process(self, pid, access):
        self.calls.append(("open", pid, access))
        if self.flags.get("open_error"): raise OSError("secret")
        return "process"
    def is_process_in_job(self, process, job):
        self.calls.append(("in_job", process, job))
        return bool(self.flags.get("nested")) if job is None else not self.flags.get("post_fail")
    def assign(self, job, process): self.calls.append(("assign", job, process)); return not self.flags.get("assign_fail")
    def query_active(self, job): self.calls.append("query"); return self.active.pop(0) if self.active else 0
    def terminate(self, job): self.calls.append("terminate"); return not self.flags.get("terminate_fail")
    def terminate_process(self, process): self.calls.append("terminate_process"); return True
    def wait(self, handle, timeout): self.calls.append(("wait", handle, timeout)); return WAIT_OBJECT_0
    def close(self, handle):
        self.closed.append(handle)
        if self.flags.get("close_fail_once"):
            self.flags["close_fail_once"] = False
            return False
        return not self.flags.get("close_fail")

def test_legacy_open_process_exact_args_and_exception_cleanup() -> None:
    api = Api(); boundary = WindowsJobBoundary(api=api)
    boundary.assign_process(42)
    assert ("open", 42, PROCESS_ACCESS) in api.calls
    error_api = Api(open_error=True)
    with pytest.raises(JobError) as error: WindowsJobBoundary(api=error_api).assign_process(42)
    assert error.value.code is JobErrorCode.INTERNAL_ERROR and error_api.closed == ["job"]

def test_job_setup_failure_returns_reachable_owner_for_retry() -> None:
    api = Api(limit_fail=True, close_fail=True)
    with pytest.raises(r._JobAcquisitionFailure) as error: r._acquire_job_owner(api)
    owner = error.value.owner
    assert owner is not None and owner._handle == "job" and "terminate" in api.calls and repr(error.value) == "<_JobAcquisitionFailure>"
    api.flags["close_fail"] = False
    owner.close(); owner.close()
    assert owner._state is r._OwnerState.CLOSED and api.closed == ["job", "job"]
    with pytest.raises(r._JobAcquisitionFailure) as clean:
        r._acquire_job_owner(Api(limit_fail=True))
    assert clean.value.owner is None

def test_borrowed_handle_assignment_uses_exact_handle_and_never_closes_it() -> None:
    api, borrowed = Api(), object(); boundary = WindowsJobBoundary(api=api)
    boundary.assign_borrowed_handle(borrowed)
    assert ("assign", "job", borrowed) in api.calls and ("in_job", borrowed, None) in api.calls
    boundary.close(1.0)
    assert ("in_job", borrowed, "job") in api.calls and any(call[0] == "wait" and call[1] is borrowed for call in api.calls if isinstance(call, tuple))
    assert borrowed not in api.closed and api.closed == ["job"]

@pytest.mark.parametrize("flags", [{"assign_fail": True}, {"post_fail": True, "terminate_fail": True}])
def test_borrowed_pre_post_failure_never_closes_caller_handle(flags: dict[str, object]) -> None:
    api, borrowed = Api(**flags), object(); boundary = WindowsJobBoundary(api=api)
    with pytest.raises(JobError): boundary.assign_borrowed_handle(borrowed)
    assert borrowed not in api.closed
    if flags.get("assign_fail"):
        assert "terminate_process" not in api.calls
    else:
        assert "terminate" in api.calls and boundary.process is borrowed and boundary.borrowed_process

def test_assigned_borrowed_cleanup_waits_exact_handle_and_retries_job_close() -> None:
    api, borrowed = Api(close_fail_once=True), object(); boundary = WindowsJobBoundary(api=api)
    boundary.assign_borrowed_handle(borrowed)
    with pytest.raises(JobError): boundary.close(1.0)
    assert boundary.process is borrowed and boundary.borrowed_process and borrowed not in api.closed
    boundary.close(1.0); boundary.close(1.0)
    assert boundary.state.value == "closed" and boundary.process is None and api.closed == ["job", "job"]
    waits = [call for call in api.calls if isinstance(call, tuple) and call[0] == "wait"]
    assert len(waits) == 2 and all(call[1] is borrowed and 0 < call[2] <= 1000 for call in waits)

@pytest.mark.parametrize("value", [None, "bad", True, math.nan, math.inf, -1])
def test_invalid_timeout_uses_emergency_cleanup_and_surfaces_timeout(value: object) -> None:
    api = Api(); boundary = WindowsJobBoundary(api=api); boundary.assign_process(1)
    with pytest.raises(JobError) as error: boundary.close(value)
    assert error.value.code is JobErrorCode.TIMEOUT and boundary.state.value == "closed"

def test_custom_float_is_rejected_without_invocation_and_wrapper_closes_consistently() -> None:
    class SecretFloat:
        called = False
        def __float__(self):
            self.called = True
            raise RuntimeError("secret-timeout")
    api, borrowed, value = Api(), object(), SecretFloat()
    owner = r._JobOwner(WindowsJobBoundary(api=api))
    owner.assign_borrowed_handle(borrowed)
    with pytest.raises(JobError) as error: owner.close(value)
    assert not value.called and str(error.value) == "timeout" and owner._state is r._OwnerState.CLOSED
    assert "terminate" in api.calls and any(call[0] == "wait" and call[1] is borrowed for call in api.calls if isinstance(call, tuple)) and "query" in api.calls and api.closed == ["job"]
    assert DEFAULT_CLEANUP_BUDGET_SECONDS == 2.0

def test_huge_finite_timeout_is_clamped_before_millisecond_conversion() -> None:
    api = Api(); boundary = WindowsJobBoundary(api=api); boundary.assign_process(1)
    boundary.close(10**300)
    waits = [call for call in api.calls if isinstance(call, tuple) and call[0] == "wait"]
    assert waits and waits[0][2] > 0

def test_job_owner_close_is_retryable_and_redacted() -> None:
    owner = r._JobOwner(WindowsJobBoundary._from_owned_job(Api(), "job"))
    assert repr(owner) == "<_JobOwner>" and repr(r._JobCleanupError()) == "<_JobCleanupError>"
    owner.close(); owner.close()
    assert owner._state is r._OwnerState.CLOSED

def test_job_owner_v2_close_uses_real_boundary_deadline_adapter() -> None:
    api, borrowed = Api(), object()
    owner = r._JobOwner(WindowsJobBoundary(api=api))
    owner.assign_borrowed_handle(borrowed)
    context = DeadlineContext(t0_ns=0, deadline_ns=1_000_000_000, reserve_ns=250_000_000, clock_ns=lambda: 0)

    owner.close_with_deadline(context)

    assert owner._state is r._OwnerState.CLOSED
    assert api.closed == ["job"]
    assert any(call[0] == "wait" and call[1] is borrowed for call in api.calls if isinstance(call, tuple))

def test_private_job_module_has_no_popen_or_ipc_surface() -> None:
    assert r.__all__ == () and not hasattr(r, "Popen") and not hasattr(r, "_PopenProcessOwner") and not hasattr(r, "_IpcPair")
