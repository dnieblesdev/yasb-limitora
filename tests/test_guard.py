from types import SimpleNamespace

import pytest

from yasb_limitora.deadline import DeadlineContext
from yasb_limitora.guard import (
    WAIT_ABANDONED,
    WAIT_FAILED,
    WAIT_OBJECT_0,
    WAIT_TIMEOUT,
    GuardError,
    Guard,
)


TEST_SID = bytes((1, 1, 0, 0, 0, 0, 0, 5, 21, 0, 0, 0))


class FakeWin32:
    def __init__(self, wait_result=WAIT_OBJECT_0, *, handle=41, release_result=True, close_result=True):
        self.wait_result = wait_result
        self.handle = handle
        self.release_result = release_result
        self.close_result = close_result
        self.calls = []

    def CreateMutexW(self, security_attributes, initial_owner, name):
        self.calls.append(("create", security_attributes, initial_owner, name))
        return self.handle

    def WaitForSingleObject(self, handle, timeout_ms):
        self.calls.append(("wait", handle, timeout_ms))
        return self.wait_result

    def ReleaseMutex(self, handle):
        self.calls.append(("release", handle))
        return self.release_result

    def CloseHandle(self, handle):
        self.calls.append(("close", handle))
        return self.close_result


class WaitRaisesWin32(FakeWin32):
    def WaitForSingleObject(self, handle, timeout_ms):
        self.calls.append(("wait", handle, timeout_ms))
        raise OSError("native wait failed")


def context(remaining_ns=1_000_000_000, reserve_ns=250_000_000):
    return DeadlineContext(t0_ns=0, deadline_ns=remaining_ns, reserve_ns=reserve_ns, clock_ns=lambda: 0)


def test_scope_name_hashes_sid_bytes_and_canonical_path_without_leaks():
    guard = Guard(api=FakeWin32(), sid_provider=lambda: TEST_SID)
    first = guard.name_for(r"C:\Config\..\config.json")
    equivalent = guard.name_for(r"c:/config.json")
    other = guard.name_for(r"C:\other.json")
    assert first == equivalent
    assert first != other
    assert first.startswith(r"Global\yasb-limitora-v2-guard-")
    assert "private" not in first and "config.json" not in first


@pytest.mark.parametrize("result", (WAIT_OBJECT_0, WAIT_ABANDONED))
def test_object_and_abandoned_wait_results_establish_ownership(result):
    api = FakeWin32(result)
    lease = Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())
    assert lease.owned is True
    assert api.calls[0][2] is False
    assert api.calls[1] == ("wait", 41, 250)


def test_wait_timeout_closes_handle_and_maps_to_safe_guard_error():
    api = FakeWin32(WAIT_TIMEOUT)
    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())
    assert error.value.code == "guard_wait_timeout"
    assert api.calls[-1] == ("close", 41)


@pytest.mark.parametrize("result", (WAIT_FAILED, 99))
def test_failed_wait_maps_to_guard_acquisition_failed(result):
    api = FakeWin32(result)
    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())
    assert error.value.code == "guard_acquisition_failed"


def test_native_wait_exception_closes_created_mutex_handle():
    api = WaitRaisesWin32()
    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())
    assert error.value.code == "guard_acquisition_failed"
    assert api.calls[-1] == ("close", 41)


def test_zero_remaining_budget_uses_zero_wait():
    api = FakeWin32(WAIT_TIMEOUT)
    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=lambda: TEST_SID).acquire(
            r"C:\config.json", DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 0)
        )
    assert error.value.code == "guard_wait_timeout"
    assert ("wait", 41, 0) in api.calls


def test_identity_failure_is_sanitized():
    api = FakeWin32()

    def fail_identity():
        raise OSError("SID and path private detail")

    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=fail_identity).acquire(r"C:\private.json", context())
    assert error.value.code == "guard_acquisition_failed"
    assert str(error.value) == "guard_acquisition_failed"
    assert api.calls == []


def test_malformed_sid_fails_closed_without_creating_a_mutex():
    api = FakeWin32()
    with pytest.raises(GuardError) as error:
        Guard(api=api, sid_provider=lambda: b"sid").acquire(r"C:\config.json", context())
    assert error.value.code == "guard_acquisition_failed"
    assert api.calls == []


def test_release_and_close_are_explicitly_available():
    api = FakeWin32()
    lease = Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())
    assert lease.release() is True
    assert lease.close() is True


def test_release_failure_retains_ownership_and_repeated_close_is_bounded():
    api = FakeWin32(release_result=False)
    lease = Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())

    assert lease.release() is False
    assert lease.owned is True and lease.closed is False
    assert lease.close() is False
    assert api.calls.count(("close", 41)) == 0
    assert lease.release() is False


def test_close_failure_retains_non_finalized_lease_for_a_later_bounded_retry():
    api = FakeWin32(close_result=False)
    lease = Guard(api=api, sid_provider=lambda: TEST_SID).acquire(r"C:\config.json", context())

    assert lease.release() is True
    assert lease.close() is False
    assert lease.owned is False and lease.closed is False
    api.close_result = True
    assert lease.close() is True
    assert lease.closed is True
    assert lease.close() is True
