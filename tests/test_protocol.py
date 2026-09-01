import io
import struct

import pytest

from yasb_limitora import (
    ProviderKey,
    ProviderState,
    ProviderView,
    SafeError,
    SafeErrorCode,
)
from yasb_limitora.deadline import DeadlineContext
from yasb_limitora.isolation import (
    CONTROL_MAX_BYTES,
    RESPONSE_MAX_BYTES,
    ProtocolError,
    ProtocolErrorCode,
    ProtocolSession,
    ScriptedOutcome,
    ScriptedProviderExecutor,
    contained_message,
    decode_frame,
    encode_frame,
    error_message,
    go_message,
    message_view,
    read_frame,
    ready_message,
    result_message,
    write_frame,
)
from yasb_limitora.isolation.protocol import read_frame_with_deadline


class Transport(io.BytesIO):
    def __init__(self, data: bytes = b"", chunk: int = 2, error: Exception | None = None, deadline: bool = False) -> None:
        super().__init__()
        self.data, self.chunk, self.error, self.deadline, self.budgets = data, chunk, error, deadline, []
    def read(self, size: int, timeout_seconds: float) -> bytes:
        self.budgets.append(timeout_seconds)
        if self.error or (self.deadline and len(self.budgets) > 1):
            raise self.error or TimeoutError("secret deadline detail")
        part, self.data = self.data[: min(size, self.chunk)], self.data[min(size, self.chunk) :]
        return part
    def write(self, data: bytes, timeout_seconds: float) -> int:
        if self.error:
            raise self.error
        return super().write(data[:2])
def raw(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload
def test_frame_is_canonical_big_endian_and_partial_reads_round_trip() -> None:
    message = contained_message("nonce-✓")
    payload = '{"nonce":"nonce-✓","type":"contained"}'.encode("utf-8")
    frame = encode_frame(message)
    assert frame == raw(payload)
    assert decode_frame(frame) == message
    reader = Transport(frame)
    assert read_frame(reader, 1.0) == message
    assert reader.budgets == sorted(reader.budgets, reverse=True)
    output = Transport()
    write_frame(output, message, 1.0)
    assert output.getvalue() == frame
def test_frame_rejects_eof_trailing_and_oversized_data() -> None:
    message = encode_frame(contained_message("n"))
    for broken in (message[:-1], message + b"x"):
        with pytest.raises(ProtocolError) as error:
            decode_frame(broken)
        assert error.value.code in {ProtocolErrorCode.EOF, ProtocolErrorCode.TRAILING_BYTES}
    for limit in (CONTROL_MAX_BYTES, RESPONSE_MAX_BYTES):
        with pytest.raises(ProtocolError) as error:
            decode_frame(struct.pack(">I", limit + 1) + b"x", limit=limit)
        assert error.value.code is ProtocolErrorCode.OVERSIZE
def test_partial_read_exhausts_deadline_with_decreasing_budgets() -> None:
    reader = Transport(encode_frame(contained_message("n")), deadline=True)
    with pytest.raises(ProtocolError) as error:
        read_frame(reader, 1.0)
    assert error.value.code is ProtocolErrorCode.TRANSPORT_TIMEOUT
    assert reader.budgets[0] >= reader.budgets[1] > 0


def test_frame_adapter_keeps_the_original_absolute_endpoint():
    frame = encode_frame(contained_message("n"))
    reader = Transport(frame, chunk=1)
    clock = [0]
    context = DeadlineContext(t0_ns=0, deadline_ns=1_000_000, reserve_ns=0, clock_ns=lambda: clock[0])
    assert read_frame_with_deadline(reader, context) == contained_message("n")
    assert clock == [0]
@pytest.mark.parametrize("payload", [
    b"\xff", b"{bad", b'{"type":"contained","nonce":"a","nonce":"b"}',
    b'{"type":"contained","nonce":"a","extra":1}', b'{"type":"contained","nonce":NaN}', b'{"type":"wat","nonce":"a"}',
    b'{"display_label":"\\u0001","nonce":"a","provider":"codex","state":"success","type":"result"}',
])
def test_frame_rejects_encoding_json_duplicate_unknown_and_nan(payload: bytes) -> None:
    with pytest.raises(ProtocolError) as error:
        decode_frame(raw(payload))
    assert error.value.code in {
        ProtocolErrorCode.INVALID_UTF8, ProtocolErrorCode.INVALID_JSON,
        ProtocolErrorCode.DUPLICATE_KEY, ProtocolErrorCode.UNKNOWN_FIELD,
        ProtocolErrorCode.INVALID_MESSAGE,
    }
    assert "secret" not in str(error.value)
@pytest.mark.parametrize("failure, code", [
    (OSError("secret pipe path"), ProtocolErrorCode.TRANSPORT_FAILURE),
    (TimeoutError("secret timeout detail"), ProtocolErrorCode.TRANSPORT_TIMEOUT),
])
def test_transport_failures_are_safe_for_reads_and_writes(failure: Exception, code: ProtocolErrorCode) -> None:
    with pytest.raises(ProtocolError) as read_error:
        read_frame(Transport(error=failure), 1.0)
    with pytest.raises(ProtocolError) as write_error:
        write_frame(Transport(error=failure), contained_message("n"), 1.0)
    assert read_error.value.code is write_error.value.code is code
    assert "secret" not in str(read_error.value) + str(write_error.value)
def test_nonce_bound_state_machine_rejects_wrong_nonce_and_transitions() -> None:
    view = ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS)
    session = ProtocolSession("nonce")
    with pytest.raises(ProtocolError) as error:
        session.accept(ready_message("nonce"))
    assert error.value.code is ProtocolErrorCode.INVALID_TRANSITION
    with pytest.raises(ProtocolError) as error:
        session.accept(contained_message("private-workspace"))
    assert error.value.code is ProtocolErrorCode.NONCE_MISMATCH
    for message in (contained_message("nonce"), ready_message("nonce"), go_message("nonce"), result_message("nonce", view)):
        assert session.accept(message) == message
    with pytest.raises(ProtocolError) as error:
        session.accept(error_message("nonce", SafeErrorCode.INTERNAL_ERROR))
    assert error.value.code is ProtocolErrorCode.INVALID_TRANSITION
