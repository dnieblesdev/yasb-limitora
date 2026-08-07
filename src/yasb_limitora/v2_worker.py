from __future__ import annotations

from dataclasses import dataclass
import multiprocessing
import os
from collections.abc import Mapping
from typing import Any, Callable

from .config import LocalConfig
from .limitora_api import read_opencode_go
from .model import DocumentView, ProviderKey, ProviderOutcome, ProviderState, ProviderView, SafeError, SafeErrorCode, V2SafeErrorCode
from .v2_deadline import DeadlineContext
from .v2_guard import GuardError, GuardLease, V2Guard
from .isolation.windows_job import WindowsJobBoundary


def _safe_error(provider: ProviderKey, code: SafeErrorCode) -> ProviderView:
    return ProviderView(provider, ProviderState.SAFE_ERROR, SafeError(code), outcome=ProviderOutcome.EXECUTION_ERROR)


def _not_run(provider: ProviderKey, reason: str) -> ProviderView:
    return ProviderView(provider, ProviderState.UNAVAILABLE, outcome=ProviderOutcome.NOT_RUN, not_run_reason=reason)


def _opencode_bootstrap(reader: Callable[[str, Mapping[str, str]], ProviderView], workspace: str, environment: Mapping[str, str], output: Any, authorized: Any = None) -> None:
    try:
        if authorized is not None:
            authorized.wait()
        output.put(reader(workspace, environment))
    except Exception:
        output.put(_safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR))


@dataclass(slots=True)
class WorkerRecord:
    worker: Any
    job: Any
    reaped: bool = False
    exit_code: int | None = None
    job_active_zero: bool = False
    handles_closed: bool = False


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
        record.reaped and record.exit_code is not None and record.job_active_zero and record.handles_closed
        for record in records
    ) and all(_supervisor_quiescent(supervisor) for supervisor in supervisors) and all(_helper_quiescent(helper) for helper in helpers)


class OpenCodeWorkerProcess:
    def __init__(self, reader=read_opencode_go, *, process_factory=None, job_factory=None, context_factory=None) -> None:
        self.reader = reader
        self.process_factory = process_factory
        self.job_factory = job_factory
        self.context_factory = context_factory or multiprocessing.get_context
        self.record: WorkerRecord | None = None

    def run_with_deadline(self, workspace: str, environment: Mapping[str, str], context: DeadlineContext) -> ProviderView:
        if context.usable_ns() <= 0:
            return _not_run(ProviderKey.OPENCODE_GO, "deadline_exhausted")
        if self.process_factory is None and os.name != "nt":
            return _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR)
        try:
            queue = self.context_factory("spawn").Queue()
            authorized = self.context_factory("spawn").Event()
            process = (self.process_factory or self.context_factory("spawn").Process)(
                target=_opencode_bootstrap, args=(self.reader, workspace, environment, queue, authorized)
            )
            process.start()
            record = self.record = WorkerRecord(process, None)
            job = self.job_factory() if self.job_factory is not None else WindowsJobBoundary()
            job.assign_process(process.pid)
            record.job = job
            authorized.set()
            process.join(context.usable_ns() / 1_000_000_000)
            if process.is_alive():
                self._close_job(job, context)
                process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
                record.exit_code = process.exitcode
                record.reaped = not process.is_alive()
                record.job_active_zero = self._job_zero(job)
                record.handles_closed = self._job_closed(job)
                return _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.TIMEOUT)
            record.exit_code = process.exitcode
            record.reaped = True
            result = queue.get_nowait()
            self._close_job(job, context)
            record.job_active_zero = self._job_zero(job)
            record.handles_closed = self._job_closed(job)
            return result if isinstance(result, ProviderView) else _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR)
        except Exception:
            if self.record is not None and self.record.job is not None:
                try:
                    self._close_job(self.record.job, context)
                except Exception:
                    pass
            if "process" in locals() and getattr(process, "is_alive", lambda: False)():
                try:
                    process.terminate()
                    process.join(max(0.0, context.cleanup_ns() / 1_000_000_000))
                except Exception:
                    pass
            return _safe_error(ProviderKey.OPENCODE_GO, SafeErrorCode.PROVIDER_ERROR)

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


