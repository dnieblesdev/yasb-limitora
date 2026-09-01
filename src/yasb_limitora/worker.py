from __future__ import annotations

import multiprocessing
import os
import sys
from collections.abc import Callable, Mapping
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from typing import Any

from .config import LocalConfig
from .isolation.windows_job import WindowsJobBoundary
from .limitora_api import (
    OPENCODE_API_KEY_ENV,
    OpenCodeFailureEvidence,
    OpenCodeReadResult,
    OpenCodeRequest,
    read_opencode_go,
)
from .model import (
    DocumentView,
    ProviderKey,
    ProviderOutcome,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
)
from .v2_deadline import DeadlineContext
from .v2_guard import GuardError, GuardLease, V2Guard
from .v2_path import _child_process, _start_quiet_child


def _safe_error(provider: ProviderKey, code: SafeErrorCode) -> ProviderView:
    return ProviderView(provider, ProviderState.SAFE_ERROR, SafeError(code), outcome=ProviderOutcome.EXECUTION_ERROR)


def _not_run(provider: ProviderKey, reason: str) -> ProviderView:
    return ProviderView(provider, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason)


def _capture_call(function: Callable[[], Any], fallback: Any = None) -> tuple[Exception | None, Any]:
    """Capture ordinary failures while leaving interrupt signals untouched."""
    error: Exception | None = None
    result = fallback

    def capture(exception_type: Any, exception: BaseException | None, traceback: Any) -> bool:
        nonlocal error
        if isinstance(exception, Exception):
            error = exception
            return True
        return False

    with ExitStack() as resources:
        resources.push(capture)
        result = function()
    return error, result


def _try_call(function: Callable[[], Any], fallback: Any = None) -> tuple[bool, Any]:
    error, result = _capture_call(function, fallback)
    return error is None, result


def _opencode_bootstrap(reader: Callable[[OpenCodeRequest], OpenCodeReadResult], request: OpenCodeRequest, output: Any, authorized: Any = None) -> None:
    original_stderr = sys.stderr
    with ExitStack() as resources:
        try:
            sys.stderr = resources.enter_context(open(os.devnull, "w", encoding="ascii"))
        except OSError:
            sys.stderr = original_stderr
        try:
            with suppress(Exception):
                if authorized is not None:
                    authorized.wait()
                output.put(reader(request))
                return
            with suppress(Exception):
                output.put(
                    OpenCodeReadResult(
                        _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR),
                        OpenCodeFailureEvidence.UNAVAILABLE,
                    )
                )
        finally:
            sys.stderr = original_stderr


@dataclass(slots=True)
class WorkerRecord:
    worker: Any
    job: Any
    queue_closed: bool = True
    queue: Any = None
    authorized_closed: bool = True
    authorized: Any = None
    reaped: bool = False
    exit_code: int | None = None
    job_active_zero: bool = False
    job_closed: bool = False
    process_closed: bool = False
    started: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    document: DocumentView
    opencode_evidence: OpenCodeFailureEvidence | None = None


def _supervisor_quiescent(supervisor: Any) -> bool:
    state = getattr(getattr(supervisor, "_state", None), "value", getattr(supervisor, "_state", None))
    return state == "closed" and all(
        getattr(supervisor, name, None) is None
        for name in ("_pending", "_prepared", "_helper", "_gate", "_data")
    )


def _helper_quiescent(helper: Any) -> bool:
    return (
        getattr(helper, "_pending_supervisor", None) is None
        and not getattr(helper, "_active", False)
        and not getattr(helper, "_retrying", False)
        and (_supervisor_quiescent(getattr(helper, "_last_supervisor", None)) if getattr(helper, "_last_supervisor", None) is not None else True)
    )


def cleanup_complete(records: list[WorkerRecord], *, supervisors=(), helpers=()) -> bool:
    return bool(records or tuple(supervisors) or tuple(helpers)) and all(
        record.reaped and (record.exit_code is not None or not record.started) and (record.job is None or (record.job_active_zero and record.job_closed)) and record.process_closed and record.queue_closed and record.authorized_closed
        for record in records
    ) and all(_supervisor_quiescent(supervisor) for supervisor in supervisors) and all(_helper_quiescent(helper) for helper in helpers)


