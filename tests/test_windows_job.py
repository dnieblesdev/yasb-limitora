import ctypes
import os

import pytest

from yasb_limitora.isolation.windows_job import (
    ACTIVE_PROCESS_INFO, BASIC_LIMIT_INFO, CLEANUP_ERROR, DWORD, EXTENDED_LIMIT_INFO, IO_COUNTERS,
    JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, MAX_WAIT_MILLISECONDS,
    MILLISECONDS_PER_SECOND, PROCESS_ACCESS, PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SET_QUOTA,
    PROCESS_TERMINATE, SYNCHRONIZE, WAIT_FAILED, WAIT_OBJECT_0, WAIT_TIMEOUT,
    JobError, JobErrorCode, JobState, WindowsJobBoundary,
)
class Clock:
    def __init__(self) -> None: self.value = 0.0
    def __call__(self) -> float:
        self.value += 0.01
        return self.value
class BudgetClock(Clock):
    def __call__(self) -> float: return self.value
class FakeApi:
    def __init__(self, **flags: object) -> None:
        self.flags, self.closed, self.calls = flags, [], []
        self.active_values, self.wait_results = list(flags.get("active_values", [1, 0])), list(flags.get("wait_results", []))

    def create_job(self): self.calls.append("create"); return None if self.flags.get("create_fail") else "job"
    def make_non_inheritable(self, handle): self.calls.append("inherit"); return not self.flags.get("inherit_fail")
    def enable_kill_on_close(self, handle):
        self.calls.append("limit")
        if self.flags.get("limit_error"): raise OSError("secret kernel path PID=999999")
        return not self.flags.get("limit_fail")
    def open_process(self, pid, access): self.calls.append(("open", pid, access)); return None if self.flags.get("open_fail") else "process"
    def is_process_in_job(self, process, job):
        self.calls.append(("in_job", job))
        if job is None: return bool(self.flags.get("nested"))
        return not self.flags.get("post_check_fail")
    def assign(self, job, process): self.calls.append("assign"); return not self.flags.get("assign_fail")
    def query_active(self, job):
        self.calls.append("query")
        if self.flags.get("query_fail"): raise JobError(JobErrorCode.INTERNAL_ERROR)
        return self.active_values.pop(0) if self.active_values else 0
    def terminate(self, job): self.calls.append("terminate"); return not self.flags.get("terminate_fail")
    def terminate_process(self, process): self.calls.append("terminate_process"); return not self.flags.get("terminate_process_fail")
    def wait(self, handle, timeout_ms):
        if self.flags.get("advance_clock"): self.flags["advance_clock"].value += 0.01
        self.calls.append(("wait", handle, timeout_ms)); return self.wait_results.pop(0) if self.wait_results else self.flags.get("wait_result", WAIT_OBJECT_0)
    def close(self, handle):
        self.closed.append(handle)
        if self.flags.get("close_fail_once") == handle:
            self.flags["close_fail_once"] = None
            return False
        return not self.flags.get("close_fail")
def boundary(api: FakeApi, clock: Clock | None = None) -> WindowsJobBoundary: return WindowsJobBoundary(api=api, clock=clock or Clock())
def test_abi_structures_and_non_windows_fail_closed() -> None:
    assert [name for name, _ in BASIC_LIMIT_INFO._fields_] == ["PerProcessUserTimeLimit", "PerJobUserTimeLimit", "LimitFlags", "MinimumWorkingSetSize", "MaximumWorkingSetSize", "ActiveProcessLimit", "Affinity", "PriorityClass", "SchedulingClass"]
    assert [name for name, _ in EXTENDED_LIMIT_INFO._fields_] == ["BasicLimitInformation", "IoInfo", "ProcessMemoryLimit", "JobMemoryLimit", "PeakProcessMemoryUsed", "PeakJobMemoryUsed"]
    assert [name for name, _ in ACTIVE_PROCESS_INFO._fields_] == ["TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime", "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses"]
    pointer = ctypes.sizeof(ctypes.c_void_p)
    assert pointer in (4, 8) and ctypes.sizeof(DWORD) == 4 and ctypes.sizeof(ACTIVE_PROCESS_INFO) == 32 + 4 * 4
    assert EXTENDED_LIMIT_INFO.BasicLimitInformation.offset == 0
    assert EXTENDED_LIMIT_INFO.IoInfo.offset == ctypes.sizeof(BASIC_LIMIT_INFO)
    assert EXTENDED_LIMIT_INFO.ProcessMemoryLimit.offset == EXTENDED_LIMIT_INFO.IoInfo.offset + ctypes.sizeof(IO_COUNTERS)
    assert ctypes.sizeof(EXTENDED_LIMIT_INFO) == EXTENDED_LIMIT_INFO.ProcessMemoryLimit.offset + 4 * pointer
    assert JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION == 1 and JOB_OBJECT_EXTENDED_LIMIT_INFORMATION == 9
    if os.name != "nt":
        with pytest.raises(JobError) as error: WindowsJobBoundary()
        assert error.value.code is JobErrorCode.UNSUPPORTED_PLATFORM
def test_access_mask_and_containment_order_before_authorization() -> None:
    api = FakeApi()
    job = boundary(api)
    job.assign_process(42)
    assert next(call for call in api.calls if isinstance(call, tuple) and call[0] == "open") == ("open", 42, PROCESS_ACCESS)
    assert PROCESS_ACCESS == PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
    assert api.calls.index("assign") < api.calls.index(("in_job", "job")) < api.calls.index("query")
    job.authorize()
    assert job.state is JobState.AUTHORIZED
