import inspect
import os
import subprocess
import sys

import pytest

import yasb_limitora.codex_supervisor as s


def _bootstrap_wrapper():
    return (
        "import sys,types; m=types.ModuleType('msvcrt'); "
        "m.open_osfhandle=lambda handle,flags: handle; "
        "sys.modules['msvcrt']=m; exec(%r)"
        % s._BOOTSTRAP
    )


def _windows_startup_metadata(gate_read, data_write):
    import msvcrt

    child_handles = [
        msvcrt.get_osfhandle(data_write),
        msvcrt.get_osfhandle(gate_read),
    ]
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": child_handles}
    return child_handles, startup


def _reap(process):
    if process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _reset_inheritable(handles):
    for handle in reversed(handles):
        try:
            os.set_handle_inheritable(handle, False)
        except Exception:
            pass
    handles.clear()


def _run_real_bootstrap(signal, nonce, *, include_metadata=True):
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    process = None
    inheritable_handles = []
    try:
        if signal is not None:
            os.write(gate_write, signal)
        os.close(gate_write)
        gate_write = -1
        env = os.environ.copy()
        startupinfo = None
        if include_metadata:
            if os.name == "nt":
                child_handles, startupinfo = _windows_startup_metadata(
                    gate_read, data_write
                )
                env.update(
                    {
                        s._GATE_ENV: str(child_handles[1]),
                        s._DATA_ENV: str(child_handles[0]),
                        s._NONCE_ENV: nonce.decode("ascii"),
                    }
                )
                for handle in child_handles:
                    os.set_handle_inheritable(handle, True)
                    inheritable_handles.append(handle)
            else:
                env.update(
                    {
                        s._GATE_ENV: str(gate_read),
                        s._DATA_ENV: str(data_write),
                        s._NONCE_ENV: nonce.decode("ascii"),
                    }
                )
        argv = [sys.executable, "-I", "-S", "-E", "-c", s._BOOTSTRAP]
        if os.name == "nt":
            child_argv, extra = argv, {}
        else:
            child_argv, extra = [argv[0], *argv[1:-1], _bootstrap_wrapper()], {
                "pass_fds": (gate_read, data_write),
            }
        process = subprocess.Popen(
            child_argv,
            env=env,
            startupinfo=startupinfo,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **extra,
        )
        _reset_inheritable(inheritable_handles)
        os.close(gate_read)
        gate_read = -1
        os.close(data_write)
        data_write = -1
        code = process.wait(timeout=2)
        output = os.read(data_read, 4096)
        return code, output
    finally:
        _reset_inheritable(inheritable_handles)
        if process is not None:
            try:
                _reap(process)
            except Exception:
                pass
        for fd in (gate_read, gate_write, data_read, data_write):
            if fd >= 0:
                try:
                    os.close(fd)
                except Exception:
                    pass


def test_real_bootstrap_emits_exact_nonce_bound_ready_frame():
    code, output = _run_real_bootstrap(b"1", b"dynamic-nonce")
    assert code == 0
    assert output == b"READY:dynamic-nonce"


@pytest.mark.parametrize(
    ("signal", "include_metadata"),
    ((b"0", True), (b"1", False)),
)
def test_real_bootstrap_rejects_invalid_or_missing_metadata_without_ready(
    signal, include_metadata
):
    code, output = _run_real_bootstrap(
        signal,
        b"dynamic-nonce",
        include_metadata=include_metadata,
    )
    assert code == 1
    assert output == b""


def test_bootstrap_harness_reaps_live_child_with_bounded_cleanup():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _reap(process)
        assert process.poll() is not None
    finally:
        _reap(process)


def test_default_nonce_is_dynamic_and_ascii_safe():
    first, second = s._new_ready_nonce(), s._new_ready_nonce()
    assert first != second
    assert 0 < len(first) <= s._NONCE_LIMIT
    assert first.decode("ascii")
    assert second.decode("ascii")


def test_private_metadata_allowlist_and_directional_startup_contract():
    environment = s._environment(
        {
            "SystemRoot": "root",
            "PATH": "path",
            "OPENAI_API_KEY": "secret",
            s._GATE_ENV: "wrong-gate",
        },
        gate_read=41,
        data_write=42,
        nonce=b"nonce-04d1",
    )
    assert environment == {
        "SystemRoot": "root",
        "PATH": "path",
        s._GATE_ENV: "41",
        s._DATA_ENV: "42",
        s._NONCE_ENV: "nonce-04d1",
    }

    startup = s._startup([42, 41], lambda: type("Startup", (), {})())
    assert startup.lpAttributeList["handle_list"] == [42, 41]
    assert 43 not in startup.lpAttributeList["handle_list"]
    assert f"os.environ.pop({s._GATE_ENV!r})" in s._BOOTSTRAP
    assert f"os.environ.pop({s._DATA_ENV!r})" in s._BOOTSTRAP
    assert f"os.environ.pop({s._NONCE_ENV!r})" in s._BOOTSTRAP
    assert f"len(nonce)>{s._NONCE_LIMIT}" in s._BOOTSTRAP


def test_windows_cleanup_resets_handles_before_closing_descriptors():
    source = inspect.getsource(_run_real_bootstrap)
    assert source.index("_reset_inheritable(inheritable_handles)") < source.index(
        "os.close(gate_read)"
    )


@pytest.mark.skipif(os.name != "nt", reason="raw HANDLE contract is Windows-specific")
def test_windows_harness_uses_raw_directional_handles():
    gate_read, gate_write = os.pipe()
    data_read, data_write = os.pipe()
    try:
        import msvcrt

        handles, startup = _windows_startup_metadata(gate_read, data_write)
        assert handles == [
            msvcrt.get_osfhandle(data_write),
            msvcrt.get_osfhandle(gate_read),
        ]
        assert startup.lpAttributeList["handle_list"] == handles
    finally:
        os.close(gate_read)
        os.close(gate_write)
        os.close(data_read)
        os.close(data_write)


def test_private_surface_has_no_public_supervisor_or_provider_exports():
    assert s.__all__ == ()
    assert not hasattr(s, "Popen")
    assert not hasattr(s, "Limitora")
    assert not hasattr(s, "StatusClient")
    assert not hasattr(s, "activate_provider")
    assert all(name.startswith("_") for name in s.__dict__ if name not in {"__name__", "__doc__", "__package__", "__loader__", "__spec__", "__all__", "__builtins__"})
