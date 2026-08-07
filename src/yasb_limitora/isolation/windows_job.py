"""Fail-closed native Windows Job Object ownership and cleanup boundary."""
import ctypes
from ctypes import wintypes
from enum import Enum
import math
import os
import time
from typing import Any, Protocol
DWORD = ctypes.c_uint32
HANDLE = wintypes.HANDLE
LARGE_INTEGER = ctypes.c_longlong
SIZE_T = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
PROCESS_ACCESS = PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
HANDLE_FLAG_INHERIT = 0x1
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
WAIT_FAILED = 0xFFFFFFFF
MIN_WAIT_MILLISECONDS, MAX_WAIT_MILLISECONDS = 1, 0xFFFFFFFE
MILLISECONDS_PER_SECOND = 1000
MIN_ACTIVE_PROCESSES, TERMINATION_EXIT_CODE = 1, 1
DEFAULT_CLEANUP_BUDGET_SECONDS = 2.0
EMERGENCY_CLEANUP_BUDGET_SECONDS = 1.0
MAX_CLEANUP_SECONDS = MAX_WAIT_MILLISECONDS / MILLISECONDS_PER_SECOND
INVALID_HANDLE = ctypes.c_void_p(-1).value
class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
class BASIC_LIMIT_INFO(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", LARGE_INTEGER), ("PerJobUserTimeLimit", LARGE_INTEGER), ("LimitFlags", DWORD), ("MinimumWorkingSetSize", SIZE_T), ("MaximumWorkingSetSize", SIZE_T), ("ActiveProcessLimit", DWORD), ("Affinity", ULONG_PTR), ("PriorityClass", DWORD), ("SchedulingClass", DWORD)]
class EXTENDED_LIMIT_INFO(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT_INFO), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", SIZE_T), ("JobMemoryLimit", SIZE_T), ("PeakProcessMemoryUsed", SIZE_T), ("PeakJobMemoryUsed", SIZE_T)]
class ACTIVE_PROCESS_INFO(ctypes.Structure):
    _fields_ = [("TotalUserTime", LARGE_INTEGER), ("TotalKernelTime", LARGE_INTEGER), ("ThisPeriodTotalUserTime", LARGE_INTEGER), ("ThisPeriodTotalKernelTime", LARGE_INTEGER), ("TotalPageFaultCount", DWORD), ("TotalProcesses", DWORD), ("ActiveProcesses", DWORD), ("TotalTerminatedProcesses", DWORD)]
class JobErrorCode(str, Enum):
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    HANDLE_FAILED = "handle_failed"
    ASSIGNMENT_FAILED = "assignment_failed"
    NESTED_JOB = "nested_job"
    INTERNAL_ERROR = "internal_error"
    INVALID_STATE = "invalid_state"
    TIMEOUT = "timeout"
CLEANUP_ERROR = JobErrorCode.INTERNAL_ERROR
class JobError(RuntimeError):
    def __init__(self, code: JobErrorCode) -> None:
        self.code = JobErrorCode(code)
        super().__init__(self.code.value)
class JobState(str, Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    AUTHORIZED = "authorized"
    CLOSED = "closed"
    BROKEN = "broken"
class NativeApi(Protocol):
    def create_job(self): ...
    def make_non_inheritable(self, handle) -> bool: ...
    def enable_kill_on_close(self, handle) -> bool: ...
    def open_process(self, pid: int, access: int): ...
    def is_process_in_job(self, process, job) -> bool: ...
    def assign(self, job, process) -> bool: ...
    def query_active(self, job) -> int: ...
    def terminate(self, job) -> bool: ...
    def terminate_process(self, process) -> bool: ...
    def wait(self, handle, timeout_ms: int) -> int: ...
    def close(self, handle) -> bool: ...
def _win_failure(code: JobErrorCode) -> None:
    try:
        ctypes.WinError(ctypes.get_last_error())
    except OSError:
        pass
    raise JobError(code) from None
class Kernel32Api:
    def __init__(self, dll: Any) -> None:
        self.dll = dll
        self.CreateJobObjectW = self._bind("CreateJobObjectW", HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR])
        self.SetHandleInformation = self._bind("SetHandleInformation", wintypes.BOOL, [HANDLE, DWORD, DWORD])
        self.SetInformationJobObject = self._bind("SetInformationJobObject", wintypes.BOOL, [HANDLE, ctypes.c_int, ctypes.c_void_p, DWORD])
        self.OpenProcess = self._bind("OpenProcess", HANDLE, [DWORD, wintypes.BOOL, DWORD])
        self.IsProcessInJob = self._bind("IsProcessInJob", wintypes.BOOL, [HANDLE, HANDLE, ctypes.POINTER(wintypes.BOOL)])
        self.AssignProcessToJobObject = self._bind("AssignProcessToJobObject", wintypes.BOOL, [HANDLE, HANDLE])
        self.QueryInformationJobObject = self._bind("QueryInformationJobObject", wintypes.BOOL, [HANDLE, ctypes.c_int, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD)])
        self.TerminateJobObject = self._bind("TerminateJobObject", wintypes.BOOL, [HANDLE, wintypes.UINT])
        self.TerminateProcess = self._bind("TerminateProcess", wintypes.BOOL, [HANDLE, wintypes.UINT])
        self.WaitForSingleObject = self._bind("WaitForSingleObject", DWORD, [HANDLE, DWORD])
        self.CloseHandle = self._bind("CloseHandle", wintypes.BOOL, [HANDLE])

    @classmethod
    def load(cls) -> "Kernel32Api":
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            raise JobError(JobErrorCode.UNSUPPORTED_PLATFORM)
        try:
            return cls(ctypes.WinDLL("kernel32", use_last_error=True))
        except Exception:
            raise JobError(JobErrorCode.INTERNAL_ERROR) from None
    def _bind(self, name: str, restype: Any, argtypes: list[Any]) -> Any:
        fn = getattr(self.dll, name)
        fn.argtypes, fn.restype = argtypes, restype
        return fn
    def create_job(self):
        handle = self.CreateJobObjectW(None, None)
        return handle if handle and handle != INVALID_HANDLE else _win_failure(JobErrorCode.HANDLE_FAILED)
    def make_non_inheritable(self, handle) -> bool:
        if not self.SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0): _win_failure(JobErrorCode.INTERNAL_ERROR)
        return True
    def enable_kill_on_close(self, handle) -> bool:
        info = EXTENDED_LIMIT_INFO()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.SetInformationJobObject(handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)): _win_failure(JobErrorCode.INTERNAL_ERROR)
        return True
    def open_process(self, pid: int, access: int):
        handle = self.OpenProcess(access, False, pid)
        return handle if handle and handle != INVALID_HANDLE else _win_failure(JobErrorCode.HANDLE_FAILED)
    def is_process_in_job(self, process, job) -> bool:
        result = wintypes.BOOL()
        if not self.IsProcessInJob(process, job, ctypes.byref(result)): _win_failure(JobErrorCode.INTERNAL_ERROR)
        return bool(result.value)
    def assign(self, job, process) -> bool:
        if not self.AssignProcessToJobObject(job, process): _win_failure(JobErrorCode.ASSIGNMENT_FAILED)
        return True
    def query_active(self, job) -> int:
        info, returned = ACTIVE_PROCESS_INFO(), DWORD()
        if not self.QueryInformationJobObject(job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(returned)): _win_failure(JobErrorCode.INTERNAL_ERROR)
        return int(info.ActiveProcesses)
    def terminate(self, job) -> bool:
        if not self.TerminateJobObject(job, TERMINATION_EXIT_CODE): _win_failure(CLEANUP_ERROR)
        return True
    def terminate_process(self, process) -> bool:
        if not self.TerminateProcess(process, TERMINATION_EXIT_CODE): _win_failure(CLEANUP_ERROR)
        return True
    def wait(self, handle, timeout_ms: int) -> int:
        result = self.WaitForSingleObject(handle, timeout_ms)
        if result == WAIT_FAILED: _win_failure(CLEANUP_ERROR)
        return int(result)
    def close(self, handle) -> bool:
        if not self.CloseHandle(handle): _win_failure(CLEANUP_ERROR)
        return True