class OpenCodeWorkerProcess:
    def __init__(self, reader=read_opencode_go, *, process_factory=None, job_factory=None, context_factory=None) -> None:
        self.reader = reader
        self.process_factory = process_factory
        self.job_factory = job_factory
        self.context_factory = context_factory or multiprocessing.get_context
        self.record: WorkerRecord | None = None
        self.last_result: OpenCodeReadResult | None = None

    def run_with_deadline(self, request: OpenCodeRequest, context: DeadlineContext) -> ProviderView:
        self.last_result = None
        if context.usable_ns() <= 0:
            return _not_run(ProviderKey.OPENCODE_GO, "deadline_exhausted")
        queue = authorized = process = None
        if self.process_factory is None and os.name != "nt":
            view = _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR)
            self.last_result = OpenCodeReadResult(view, OpenCodeFailureEvidence.UNAVAILABLE)
            return view

        def attempt() -> ProviderView:
            nonlocal authorized, process, queue
            process_context = self.context_factory("spawn")
            queue = process_context.Queue()
            record = self.record = WorkerRecord(None, None, queue_closed=False, queue=queue, authorized_closed=False)
            authorized = process_context.Event()
            record.authorized = authorized
            process = _child_process(
                process_context,
                _opencode_bootstrap,
                (self.reader, request, queue, authorized),
                self.process_factory,
            )
            record.worker = process
            _start_quiet_child(process)
            record.started = True
            job = self.job_factory() if self.job_factory is not None else WindowsJobBoundary()
            record.job = job
            pid = process.pid
            if not isinstance(pid, int):
                raise TypeError("worker process has no pid")
            job.assign_process(pid, allow_nested=True)
            if context.usable_ns() <= 0:
                view = _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.TIMEOUT)
                self.last_result = OpenCodeReadResult(view, OpenCodeFailureEvidence.TIMEOUT)
                return view
            authorized.set()
            process.join(context.usable_ns() / 1_000_000_000)
            if process.is_alive():
                self._close_job(job, context)
                record.job_active_zero = self._job_zero(job)
                record.job_closed = self._job_closed(job)
                self._reap_process(process, context, terminate=True)
                view = _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.TIMEOUT)
                self.last_result = OpenCodeReadResult(view, OpenCodeFailureEvidence.TIMEOUT)
                return view
            record.exit_code = process.exitcode
            record.reaped = True
            result = queue.get_nowait()
            self.last_result = result if isinstance(result, OpenCodeReadResult) else None
            self._close_job(job, context)
            record.job_active_zero = self._job_zero(job)
            record.job_closed = self._job_closed(job)
            self._reap_process(process, context, terminate=False)
            if isinstance(result, OpenCodeReadResult):
                return result.view
            if isinstance(result, ProviderView):
                return result
            return _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR)

        try:
            error, view = _capture_call(attempt)
            if error is not None:
                def recover_job() -> None:
                    if self.record is not None and self.record.job is not None:
                        self._close_job(self.record.job, context)
                        self.record.job_active_zero = self._job_zero(self.record.job)
                        self.record.job_closed = self._job_closed(self.record.job)

                _try_call(recover_job)
                if process is not None:
                    self._reap_process(process, context, terminate=True)
                self.last_result = OpenCodeReadResult(
                    _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR),
                    OpenCodeFailureEvidence.UNAVAILABLE,
                )
                return self.last_result.view
            return view
        finally:
            if process is not None and self.record is not None and not self.record.reaped:
                self._reap_process(process, context, terminate=False)
            elif self.record is not None and process is None:
                self.record.reaped = True
                self.record.process_closed = True
            if self.record is not None and authorized is None:
                self.record.authorized_closed = True
            if queue is not None:
                def close_queue() -> None:
                    self._close_queue(queue)
                    if self.record is not None:
                        self.record.queue_closed = True
                        self.record.queue = None

                closed, _ = _try_call(close_queue)
                if not closed and self.record is not None:
                    self.record.queue_closed = False
            if authorized is not None:
                def close_authorized() -> None:
                    close = getattr(authorized, "close", None)
                    if close is not None:
                        close()
                    if self.record is not None:
                        self.record.authorized_closed = True
                        self.record.authorized = None

                closed, _ = _try_call(close_authorized)
                if not closed and self.record is not None:
                    self.record.authorized_closed = False

    @staticmethod
    def _close_queue(queue: Any) -> None:
        cancel = getattr(queue, "cancel_join_thread", None)
        if cancel is not None:
            cancel()
        close = getattr(queue, "close", None)
        if close is not None:
            close()

    def _reap_process(self, process: Any, context: DeadlineContext, *, terminate: bool) -> None:
        record = self.record
        if record is None:
            return
        if record.started:
            alive = getattr(process, "is_alive", lambda: False)()
            if alive and terminate:
                _try_call(process.terminate)
            if alive:
                _try_call(lambda: process.join(max(0.0, context.cleanup_ns() / 1_000_000_000)))
            alive = getattr(process, "is_alive", lambda: False)()
            if alive:
                kill = getattr(process, "kill", None)
                if kill is not None:
                    _try_call(
                        lambda: (
                            kill(),
                            process.join(max(0.0, context.cleanup_ns() / 1_000_000_000)),
                        )
                    )
            alive = getattr(process, "is_alive", lambda: False)()
            record.exit_code = getattr(process, "exitcode", None)
            record.reaped = not alive
        else:
            record.reaped = True
        if not record.reaped:
            return
        close = getattr(process, "close", None)
        if close is None:
            record.process_closed = True
            return
        closed, _ = _try_call(close)
        record.process_closed = closed

    def _close_job(self, job: Any, context: DeadlineContext) -> None:
        close = getattr(job, "close_with_deadline", None)
        if close is not None:
            close(context)
        else:
            job.close(max(0.0, context.cleanup_ns() / 1_000_000_000))

    @staticmethod
    def _job_zero(job: Any) -> bool:
        return bool(getattr(job, "active_processes", 0) == 0 or getattr(job, "job_active_zero", False))

    @staticmethod
    def _job_closed(job: Any) -> bool:
        return getattr(job, "state", None) == "closed" or getattr(job, "closed", False)