def test_result_and_error_schemas_round_trip_only_safe_view_fields() -> None:
    view = ProviderView(ProviderKey.OPENCODE_GO, ProviderState.SAFE_ERROR, SafeError("provider_error"), "成功")
    message = result_message("n", view)
    assert message_view(message) == view
    assert set(message) == {"type", "nonce", "provider", "state", "display_label", "error"}
    error = error_message("n", SafeErrorCode.TIMEOUT)
    assert decode_frame(encode_frame(error)) == error
    assert "private-workspace" not in str(error)
@pytest.mark.parametrize("state", list(ProviderState))
def test_scripted_fake_preserves_each_state_and_fixed_provider_order(state: ProviderState) -> None:
    error = SafeError(SafeErrorCode.PROVIDER_ERROR) if state is ProviderState.SAFE_ERROR else None
    fake = ScriptedProviderExecutor(
        ScriptedOutcome(ProviderView(ProviderKey.CODEX, state, error)),
        ScriptedOutcome(ProviderView(ProviderKey.OPENCODE_GO, ProviderState.UNAVAILABLE)),
    )
    document = fake.execute_all(1.0)
    assert tuple(view.provider for view in document.providers) == (ProviderKey.CODEX, ProviderKey.OPENCODE_GO)
    assert document.providers[0].state is state
def test_scripted_fake_maps_timeout_and_drops_late_result_without_mutation() -> None:
    late = ProviderView(ProviderKey.CODEX, ProviderState.SUCCESS, display_label="late-secret")
    fake = ScriptedProviderExecutor(ScriptedOutcome(late, delay_seconds=2, late=True), None)
    first = fake.execute(ProviderKey.CODEX, 1.0)
    second = fake.execute(ProviderKey.CODEX, 1.0)
    assert first == second == ProviderView(ProviderKey.CODEX, ProviderState.SAFE_ERROR, SafeError(SafeErrorCode.TIMEOUT))
    assert "late-secret" not in repr(first)
