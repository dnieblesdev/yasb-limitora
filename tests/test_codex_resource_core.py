import importlib

import pytest

import yasb_limitora._codex_resource_core as r


def spec(number: int, generation: r._GenerationToken, closer) -> r._EndpointSpec:
    return r._new_endpoint_spec(number, generation, closer)


def test_pair_is_already_owned_and_hides_endpoint_construction() -> None:
    registry = r._GenerationRegistry()
    owner = r._OwnerToken()
    generation = r._GenerationToken()
    pair = r._new_ipc_pair(spec(5, generation, lambda identity: r._CloseOutcome.CLOSED), spec(6, generation, lambda identity: r._CloseOutcome.CLOSED), owner, registry)
    assert pair._owner is owner and pair._state is r._PairState.OPEN
    assert not hasattr(pair, "_claim") and not hasattr(r, "_new_endpoint")
    assert repr(pair) == "<_IpcPair>" and repr(spec(7, generation, lambda identity: None)) == "<_EndpointSpec>"


def test_pair_closes_reverse_order_and_retries_only_retry_outcomes() -> None:
    events: list[str] = []
    outcomes = {"write": [r._CloseOutcome.RETRY, r._CloseOutcome.CLOSED], "read": [r._CloseOutcome.CLOSED]}

    def closer(name: str):
        def close(identity: r._FdIdentity):
            events.append(name)
            return outcomes[name].pop(0)
        return close

    generation, owner, registry = r._GenerationToken(), r._OwnerToken(), r._GenerationRegistry()
    pair = r._new_ipc_pair(spec(5, generation, closer("read")), spec(6, generation, closer("write")), owner, registry)
    with pytest.raises(r._CleanupError): pair._close(owner)
    assert events == ["write", "read"] and pair._state is r._PairState.BROKEN
    pair._close(owner); pair._close(owner)
    assert events == ["write", "read", "write"] and pair._state is r._PairState.CLOSED and pair._read._spec is None and pair._write._spec is None


def test_transfer_prevalidates_both_endpoints_and_broken_pair_cannot_transfer() -> None:
    registry = r._GenerationRegistry()
    owner, replacement = r._OwnerToken(), r._OwnerToken()
    generation, replacement_generation = r._GenerationToken(), r._GenerationToken()
    pair = r._new_ipc_pair(spec(5, generation, lambda identity: r._CloseOutcome.CLOSED), spec(6, generation, lambda identity: r._CloseOutcome.CLOSED), owner, registry)
    replacement_pair = r._new_ipc_pair(spec(5, replacement_generation, lambda identity: r._CloseOutcome.CLOSED), spec(7, replacement_generation, lambda identity: r._CloseOutcome.CLOSED), replacement, registry)
    assert pair._owner is owner
    with pytest.raises(r._OwnershipError): pair._transfer(owner, replacement)
    assert pair._owner is owner
    replacement_pair._close(replacement)
    broken_registry = r._GenerationRegistry()
    broken_owner = r._OwnerToken()
    retry = [True]
    broken = r._new_ipc_pair(spec(8, generation, lambda identity: r._CloseOutcome.RETRY if retry and retry.pop() else r._CloseOutcome.CLOSED), spec(9, generation, lambda identity: r._CloseOutcome.CLOSED), broken_owner, broken_registry)
    with pytest.raises(r._CleanupError): broken._close(broken_owner)
    with pytest.raises(r._OwnershipError): broken._transfer(broken_owner, replacement)
    assert broken._owner is broken_owner
    broken._close(broken_owner)


def test_generation_registry_blocks_stale_close_and_transfer() -> None:
    calls: list[str] = []
    registry = r._GenerationRegistry()
    owner, replacement = r._OwnerToken(), r._OwnerToken()
    old_generation, new_generation = r._GenerationToken(), r._GenerationToken()
    old = r._new_ipc_pair(spec(5, old_generation, lambda identity: calls.append("old") or r._CloseOutcome.CLOSED), spec(6, old_generation, lambda identity: r._CloseOutcome.CLOSED), owner, registry)
    new = r._new_ipc_pair(spec(5, new_generation, lambda identity: calls.append("new") or r._CloseOutcome.CLOSED), spec(7, new_generation, lambda identity: r._CloseOutcome.CLOSED), replacement, registry)
    with pytest.raises(r._OwnershipError): old._transfer(owner, replacement)
    with pytest.raises(r._StaleGenerationError): old._close(owner)
    new._close(replacement)
    old._close(owner)
    assert calls == ["new"]