class RefreshAttempt:
    """Own one provider refresh, its fresh resources, and bounded cleanup."""

    def __init__(self, *, guard_factory=V2Guard, codex_executor=None, opencode_factory=OpenCodeWorkerProcess) -> None:
        self.guard_factory = guard_factory
        self.codex_executor = codex_executor
        self.opencode_factory = opencode_factory
        self.worker_records: list[WorkerRecord] = []
        self.workers: list[Any] = []
        self.codex_helpers: list[Any] = []
        self._unfinalized_leases: list[Any] = []
        self.authority_acquired = False
        self.last_record: ExecutionRecord | None = None

    def _cleanup_resources(self, context: DeadlineContext) -> bool:
        cleanup_error = False
        for worker in self.workers:
            record = getattr(worker, "record", None)
            if record is not None and record not in self.worker_records:
                self.worker_records.append(record)
        for record in self.worker_records:
            if not record.job_closed and record.job is not None:
                def close_record_job(record: WorkerRecord = record) -> None:
                    self._close_job(record.job, context)
                    worker_process_type: type[OpenCodeWorkerProcess] = OpenCodeWorkerProcess
                    record.job_active_zero = worker_process_type._job_zero(record.job)
                    record.job_closed = worker_process_type._job_closed(record.job)

                closed, _ = _try_call(close_record_job)
                if not closed:
                    cleanup_error = True
            if not record.queue_closed and record.queue is not None:
                def close_record_queue(record: WorkerRecord = record) -> None:
                    OpenCodeWorkerProcess._close_queue(record.queue)
                    record.queue_closed = True
                    record.queue = None

                closed, _ = _try_call(close_record_queue)
                if not closed:
                    cleanup_error = True
            if not record.authorized_closed and record.authorized is not None:
                def close_record_authorized(record: WorkerRecord = record) -> None:
                    close = getattr(record.authorized, "close", None)
                    if close is not None:
                        close()
                    record.authorized_closed = True
                    record.authorized = None

                closed, _ = _try_call(close_record_authorized)
                if not closed:
                    cleanup_error = True
            owner = next((worker for worker in self.workers if getattr(worker, "record", None) is record), None)
            reap = getattr(owner, "_reap_process", None)
            if callable(reap) and (not record.reaped or not record.process_closed):
                reaped, _ = _try_call(
                    lambda reap=reap, record=record: reap(record.worker, context, terminate=not record.reaped)
                )
                if not reaped:
                    cleanup_error = True
            if not record.reaped or not record.process_closed or not record.queue_closed or not record.authorized_closed:
                cleanup_error = True
        for helper in self.codex_helpers:
            pending = getattr(helper, "_pending_supervisor", None)
            if pending is None:
                continue
            retry = getattr(helper, "_retry_cleanup_with_deadline", None)
            if not callable(retry):
                cleanup_error = True
                continue
            retried, retry_result = _try_call(lambda retry=retry: retry(context))
            if not retried or not retry_result:
                cleanup_error = True
        if (self.worker_records or self.codex_helpers) and not cleanup_error:
            checked, complete = _try_call(
                lambda: cleanup_complete(self.worker_records, helpers=self.codex_helpers)
            )
            if not checked or not complete:
                cleanup_error = True
        return not cleanup_error

    @staticmethod
    def _close_job(job: Any, context: DeadlineContext) -> None:
        close = getattr(job, "close_with_deadline", None)
        if close is not None:
            close(context)
        else:
            job.close(max(0.0, context.cleanup_ns() / 1_000_000_000))

    @staticmethod
    def _release_provider_lease(lease: Any) -> bool:
        """Finalize a lease in order, retaining completed substeps for retry."""
        owned = getattr(lease, "owned", None)
        closed_state = getattr(lease, "closed", None)
        released = bool(getattr(lease, "_yasb_release_complete", False))
        closed = bool(getattr(lease, "_yasb_close_complete", False))
        if isinstance(owned, bool):
            released = released or not owned
        if isinstance(closed_state, bool):
            closed = closed or closed_state
        if not released:
            released_ok, release_result = _try_call(lambda: bool(lease.release()), False)
            released = release_result if released_ok else False
            if released:
                with suppress(Exception):
                    lease._yasb_release_complete = True
        if released and not closed:
            closed_ok, close_result = _try_call(lambda: bool(lease.close()), False)
            closed = close_result if closed_ok else False
            if closed:
                with suppress(Exception):
                    lease._yasb_close_complete = True
        if released and closed:
            with suppress(Exception):
                lease._yasb_finalized = True
        return released and closed

    def _retry_unfinalized_leases(self) -> bool:
        remaining = []
        for lease in self._unfinalized_leases:
            if not self._release_provider_lease(lease):
                remaining.append(lease)
        self._unfinalized_leases = remaining
        return not remaining

    def run(
        self,
        config: LocalConfig,
        environment: Mapping[str, str],
        context: DeadlineContext,
        config_path: str,
        *,
        provider_errors: frozenset[ProviderKey] | set[ProviderKey] = frozenset(),
    ) -> DocumentView:
        self.last_record = None
        views = {
            ProviderKey.CODEX: _not_run(ProviderKey.CODEX, "disabled"),
            ProviderKey.OPENCODE_GO: _not_run(ProviderKey.OPENCODE_GO, "disabled"),
        }
        for provider in provider_errors:
            views[provider] = _safe_error(provider, SafeErrorCode.CONFIGURATION_INVALID)
        if (self.worker_records or self.codex_helpers) and not self._cleanup_resources(context):
            result = self._document(views, SafeErrorCode.CLEANUP_FAILED)
            self.last_record = ExecutionRecord(result)
            return result
        if self._unfinalized_leases and not self._retry_unfinalized_leases():
            result = self._document(views, SafeErrorCode.CLEANUP_FAILED)
            self.last_record = ExecutionRecord(result)
            return result
        if self.worker_records or self.codex_helpers:
            self.worker_records.clear()
            self.codex_helpers.clear()
        enabled = frozenset()
        if ProviderKey.CODEX not in provider_errors and config.codex.enabled and config.codex.runner:
            enabled = enabled | {ProviderKey.CODEX}
        api_key = environment.get(OPENCODE_API_KEY_ENV)
        if ProviderKey.OPENCODE_GO not in provider_errors and config.opencode_go.enabled and isinstance(api_key, str) and api_key:
            enabled = enabled | {ProviderKey.OPENCODE_GO}
        if not enabled:
            result = self._document(views)
            self.last_record = ExecutionRecord(result)
            return result
        lease: GuardLease | None = None
        cleanup_error = False
        result: DocumentView | None = None
        unexpected_error: Exception | None = None
        current_opencode_result: OpenCodeReadResult | None = None
        current_worker: Any | None = None
        self.authority_acquired = self.guard_factory is None
        def execute() -> None:
            nonlocal current_opencode_result, current_worker, lease, result, views
            if self.guard_factory is not None:
                guard = self.guard_factory()
                lease = guard.acquire(config_path, context)
                self.authority_acquired = lease is not None
            if context.usable_ns() <= 0:
                result = self._document(
                    {
                        key: view if key in provider_errors else _not_run(key, "deadline_exhausted")
                        for key, view in views.items()
                    },
                    SafeErrorCode.DEADLINE_EXHAUSTED,
                )
            elif ProviderKey.CODEX in enabled:
                executor = self.codex_executor
                if executor is None:
                    from .codex_helper import CodexHelperExecutor
                    executor = CodexHelperExecutor()
                if executor not in self.codex_helpers:
                    self.codex_helpers.append(executor)
                run = getattr(executor, "run_with_deadline", None)
                runner_path = config.codex.runner
                if not isinstance(runner_path, str) or not runner_path:
                    views[ProviderKey.CODEX] = _safe_error(ProviderKey.CODEX, SafeErrorCode.CONFIGURATION_INVALID)
                else:
                    runner = (runner_path, "app-server")
                    views[ProviderKey.CODEX] = run(runner, context) if run else executor.run(runner)
            if result is None and ProviderKey.OPENCODE_GO in enabled:
                remaining_ns = context.remaining_ns()
                usable_ns = max(0, remaining_ns - context.reserve_ns)
                if usable_ns <= 0:
                    views[ProviderKey.OPENCODE_GO] = _not_run(ProviderKey.OPENCODE_GO, "deadline_exhausted")
                    result = self._document(views, SafeErrorCode.DEADLINE_EXHAUSTED)
                else:
                    opencode_api_key = api_key
                    if not isinstance(opencode_api_key, str) or not opencode_api_key:
                        views[ProviderKey.OPENCODE_GO] = _safe_error(
                            ProviderKey.OPENCODE_GO, SafeErrorCode.CONFIGURATION_INVALID
                        )
                    else:
                        current_worker = self.opencode_factory()
                        self.workers.append(current_worker)
                        remaining = remaining_ns / 1_000_000_000
                        request = OpenCodeRequest(
                            opencode_api_key,
                            min(config.opencode_go.timeout_seconds, usable_ns / 1_000_000_000),
                            remaining,
                        )
                        views[ProviderKey.OPENCODE_GO] = current_worker.run_with_deadline(request, context)
                        current_opencode_result = getattr(current_worker, "last_result", None)
                        if current_worker.record is not None and current_worker.record not in self.worker_records:
                            self.worker_records.append(current_worker.record)
            if result is None:
                result = self._document(views)
        try:
            error, _ = _capture_call(execute)
            if isinstance(error, GuardError):
                code = SafeErrorCode.GUARD_WAIT_TIMEOUT if error.code == "guard_wait_timeout" else SafeErrorCode.GUARD_ACQUISITION_FAILED
                reason = "guard_wait_timeout" if error.code == "guard_wait_timeout" else "document_aborted"
                result = self._document({key: _not_run(key, reason) for key in views}, code)
            elif error is not None:
                current_opencode_result = getattr(current_worker, "last_result", None)
                views = {key: view if key in provider_errors else _not_run(key, "document_aborted") for key, view in views.items()}
                unexpected_error = error
        finally:
            cleanup_safe = self._cleanup_resources(context)
            lease_released = lease is None
            if cleanup_safe and lease is not None:
                lease_released = self._release_provider_lease(lease)
            if lease is not None and not lease_released and lease not in self._unfinalized_leases:
                self._unfinalized_leases.append(lease)
            cleanup_error = not cleanup_safe or not lease_released
            if cleanup_safe and lease_released:
                self.worker_records.clear()
                self.codex_helpers.clear()
            if cleanup_error:
                preserved = views if result is None else {view.provider: view for view in result.providers}
                result = self._document(preserved, SafeErrorCode.CLEANUP_FAILED)
        if unexpected_error is not None:
            raise unexpected_error
        document = result if result is not None else self._document(views, SafeErrorCode.GUARD_ACQUISITION_FAILED)
        evidence = current_opencode_result.evidence if isinstance(current_opencode_result, OpenCodeReadResult) else None
        self.last_record = ExecutionRecord(document, evidence)
        return document

    def run_refresh_attempt(
        self,
        config: LocalConfig,
        environment: Mapping[str, str],
        context: DeadlineContext,
        config_path: str,
    ):
        """Run one normal refresh attempt and prepare its public cache bytes."""
        from .cache import SingleFlightResult
        from .projection import ProjectionInput, project_bytes

        document = self.run(config, environment, context, config_path)
        evidence = self.last_record.opencode_evidence if self.last_record is not None else None
        enabled = frozenset(
            provider
            for provider, enabled_flag in (
                (ProviderKey.CODEX, config.codex.enabled),
                (ProviderKey.OPENCODE_GO, config.opencode_go.enabled),
            )
            if enabled_flag
        )
        _, public_bytes = _try_call(
            lambda: project_bytes(ProjectionInput(document, enabled, evidence)),
            None,
        )
        return SingleFlightResult(value=document, cached_public_bytes=public_bytes, produced=True)

    @staticmethod
    def _document(views: dict[ProviderKey, ProviderView], error: SafeErrorCode | None = None) -> DocumentView:
        return DocumentView.ordered(views[ProviderKey.CODEX], views[ProviderKey.OPENCODE_GO], SafeError(error) if error else None)


