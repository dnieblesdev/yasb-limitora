"""Private Codex helper bootstrap/readiness contract."""

import secrets as _secrets
import subprocess as _subprocess
import typing as _typing

__all__: tuple[str, ...] = ()

_GATE_ENV = "_YASB_CODEX_GATE_HANDLE"
_DATA_ENV = "_YASB_CODEX_DATA_HANDLE"
_NONCE_ENV = "_YASB_CODEX_READY_NONCE"
_NONCE_LIMIT = 128
_BOOTSTRAP = "\n".join(
    (
        "import os,msvcrt",
        "try:",
        f"    gate=msvcrt.open_osfhandle(int(os.environ.pop({_GATE_ENV!r})),0)",
        f"    data=msvcrt.open_osfhandle(int(os.environ.pop({_DATA_ENV!r})),1)",
        f"    nonce=os.environ.pop({_NONCE_ENV!r}).encode('ascii')",
        f"    if not nonce or len(nonce)>{_NONCE_LIMIT}: raise ValueError",
        "    signal=os.read(gate,1)",
        "    os.close(gate)",
        "    if signal != b'1':",
        "        os.close(data)",
        "        raise SystemExit(1)",
        "    payload=b'READY:'+nonce",
        "    written=os.write(data,payload)",
        "    os.close(data)",
        "    raise SystemExit(0 if written == len(payload) else 1)",
        "except SystemExit:",
        "    raise",
        "except Exception:",
        "    raise SystemExit(1)",
    )
)
_ENV_KEYS = (
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "CODEX_HOME",
)


def _environment(
    source: _typing.Mapping[str, str],
    *,
    gate_read: int,
    data_write: int,
    nonce: bytes,
) -> dict[str, str]:
    """Build the child environment without inheriting unrelated metadata."""
    if type(nonce) is not bytes or not 0 < len(nonce) <= _NONCE_LIMIT:
        raise ValueError("invalid readiness nonce")
    try:
        nonce_text = nonce.decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("invalid readiness nonce") from None
    environment = {key: source[key] for key in _ENV_KEYS if key in source}
    environment.update(
        {
            _GATE_ENV: str(gate_read),
            _DATA_ENV: str(data_write),
            _NONCE_ENV: nonce_text,
        }
    )
    return environment


def _startup(
    handles: _typing.Iterable[int],
    factory: _typing.Callable[[], _typing.Any] | None = None,
) -> _typing.Any:
    """Create startup metadata for exactly the child data-write/gate-read pair."""
    child_handles = list(handles)
    if len(child_handles) != 2 or len(set(child_handles)) != 2:
        raise ValueError("directional child handle list must contain two handles")
    try:
        startup = factory() if factory is not None else _subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": child_handles}
        return startup
    except Exception:
        raise ValueError("invalid startup metadata") from None


def _new_ready_nonce() -> bytes:
    """Generate a non-repeating ASCII-safe nonce for one helper handshake."""
    return _secrets.token_hex(32).encode("ascii")
