from datetime import datetime, timezone
from types import SimpleNamespace

import limitora

from yasb_limitora.codex_helper import CodexHelperExecutor
from yasb_limitora.limitora_api import (
    CodexLimitoraAdapter,
    read_opencode_go,
)
from yasb_limitora.model import ProviderState, SafeErrorCode


def _snapshot(state=limitora.ProviderState.AVAILABLE, freshness=limitora.Freshness.FRESH):
    now = datetime.now(timezone.utc)
    status = limitora.ProviderStatus(limitora.ProviderId("codex"), state, now)
    snapshot = limitora.ProviderSnapshot(
        limitora.ProviderId("codex"), status, now, now, limitora.SourceMetadata("test")
    )
    return limitora.StatusSnapshotResult(snapshot, freshness)


def test_adapter_uses_root_public_api_and_maps_success_unavailable_stale_and_error():
    provider_error = limitora.ProviderError(
        limitora.ProviderErrorKind.TRANSPORT,
        limitora.ProviderId("codex"),
        "safe provider failure",
        retryable=False,
    )
    results = iter((_snapshot(), _snapshot(state=limitora.ProviderState.UNAVAILABLE), _snapshot(freshness=limitora.Freshness.STALE), provider_error, TimeoutError("secret")))

    class Client:
        def read_status(self, request):
            result = next(results)
            if isinstance(result, BaseException):
                raise result
            return result

    clients = iter((Client(), Client(), Client(), Client(), Client()))
    adapter = CodexLimitoraAdapter(lambda config: next(clients))
    assert adapter.read(("C:\\codex.exe",)).state is ProviderState.SUCCESS
    assert adapter.read(("C:\\codex.exe",)).state is ProviderState.UNAVAILABLE
    assert adapter.read(("C:\\codex.exe",)).state is ProviderState.UNAVAILABLE
    assert adapter.read(("C:\\codex.exe",)).error.code is SafeErrorCode.PROVIDER_ERROR
    assert adapter.read(("C:\\codex.exe",)).error.code is SafeErrorCode.TIMEOUT
    view = read_opencode_go("private-workspace", {})
    assert view.state is ProviderState.UNAVAILABLE
    assert "private-workspace" not in repr(view)


def test_concurrent_cleanup_ownership_is_atomic():
    import threading
    started, release, created, fail = threading.Event(), threading.Event(), [], [True]
    def close(timeout):
        if fail[0]: raise RuntimeError("private cleanup detail")
    def factory(**kwargs):
        created.append(1)
        return SimpleNamespace(acquire=lambda: (started.set(), release.wait()), close=close)
    executor = CodexHelperExecutor(factory)
    barrier, results = threading.Barrier(2), [None, None]
    def work(index): barrier.wait(); results.__setitem__(index, executor.run(("C:\\codex.exe",)))
    threads = [threading.Thread(target=work, args=(index,)) for index in range(2)]
    [thread.start() for thread in threads]; started.wait(); release.set(); [thread.join() for thread in threads]
    assert len(created) == 1 and all(result.error.code is SafeErrorCode.INTERNAL_ERROR for result in results)
    assert executor.retry_cleanup() is False; fail[0] = False
    assert executor.retry_cleanup() and executor.run(("C:\\codex.exe",)).error.code is SafeErrorCode.PROVIDER_ERROR and len(created) == 2


def test_ready_trailing_data_fails_before_dispatch():
    from yasb_limitora.codex_helper import _PersistentTransport, _TransportError
    peeks = iter(((7, False), (4, False)))
    transport = _PersistentTransport(1, 2, peek=lambda fd: next(peeks), read=lambda fd, size: b"READY:n", nonblocking=True)
    rejected = []
    def acquire():
        try: transport.read_frame(expected_size=7)
        except _TransportError: rejected.append(True); raise
        raise AssertionError("trailing READY was accepted")
    supervisor = SimpleNamespace(acquire=acquire, close=lambda timeout: None)
    result = CodexHelperExecutor(lambda **kwargs: supervisor).run(("C:\\codex.exe",))
    assert result.error.code is SafeErrorCode.PROVIDER_ERROR
    assert rejected == [True]