class ExecutionOrchestrator:
    """Create a fresh refresh owner for every orchestration call."""

    def __init__(self, *, guard_factory=V2Guard, codex_executor=None, opencode_factory=OpenCodeWorkerProcess) -> None:
        self.guard_factory = guard_factory
        self.codex_executor = codex_executor
        self.opencode_factory = opencode_factory
        self._attempt: RefreshAttempt | None = None
        self._worker_history: list[Any] = []
        self.last_record: ExecutionRecord | None = None

    @property
    def workers(self) -> list[Any]:
        return self._worker_history

    @property
    def worker_records(self) -> list[WorkerRecord]:
        return self._attempt.worker_records if self._attempt is not None else []

    @property
    def codex_helpers(self) -> list[Any]:
        return self._attempt.codex_helpers if self._attempt is not None else []

    def run(
        self,
        config: LocalConfig,
        environment: Mapping[str, str],
        context: DeadlineContext,
        config_path: str,
        *,
        provider_errors: frozenset[ProviderKey] | set[ProviderKey] = frozenset(),
    ) -> DocumentView:
        previous = self._attempt
        if previous is not None:
            cleaned = previous._cleanup_resources(context) and previous._retry_unfinalized_leases()
            if not cleaned:
                views = {
                    ProviderKey.CODEX: _safe_error(ProviderKey.CODEX, SafeErrorCode.CONFIGURATION_INVALID)
                    if ProviderKey.CODEX in provider_errors else _not_run(ProviderKey.CODEX, "disabled"),
                    ProviderKey.OPENCODE_GO: _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.CONFIGURATION_INVALID)
                    if ProviderKey.OPENCODE_GO in provider_errors else _not_run(ProviderKey.OPENCODE_GO, "disabled"),
                }
                result = previous._document(views, SafeErrorCode.CLEANUP_FAILED)
                self.last_record = ExecutionRecord(result)
                return result
            previous.worker_records.clear()
            previous.codex_helpers.clear()

        attempt = RefreshAttempt(
            guard_factory=self.guard_factory,
            codex_executor=self.codex_executor,
            opencode_factory=self.opencode_factory,
        )
        self._attempt = attempt
        result = attempt.run(config, environment, context, config_path, provider_errors=provider_errors)
        self._worker_history.extend(attempt.workers)
        self.last_record = attempt.last_record
        return result

    def run_refresh_attempt(
        self,
        config: LocalConfig,
        environment: Mapping[str, str],
        context: DeadlineContext,
        config_path: str,
        enabled_providers: frozenset[ProviderKey] | None = None,
        *,
        provider_errors: frozenset[ProviderKey] | set[ProviderKey] = frozenset(),
    ):
        """Run one provider attempt and prepare its authoritative publication payload."""
        from .cache import SingleFlightResult
        from .projection import ProjectionInput, project_bytes

        document = self.run(config, environment, context, config_path, provider_errors=provider_errors)
        record = self.last_record
        if enabled_providers is None:
            enabled_providers = frozenset(
                provider
                for provider, enabled in (
                    (ProviderKey.CODEX, config.codex.enabled or ProviderKey.CODEX in provider_errors),
                    (ProviderKey.OPENCODE_GO, config.opencode_go.enabled or ProviderKey.OPENCODE_GO in provider_errors),
                )
                if enabled
            )
        evidence = None
        if record is not None:
            evidence = record.opencode_evidence
        cacheable = (
            record is not None
            and document.document_error is None
            and any(view.outcome in (ProviderOutcome.SNAPSHOT, ProviderOutcome.UNDETECTED) for view in document.providers)
            and all(view.outcome is not ProviderOutcome.EXECUTION_ERROR for view in document.providers)
        )
        projected = project_bytes(ProjectionInput(document, enabled_providers, evidence)) if cacheable else None
        return SingleFlightResult(value=document, cached_public_bytes=projected, produced=True)


__all__ = ("ExecutionOrchestrator", "ExecutionRecord", "OpenCodeWorkerProcess", "RefreshAttempt", "WorkerRecord", "cleanup_complete")