@pytest.mark.parametrize("flags, code", [
    ({"assign_fail": True}, JobErrorCode.ASSIGNMENT_FAILED),
    ({"post_check_fail": True}, JobErrorCode.ASSIGNMENT_FAILED),
    ({"active_values": [0]}, JobErrorCode.ASSIGNMENT_FAILED),
    ({"query_fail": True}, JobErrorCode.INTERNAL_ERROR),
    ({"nested": True}, JobErrorCode.NESTED_JOB),
    ({"open_fail": True}, JobErrorCode.HANDLE_FAILED),
])
def test_each_containment_check_failure_cleans_and_never_authorizes(flags: dict[str, object], code: JobErrorCode) -> None:
    api = FakeApi(**flags)
    if flags.get("query_fail"): api.flags["query_fail"] = False
    job = boundary(api)
    if flags.get("query_fail"): api.flags["query_fail"] = True
    with pytest.raises(JobError) as error: job.assign_process(999999)
    assert error.value.code is code
    with pytest.raises(JobError): job.authorize()
    assert "terminate" in api.calls
def test_success_cleanup_terminates_waits_accounts_and_is_idempotent() -> None:
    clock = BudgetClock(); api = FakeApi(active_values=[1, 0], wait_results=[WAIT_TIMEOUT, WAIT_OBJECT_0], advance_clock=clock)
    job = boundary(api, clock)
    job.assign_process(1)
    job.close(1.0)
    job.close(1.0)
    waits = [call for call in api.calls if isinstance(call, tuple) and call[0] == "wait"]
    assert job.state is JobState.CLOSED and api.calls.count("terminate") == 1 and api.closed == ["process", "job"]
    assert {call[1] for call in waits} == {"process"} and waits[0][2] > waits[1][2] > 0 and all(call[2] <= MAX_WAIT_MILLISECONDS for call in waits)
    assert clock.value <= 1.0
@pytest.mark.parametrize("flags, code, closed, retry", [({"terminate_fail": True}, CLEANUP_ERROR, ["process"], True), ({"query_fail": True}, CLEANUP_ERROR, ["process"], False), ({"wait_result": WAIT_FAILED}, CLEANUP_ERROR, [], False), ({"wait_result": WAIT_TIMEOUT, "active_values": [1] * 200}, JobErrorCode.TIMEOUT, [], True)])
def test_cleanup_failures_retain_failed_ownership(flags: dict[str, object], code: JobErrorCode, closed: list[str], retry: bool) -> None:
    api = FakeApi(**flags)
    if flags.get("query_fail"): api.flags["query_fail"] = False
    job = boundary(api)
    job.assign_process(1)
    if flags.get("query_fail"): api.flags["query_fail"] = True
    with pytest.raises(JobError) as error: job.close(0.05)
    assert error.value.code is code and api.closed == closed and job.state is JobState.BROKEN and (flags.get("wait_result") != WAIT_TIMEOUT or job.process == "process") and (not flags.get("terminate_fail") or job.job == "job")
    with pytest.raises(JobError): job.assign_process(2)
    assert not any(call[1] == 2 for call in api.calls if isinstance(call, tuple) and call[0] == "open")
    if retry:
        api.flags.update(terminate_fail=False, wait_result=WAIT_OBJECT_0); api.active_values = [0]
        job.close(1.0)
        assert job.state is JobState.CLOSED
    if not retry:
        with pytest.raises(JobError): job.close(0.05)
    assert api.closed.count("process") <= 1 and api.closed.count("job") <= 1
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_invalid_cleanup_timeout_still_cleans_and_maps_to_timeout(value: float) -> None:
    api = FakeApi(active_values=[1, 0])
    job = boundary(api)
    job.assign_process(1)
    with pytest.raises(JobError) as error: job.close(value)
    assert error.value.code is JobErrorCode.TIMEOUT and "terminate" in api.calls and api.closed == ["process", "job"]
@pytest.mark.parametrize("handle", ["process", "job"])
def test_close_handle_failure_retains_only_failed_ownership_for_retry(handle: str) -> None:
    api = FakeApi(active_values=[1, 0, 0], close_fail_once=handle)
    job = boundary(api)
    job.assign_process(1)
    with pytest.raises(JobError): job.close(1.0)
    assert job.state is not JobState.CLOSED and getattr(job, handle) == handle
    job.close(1.0)
    assert job.state is JobState.CLOSED and api.closed.count(handle) == 2
    other = "job" if handle == "process" else "process"
    assert api.closed.count(other) == 1
def test_partial_setup_uses_process_termination_before_assignment_and_redacts_os_details() -> None:
    api = FakeApi(limit_error=True)
    with pytest.raises(JobError) as error: boundary(api)
    assert error.value.code is JobErrorCode.INTERNAL_ERROR and api.closed == ["job"] and "999999" not in str(error.value) and "secret" not in str(error.value)
def test_unassigned_partial_failure_terminates_retained_process_and_waits() -> None:
    api = FakeApi(assign_fail=True, terminate_process_fail=True)
    job = boundary(api)
    with pytest.raises(JobError): job.assign_process(1)
    assert api.calls.index("terminate_process") < api.calls.index("terminate")
    assert {call[1] for call in api.calls if isinstance(call, tuple) and call[0] == "wait"} == {"process"}
    assert job.state is JobState.BROKEN and job.process == "process"
    api.flags["terminate_process_fail"] = False
    job.close(1.0)
    assert job.state is JobState.CLOSED and api.closed.count("process") == 1