class V2ExecutionOrchestrator:
    def __init__(self, *, guard_factory=V2Guard, codex_executor=None, opencode_factory=OpenCodeWorkerProcess) -> None:
        self.guard_factory = guard_factory
        self.codex_executor = codex_executor
        self.opencode_factory = opencode_factory
        self.worker_records: list[WorkerRecord] = []
        self.workers: list[Any] = []
        self.codex_helpers: list[Any] = []

    def run(self, config: LocalConfig, environment: Mapping[str, str], context: DeadlineContext, config_path: str) -> DocumentView:
        views = {
            ProviderKey.CODEX: _not_run(ProviderKey.CODEX, "disabled"),
            ProviderKey.OPENCODE_GO: _not_run(ProviderKey.OPENCODE_GO, "disabled"),
        }
        enabled = frozenset()
        if config.codex.enabled and config.codex.runner:
            enabled = enabled | {ProviderKey.CODEX}
        if config.opencode_go.enabled and config.opencode_go.workspace_id:
            enabled = enabled | {ProviderKey.OPENCODE_GO}
        if not enabled:
            return self._document(views)
        lease: GuardLease | None = None
        cleanup_error = False
        result: DocumentView | None = None
        try:
            guard = self.guard_factory()
            lease = guard.acquire(config_path, context)
            if context.usable_ns() <= 0:
                result = self._document(
                    {
                        key: _not_run(key, "deadline_exhausted") if key in enabled else view
                        for key, view in views.items()
                    },
                    V2SafeErrorCode.DEADLINE_EXHAUSTED,
                )
            elif ProviderKey.CODEX in enabled:
                executor = self.codex_executor
                if executor is None:
                    from .codex_helper import CodexHelperExecutor
                    executor = CodexHelperExecutor()
                if executor not in self.codex_helpers:
                    self.codex_helpers.append(executor)
                run = getattr(executor, "run_with_deadline", None)
                views[ProviderKey.CODEX] = run((config.codex.runner,), context) if run else executor.run((config.codex.runner,))
            if result is None and ProviderKey.OPENCODE_GO in enabled:
                worker = self.opencode_factory()
                self.workers.append(worker)
                views[ProviderKey.OPENCODE_GO] = worker.run_with_deadline(config.opencode_go.workspace_id, environment, context)
                if worker.record is not None:
                    if worker.record not in self.worker_records:
                        self.worker_records.append(worker.record)
            if result is None:
                result = self._document(views)
        except GuardError as error:
            code = V2SafeErrorCode.GUARD_WAIT_TIMEOUT if error.code == "guard_wait_timeout" else V2SafeErrorCode.GUARD_ACQUISITION_FAILED
            reason = "guard_wait_timeout" if error.code == "guard_wait_timeout" else "document_aborted"
            result = self._document({key: _not_run(key, reason) for key in views}, code)
        except Exception:
            result = self._document(views, V2SafeErrorCode.GUARD_ACQUISITION_FAILED)
        finally:
            if lease is not None:
                for worker in self.workers:
                    if getattr(worker, "record", None) is not None and worker.record not in self.worker_records:
                        self.worker_records.append(worker.record)
                # Workers and their Job handles are closed before ownership is
                # relinquished. This is the no-overlap boundary.
                for record in self.worker_records:
                    if not record.handles_closed and record.job is not None:
                        try:
                            close = getattr(record.job, "close_with_deadline", None)
                            if close is not None:
                                close(context)
                            else:
                                record.job.close(max(0.0, context.cleanup_ns() / 1_000_000_000))
                            record.job_active_zero = self._job_zero(record.job)
                            record.handles_closed = self._job_closed(record.job)
                        except Exception:
                            cleanup_error = True
                if (self.worker_records or self.codex_helpers) and not cleanup_complete(self.worker_records, helpers=self.codex_helpers):
                    cleanup_error = True
                try:
                    release_ok = lease.release()
                except Exception:
                    release_ok = False
                try:
                    close_ok = lease.close()
                except Exception:
                    close_ok = False
                if not close_ok or not release_ok:
                    cleanup_error = True
                if cleanup_error:
                    preserved = views if result is None else {view.provider: view for view in result.providers}
                    result = self._document(preserved, V2SafeErrorCode.CLEANUP_FAILED)
        return result if result is not None else self._document(views, V2SafeErrorCode.GUARD_ACQUISITION_FAILED)

    @staticmethod
    def _document(views: dict[ProviderKey, ProviderView], error: V2SafeErrorCode | None = None) -> DocumentView:
        return DocumentView.ordered(views[ProviderKey.CODEX], views[ProviderKey.OPENCODE_GO], SafeError(error) if error else None)


__all__ = ("OpenCodeWorkerProcess", "V2ExecutionOrchestrator", "WorkerRecord", "cleanup_complete")
