import pytest

import yasb_limitora.codex_process_resources as r


class Handle:
    def __init__(self, events: list[str]) -> None: self.events = events
    def Close(self) -> None: self.events.append("release")
    def __repr__(self) -> str: return "<Handle>"


class Process:
    def __init__(self, events: list[str], **flags: object) -> None:
        self.events, self.flags, self.alive, self.handle_reads = events, flags, True, 0
        self._real_handle = Handle(events)
    @property
    def _handle(self):
        self.handle_reads += 1
        if self.flags.get("adapt_fail"): raise RuntimeError("secret-handle")
        return self._real_handle
    def poll(self): self.events.append("poll"); return None if self.alive else 0
    def terminate(self):
        self.events.append("terminate")
        if self.flags.get("terminate_fail"): raise OSError("secret-terminate")
        self.alive = False
    def wait(self, timeout):
        self.events.append("wait")
        if self.flags.get("wait_fail"): raise TimeoutError("secret-wait")
        self.alive = False


class Job:
    def __init__(self, events: list[str], **flags: object) -> None:
        self.events, self.flags, self.assigned = events, flags, False
    def assign_borrowed_handle(self, handle): self.events.append(("assign", handle)); self.assigned = True
    def close(self, timeout):
        self.events.append("job")
        if self.flags.get("fail_once"):
            self.flags["fail_once"] = False
            raise r._ProcessResourceError("job_failure")


def test_register_stores_exact_popen_without_touching_hooks() -> None:
    class Hostile:
        @property
        def _handle(self): raise AssertionError("adapted too early")
        def poll(self): raise AssertionError("polled too early")
    process = Hostile(); owner = r._PopenProcessOwner.register(process)
    assert owner._popen is process and owner._state is r._PopenState.REGISTERED


def test_adaptation_failure_keeps_owner_for_direct_terminate_wait_cleanup() -> None:
    events: list[str] = []; process = Process(events, adapt_fail=True); owner = r._PopenProcessOwner.register(process)
    with pytest.raises(r._PopenAdaptationError) as error: owner.adapt_native_handle()
    owner.close(1.0)
    assert owner._state is r._PopenState.CLOSED and events == ["poll", "terminate", "wait"] and "secret" not in str(error.value)


@pytest.mark.parametrize("failure", ["terminate_fail", "wait_fail"])
def test_direct_cleanup_retains_exact_popen_for_retry(failure: str) -> None:
    events: list[str] = []; process = Process(events, **{failure: True}); owner = r._PopenProcessOwner.register(process); handle = owner.adapt_native_handle()
    with pytest.raises(r._PopenCleanupError): owner.close(1.0)
    assert owner._popen is process and owner._native_handle is handle and owner._state is r._PopenState.BROKEN
    process.flags[failure] = False
    owner.close(1.0); owner.close(1.0)
    assert owner._state is r._PopenState.CLOSED and events.count("release") == 1


def test_exact_handle_adapts_without_pid_reopen_and_timeout_secret_is_not_coerced() -> None:
    events: list[str] = []; process = Process(events); owner = r._PopenProcessOwner.register(process); handle = owner.adapt_native_handle()
    assert handle is process._real_handle and process.handle_reads == 1
    class SecretFloat:
        called = False
        def __float__(self): self.called = True; raise RuntimeError("secret-timeout")
    value = SecretFloat()
    with pytest.raises(r._PopenTimeoutError) as error: owner.close(value)
    assert not value.called and str(error.value) == "timeout" and owner._state is r._PopenState.CLOSED


def test_pre_assignment_aggregate_closes_only_process_and_repeated_close_is_safe() -> None:
    events: list[str] = []; process = Process(events); owner = r._PopenProcessOwner.register(process)
    aggregate = r._HelperProcessResources(owner)
    aggregate.close(1.0); aggregate.close(1.0)
    assert aggregate._state is r._HelperState.CLOSED and events == ["poll", "terminate", "wait"]


def test_attach_requires_adaptation_and_only_once() -> None:
    events: list[str] = []; process = Process(events); owner = r._PopenProcessOwner.register(process); aggregate = r._HelperProcessResources(owner); job = Job(events)
    with pytest.raises(r._OwnershipError): aggregate.attach_job(job)
    handle = owner.adapt_native_handle(); aggregate.attach_job(job)
    assert events == [("assign", handle)]
    with pytest.raises(r._OwnershipError): aggregate.attach_job(Job(events))


def test_job_closes_first_and_failed_job_retains_both_for_retry() -> None:
    events: list[str] = []; process = Process(events); owner = r._PopenProcessOwner.register(process); handle = owner.adapt_native_handle(); job = Job(events, fail_once=True); aggregate = r._HelperProcessResources(owner); aggregate.attach_job(job)
    with pytest.raises(r._ProcessResourceError): aggregate.close(1.0)
    assert owner._popen is process and owner._native_handle is handle and events == [("assign", handle), "job"]
    aggregate.close(1.0); aggregate.close(1.0)
    assert aggregate._state is r._HelperState.CLOSED and events == [("assign", handle), "job", "job", "poll", "terminate", "wait", "release"]


def test_redaction_and_scope_are_private() -> None:
    assert repr(r._PopenProcessOwner.register(object())) == "<_PopenProcessOwner>"
    assert repr(r._PopenCleanupError()) == "<_PopenCleanupError>"
    assert r.__all__ == () and not hasattr(r, "Popen") and not hasattr(r, "subprocess") and not hasattr(r, "WindowsJobBoundary")
    import yasb_limitora
    assert not hasattr(yasb_limitora, "_PopenProcessOwner")