def test_retired_generation_cannot_reenter_after_aba_and_new_c_may_register() -> None:
    registry = r._GenerationRegistry()
    owner_a, owner_b, owner_c = r._OwnerToken(), r._OwnerToken(), r._OwnerToken()
    generation_a, generation_b, generation_c = r._GenerationToken(), r._GenerationToken(), r._GenerationToken()
    stale = spec(5, generation_a, lambda identity: r._CloseOutcome.CLOSED)
    pair_a = r._new_ipc_pair(stale, spec(6, generation_a, lambda identity: r._CloseOutcome.CLOSED), owner_a, registry)
    pair_a._close(owner_a)
    pair_b = r._new_ipc_pair(spec(5, generation_b, lambda identity: r._CloseOutcome.CLOSED), spec(7, generation_b, lambda identity: r._CloseOutcome.CLOSED), owner_b, registry)
    with pytest.raises(r._OwnershipError):
        r._new_ipc_pair(stale, spec(8, generation_a, lambda identity: r._CloseOutcome.CLOSED), owner_a, registry)
    with pytest.raises(r._StaleGenerationError): registry._close(stale)
    with pytest.raises(r._OwnershipError): pair_b._transfer(owner_a, owner_c)
    pair_b._close(owner_b)
    pair_c = r._new_ipc_pair(spec(5, generation_c, lambda identity: r._CloseOutcome.CLOSED), spec(9, generation_c, lambda identity: r._CloseOutcome.CLOSED), owner_c, registry)
    pair_c._close(owner_c)


def test_unexpected_close_is_terminal_and_never_retried_after_reuse() -> None:
    calls: list[str] = []
    registry = r._GenerationRegistry()
    owner, replacement = r._OwnerToken(), r._OwnerToken()
    old_generation, new_generation = r._GenerationToken(), r._GenerationToken()

    def closes_then_raises(identity: r._FdIdentity):
        calls.append("old")
        raise RuntimeError("after-side-effect")

    old = r._new_ipc_pair(spec(5, old_generation, closes_then_raises), spec(6, old_generation, lambda identity: r._CloseOutcome.CLOSED), owner, registry)
    with pytest.raises(r._IndeterminateCleanupError): old._close(owner)
    new = r._new_ipc_pair(spec(5, new_generation, lambda identity: calls.append("new") or r._CloseOutcome.CLOSED), spec(7, new_generation, lambda identity: r._CloseOutcome.CLOSED), replacement, registry)
    new._close(replacement)
    old._close(owner)
    assert calls == ["old", "new"]


def test_indeterminate_precedes_retry_when_write_retries_and_read_is_unknown() -> None:
    events: list[str] = []
    registry = r._GenerationRegistry()
    owner = r._OwnerToken()
    def read(identity: r._FdIdentity):
        events.append("read")
        raise RuntimeError("unknown")
    pair = r._new_ipc_pair(spec(5, r._GenerationToken(), read), spec(6, r._GenerationToken(), lambda identity: events.append("write") or r._CloseOutcome.RETRY), owner, registry)
    with pytest.raises(r._IndeterminateCleanupError): pair._close(owner)
    with pytest.raises(r._CleanupError): pair._close(owner)
    assert events == ["write", "read", "write"]


def test_indeterminate_precedes_retry_in_reverse_endpoint_setup() -> None:
    events: list[str] = []
    registry = r._GenerationRegistry()
    owner = r._OwnerToken()
    def write(identity: r._FdIdentity):
        events.append("write")
        raise RuntimeError("unknown")
    pair = r._new_ipc_pair(spec(5, r._GenerationToken(), lambda identity: events.append("read") or r._CloseOutcome.RETRY), spec(6, r._GenerationToken(), write), owner, registry)
    with pytest.raises(r._IndeterminateCleanupError): pair._close(owner)
    assert events == ["write", "read"]


def test_view_errors_and_public_surface_are_redacted_and_core_only() -> None:
    view = r._ResourceView("prepare")
    assert view._phase == "prepare" and repr(view) == "<_ResourceView>"
    with pytest.raises(AttributeError): view._phase = "other"
    assert repr(r._OwnerToken()) == "<_OwnerToken>" and repr(r._FdIdentity(5, r._GenerationToken())) == "<_FdIdentity>"
    assert repr(r._OwnershipError()) == "<_OwnershipError>" and repr(r._CleanupError()) == "<_CleanupError>"
    import yasb_limitora
    assert r.__all__ == () and not any(hasattr(yasb_limitora, name) for name in ("_IpcPair", "_OwnedEndpoint", "_FdIdentity"))
    assert not any(name in r.__dict__ for name in ("_AcquisitionOwner", "_CommittedOwner", "subprocess", "ctypes", "win32api"))
    with pytest.raises(ModuleNotFoundError): importlib.import_module("yasb_limitora.codex_resources")