def _deadline(clock: Any, value: object) -> float:
    if type(value) not in (int, float): raise JobError(JobErrorCode.TIMEOUT) from None
    try: timeout = float(value)
    except (ValueError, OverflowError): raise JobError(JobErrorCode.TIMEOUT) from None
    if not math.isfinite(timeout) or timeout < 0: raise JobError(JobErrorCode.TIMEOUT) from None
    return clock() + min(timeout, MAX_CLEANUP_SECONDS)
class WindowsJobBoundary:
    def __init__(self, api: NativeApi | None = None, clock: Any = time.monotonic) -> None:
        self.api, self.clock = api or Kernel32Api.load(), clock
        self.job = self.process = None; self.assigned = False; self.borrowed_process = False
        self.state = JobState.CREATED
        try:
            self.job = self._call("create_job")
            if not self.job or not self._call("make_non_inheritable", self.job) or not self._call("enable_kill_on_close", self.job): raise JobError(CLEANUP_ERROR)
        except Exception as error:
            ok, _ = self._cleanup(False, self.clock() + EMERGENCY_CLEANUP_BUDGET_SECONDS, True)
            self.state = JobState.CLOSED if ok else JobState.BROKEN
            raise JobError(CLEANUP_ERROR) if not ok else (error if isinstance(error, JobError) else JobError(JobErrorCode.INTERNAL_ERROR)) from None

    @classmethod
    def _from_owned_job(cls, api: NativeApi, job: Any, clock: Any = time.monotonic) -> "WindowsJobBoundary":
        boundary = cls.__new__(cls)
        boundary.api, boundary.clock = api, clock
        boundary.job = job
        boundary.process = None
        boundary.assigned = False
        boundary.borrowed_process = False
        boundary.state = JobState.CREATED
        return boundary

    def _call(self, name: str, *args: Any) -> Any:
        try: return getattr(self.api, name)(*args)
        except JobError: raise
        except Exception: raise JobError(JobErrorCode.INTERNAL_ERROR) from None
    def _safe(self, name: str, *args: Any) -> bool:
        try: return bool(self._call(name, *args))
        except JobError: return False
    def _close_handles(self, process_ready: bool = True, job_ready: bool = True) -> bool:
        ok = process_ready and job_ready
        for name, ready in (("process", process_ready), ("job", job_ready)):
            handle = getattr(self, name)
            if handle is None or not ready: continue
            if name == "process" and self.borrowed_process:
                continue
            try: closed = bool(self._call("close", handle))
            except JobError: closed = False
            if closed: setattr(self, name, None)
            else: ok = False
        if self.borrowed_process and process_ready and job_ready and self.job is None:
            self.process, self.borrowed_process = None, False
        return ok
    def _cleanup(self, assigned: bool, deadline: float, timed_out: bool = False) -> tuple[bool, bool]:
        ok, process_waited, wait_failed, active_zero = True, self.process is None or (self.borrowed_process and not assigned), False, self.job is None or not assigned
        process_terminated = self.process is None or assigned or self.borrowed_process
        job_terminated = self.job is None
        if not assigned and self.process is not None and not self.borrowed_process:
            process_terminated = self._safe("terminate_process", self.process)
            ok &= process_terminated
        if self.job is not None:
            job_terminated = self._safe("terminate", self.job)
            ok &= job_terminated
        while self.process is not None or self.job is not None:
            remaining = deadline - self.clock()
            if remaining <= 0:
                timed_out = True
                break
            timeout_ms = max(MIN_WAIT_MILLISECONDS, min(MAX_WAIT_MILLISECONDS, int(remaining * MILLISECONDS_PER_SECOND)))
            if self.process is not None and (not self.borrowed_process or assigned):
                try: result = self._call("wait", self.process, timeout_ms)
                except JobError: ok = process_waited = False; result = WAIT_FAILED
                if result == WAIT_OBJECT_0: process_waited = True
                elif result == WAIT_TIMEOUT: process_waited = False
                else: ok = process_waited = False; wait_failed = True
            if self.job is None or not assigned:
                if process_waited or wait_failed: break
                continue
            remaining = deadline - self.clock()
            if remaining <= 0: timed_out = True; break
            try: active = self._call("query_active", self.job)
            except JobError: ok = False; break
            if active == 0 and process_waited: active_zero = True; break
            if wait_failed: break
            if active < 0: ok = False; break
        process_ready = process_terminated and process_waited
        job_ready = job_terminated and active_zero
        closed = self._close_handles(process_ready, job_ready)
        return ok and closed, timed_out
    def assign_process(self, pid: int) -> None:
        if self.state is not JobState.CREATED or self.process is not None or self.job is None: raise JobError(JobErrorCode.INVALID_STATE)
        assigned = False
        try:
            self.process = self._call("open_process", pid, PROCESS_ACCESS)
            if not self.process: raise JobError(JobErrorCode.HANDLE_FAILED)
            if self._call("is_process_in_job", self.process, None): raise JobError(JobErrorCode.NESTED_JOB)
            assigned = bool(self._call("assign", self.job, self.process))
            self.assigned = assigned
            if not assigned: raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            if not self._call("is_process_in_job", self.process, self.job): raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            if self._call("query_active", self.job) < MIN_ACTIVE_PROCESSES: raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            self.assigned = True; self.state = JobState.ASSIGNED
        except Exception as error:
            ok, _ = self._cleanup(assigned, self.clock() + EMERGENCY_CLEANUP_BUDGET_SECONDS, True)
            self.state = JobState.CLOSED if ok else JobState.BROKEN
            if not ok: raise JobError(CLEANUP_ERROR) from None
            raise error if isinstance(error, JobError) else JobError(JobErrorCode.INTERNAL_ERROR) from None

    def assign_borrowed_handle(self, handle: Any) -> None:
        if self.state is not JobState.CREATED or self.process is not None or self.job is None: raise JobError(JobErrorCode.INVALID_STATE)
        if not handle or handle == INVALID_HANDLE: raise JobError(JobErrorCode.HANDLE_FAILED)
        assigned = False
        self.process, self.borrowed_process = handle, True
        try:
            if self._call("is_process_in_job", handle, None): raise JobError(JobErrorCode.NESTED_JOB)
            assigned = bool(self._call("assign", self.job, handle))
            self.assigned = assigned
            if not assigned: raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            if not self._call("is_process_in_job", handle, self.job): raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            if self._call("query_active", self.job) < MIN_ACTIVE_PROCESSES: raise JobError(JobErrorCode.ASSIGNMENT_FAILED)
            self.assigned = True; self.state = JobState.ASSIGNED
        except Exception as error:
            ok, _ = self._cleanup(assigned, self.clock() + EMERGENCY_CLEANUP_BUDGET_SECONDS, True)
            self.state = JobState.CLOSED if ok else JobState.BROKEN
            if not ok: raise JobError(CLEANUP_ERROR) from None
            raise error if isinstance(error, JobError) else JobError(JobErrorCode.INTERNAL_ERROR) from None
    def authorize(self) -> None:
        if self.state is not JobState.ASSIGNED: raise JobError(JobErrorCode.INVALID_STATE)
        self.state = JobState.AUTHORIZED
    def close(self, timeout_seconds: float = DEFAULT_CLEANUP_BUDGET_SECONDS) -> None:
        if self.state is JobState.CLOSED: return
        timed_out = False
        try:
            deadline = _deadline(self.clock, timeout_seconds)
        except JobError:
            deadline, timed_out = self.clock() + EMERGENCY_CLEANUP_BUDGET_SECONDS, True
        ok, cleanup_timeout = self._cleanup(self.assigned, deadline, timed_out)
        timed_out |= cleanup_timeout
        if ok: self.state = JobState.CLOSED
        else: self.state = JobState.BROKEN
        if timed_out: raise JobError(JobErrorCode.TIMEOUT) from None
        if not ok: raise JobError(CLEANUP_ERROR) from None

    def close_with_deadline(self, context) -> None:
        remaining = context.cleanup_ns()
        if remaining <= 0:
            raise JobError(JobErrorCode.TIMEOUT)
        self.close(remaining / 1_000_000_000)
    finalize = close
