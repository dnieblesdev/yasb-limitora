"""S05 setup-assist protocol: nonce grammar, independent transport derivation, exclusive bounded request/result, strict schema refusal, sanitized non-stdout results."""

from __future__ import annotations

import inspect
import io
import json
import ntpath
import os
import subprocess

import pytest  # pyright: ignore[reportMissingImports]

import yasb_limitora.setup_assist as sa
from yasb_limitora import cli

NONCE = "0123456789abcdef" * 2
V1 = "gentle-ai.yasb-limitora.setup-assist-request/v1"
LOCAL = r"C:\Users\u\AppData\Local"

class SpyFs:
    def __init__(self, kinds=None): self.kinds, self.calls = dict(kinds or {}), []
    def _resolve(self, path):
        self.calls.append(path)
        return self.kinds.get(path, "missing")
    def is_dir(self, path): return self._resolve(path) == "dir"
    def is_reparse(self, path): return self._resolve(path) == "unreadable"
    def file_kind(self, path): return self._resolve(path)

def transport(tmp_path, raw=None, nonce=NONCE):
    la, root = tmp_path / "la", tmp_path / "la" / "Temp" / "yasb-limitora-setup-assist" / nonce
    root.mkdir(parents=True)
    if raw is not None:
        (root / "request.json").write_bytes(raw)
    return la, root

def request_bytes(operations, **extra):
    return json.dumps({"schema": V1, "operations": operations, **extra}).encode()

def run(la, env=None, **kwargs):
    return sa._run_setup_assist({sa._NONCE_ENV: NONCE, **(env or {})}, local_appdata=str(la), **kwargs)

def result_of(root):
    return json.loads((root / "result.json").read_bytes())

def test_derivation_is_literal_two_input_and_outside_program_and_state_roots():
    assert list(inspect.signature(sa._derive_transport_root).parameters) == ["local_appdata", "nonce"]
    root = sa._derive_transport_root(LOCAL, NONCE)
    assert root == LOCAL + "\\Temp\\yasb-limitora-setup-assist\\" + NONCE == sa._derive_transport_root(LOCAL, NONCE)
    for sibling in (LOCAL + "\\Programs\\yasb-limitora", LOCAL + "\\yasb-limitora"):
        assert not root.startswith(sibling) and not sibling.startswith(root)

@pytest.mark.parametrize("value,valid", [("0" * 32, True), (NONCE, True), ("a1b2c3d4e5f60718293a4b5c6d7e8f90", True), ("", False), ("A" * 32, False), ("0" * 31, False), ("0" * 33, False), ("g" * 32, False), ("0" * 30 + "\\.", False), (None, False), (12345, False), ("0" * 16 + ".." + "0" * 14, False)])
def test_nonce_grammar(value, valid):
    assert sa._valid_nonce(value) is valid

def test_invalid_nonce_refuses_before_any_filesystem_access(tmp_path):
    fs = SpyFs()
    assert sa._run_setup_assist({sa._NONCE_ENV: "ABC123"}, local_appdata=str(tmp_path / "la"), fs=fs) == 1
    assert fs.calls == [] and not (tmp_path / "la").exists() and list(tmp_path.iterdir()) == []

def test_discover_and_running_use_transport_result_not_stdout(tmp_path, capsys):
    raw = request_bytes([{"operation": "discover"}, {"operation": "yasb-running"}])
    la, root = transport(tmp_path, raw)
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 0
    assert capsys.readouterr() == ("", "")  # stdout is never a consumed interface
    assert (root / "request.json").read_bytes() == raw
    result = result_of(root)
    assert set(result) == {"schema", "status", "operations"} and result["schema"] == "gentle-ai.yasb-limitora.setup-assist-result/v1"
    assert result["status"] == "complete" and [record["operation"] for record in result["operations"]] == ["discover", "yasb-running"]
    assert all(record["status"] == "ok" for record in result["operations"])
    facts = result["operations"][0]["facts"]
    assert facts["outcome"] in {"detected", "absent", "inconclusive"} and facts["process-status"] in {"running", "clear", "inconclusive"}
    text = (root / "result.json").read_text(encoding="utf-8")
    assert str(la) not in text and str(tmp_path) not in text and "Temp" not in text

def test_discovery_never_creates_program_or_state_roots(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 0
    assert not (la / "yasb-limitora").exists() and not (la / "Programs").exists()
    assert sorted(entry.name for entry in root.iterdir()) == ["request.json", "result.json"]

def test_missing_transport_refuses_without_creating_anything(tmp_path):
    la = tmp_path / "la"
    la.mkdir()
    assert run(la) == 1 and not (la / "Temp").exists()

def test_reparse_transport_component_refuses_without_result_write(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    fs = SpyFs({str(la): "dir", ntpath.join(str(la), "Temp"): "unreadable"})
    assert run(la, fs=fs) == 1 and fs.calls and not (root / "result.json").exists()

def test_missing_request_writes_bounded_refusal(tmp_path):
    la, root = transport(tmp_path)
    assert run(la) == 1 and result_of(root)["status"] == "refused"
    assert result_of(root)["operations"] == [{"operation": "request", "status": "refused", "reason": "request-missing"}]

def test_non_regular_request_file_refuses(tmp_path):
    la, root = transport(tmp_path)
    (root / "request.json").mkdir()
    assert run(la) == 1 and result_of(root)["operations"][0]["reason"] == "request-unsafe"

def test_oversize_request_refuses_and_preserves_bytes(tmp_path):
    raw = b"{" + b" " * (64 * 1024 + 1)
    la, root = transport(tmp_path, raw)
    assert run(la) == 1 and result_of(root)["operations"][0]["reason"] == "request-oversize"
    assert (root / "request.json").read_bytes() == raw

def test_result_creation_stays_exclusive_even_if_the_fs_view_is_stale(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    (root / "result.json").write_bytes(b"PLANTED")
    parent = ntpath.join(str(la), "Temp", "yasb-limitora-setup-assist")
    stale = SpyFs({str(la): "dir", ntpath.join(str(la), "Temp"): "dir", parent: "dir", str(root): "dir", ntpath.join(str(root), "request.json"): "file"})
    assert run(la, {"USERPROFILE": str(tmp_path)}, fs=stale) == 1  # O_EXCL must fail closed on the race
    assert (root / "result.json").read_bytes() == b"PLANTED"

VIOLATIONS = [
    (b"{not json", "request-malformed"),
    (b"[]", "request-malformed"),
    (b'{"schema": "x", "schema": "y", "operations": []}', "request-malformed"),
    (b'{"schema": "' + V1.encode() + b'", "operations": [{"operation": "discover", "x": Infinity}]}', "request-malformed"),
    (request_bytes([{"operation": "discover"}], schema=V1[:-2] + "v2"), "schema-violation"),
    (json.dumps({"schema": V1}).encode(), "schema-violation"),
    (request_bytes([]), "schema-violation"),
    (json.dumps({"schema": V1, "operations": "discover"}).encode(), "schema-violation"),
    (request_bytes([{"operation": "discover"}], transport_dir="C:\\x"), "schema-violation"),
    (request_bytes([{"operation": "wipe-everything"}]), "unknown-operation"),
    (request_bytes([{"operation": "discover"}, {"operation": "discover"}]), "duplicate-operation"),
    (request_bytes([{"operation": "discover", "consent": True}]), "schema-violation"),
    (request_bytes([{"operation": "discover", "target_path": "C:\\x"}]), "path-key-rejected"),
    (request_bytes([{"operation": "discover"}] * 9), "too-many-operations"),
]

@pytest.mark.parametrize("raw,reason", VIOLATIONS, ids=[str(index) for index in range(len(VIOLATIONS))])
def test_schema_violations_refuse_and_preserve_request_bytes(tmp_path, raw, reason):
    la, root = transport(tmp_path, raw)
    assert run(la) == 1 and (root / "request.json").read_bytes() == raw
    result = result_of(root)
    assert set(result) == {"schema", "status", "operations"} and result["status"] == "refused" and result["operations"][0]["reason"] == reason

def test_path_operation_uses_explicit_fake_and_never_constructs_real_registry(tmp_path, monkeypatch):
    class FakeRegistry:
        value, recorded, notifications = "A", None, 0

        def read_user_path(self):
            return self.value, 2

        def write_user_path(self, value, value_type):
            self.value = value

        def compare_and_write_user_path(self, expected, value, value_type):
            if self.read_user_path() != expected:
                return False
            self.write_user_path(value, value_type)
            return True

        def read_recorded_element(self):
            return self.recorded

        def write_recorded_element(self, element):
            self.recorded = element

        def clear_recorded_element(self):
            self.recorded = None

        def notify_environment_changed(self):
            self.notifications += 1

    fake = FakeRegistry()
    monkeypatch.setattr(sa._path_cleanup, "WindowsUserPathRegistry", lambda: (_ for _ in ()).throw(AssertionError("real registry")))
    la, root = transport(tmp_path, request_bytes([{"operation": "path-add"}, {"operation": "discover"}]))
    assert run(la, {"USERPROFILE": str(tmp_path)}, registry=fake) == 0
    result = result_of(root)
    assert result["status"] == "complete" and result["operations"][0] == {"operation": "path-add", "status": "ok"}
    assert fake.notifications == 1 and fake.recorded is not None

def test_env_block_choice_requires_explicit_true_consent(tmp_path):
    raw = request_bytes([{"operation": "env-block-apply", "consent": False}])
    la, root = transport(tmp_path, raw)
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 1
    assert result_of(root)["operations"] == [{"operation": "env-block-apply", "status": "refused", "reason": "env-consent-required"}]

def test_preexisting_result_is_never_overwritten(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    (root / "result.json").write_bytes(b"SENTINEL")
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 1 and (root / "result.json").read_bytes() == b"SENTINEL"

# --- S07-C2: state-cleanup consent schema and injected-registry protocol guard ---

def test_state_cleanup_requires_string_yes_consent_not_boolean(tmp_path):
    raw = request_bytes([{"operation": "state-cleanup", "consent": True}])
    la, root = transport(tmp_path, raw)
    assert run(la) == 1
    assert result_of(root)["operations"][0]["reason"] == "schema-violation"

def test_state_cleanup_without_consent_is_schema_violation(tmp_path):
    raw = request_bytes([{"operation": "state-cleanup"}])
    la, root = transport(tmp_path, raw)
    assert run(la) == 1
    assert result_of(root)["operations"][0]["reason"] == "schema-violation"

def test_state_cleanup_wrong_consent_string_is_schema_violation(tmp_path):
    raw = request_bytes([{"operation": "state-cleanup", "consent": "NO"}])
    la, root = transport(tmp_path, raw)
    assert run(la) == 1
    assert result_of(root)["operations"][0]["reason"] == "schema-violation"

def test_state_cleanup_with_yes_consent_uses_injected_registry_and_transports_result(tmp_path, monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc
    cleanup_mod = __import__("yasb_limitora._path_cleanup", fromlist=["_path_cleanup"])

    class FakeRegistry:
        value, recorded, notifications = "A", None, 0

        def read_user_path(self):
            return self.value, 2

        def write_user_path(self, v, t):
            self.value = v

        def compare_and_write_user_path(self, expected, v, t):
            if self.read_user_path() != expected:
                return False
            self.write_user_path(v, t)
            return True

        def read_recorded_element(self):
            return self.recorded

        def write_recorded_element(self, e):
            self.recorded = e

        def clear_recorded_element(self):
            self.recorded = None

        def notify_environment_changed(self):
            self.notifications += 1

    fake = FakeRegistry()
    cleanup_mod.append_user_path(fake, r"C:\bin")  # create a recorded element
    deleted: list[str] = []
    monkeypatch.setattr(nsc, "delete_directory", lambda p: (deleted.append(p), True)[1])
    la, root = transport(tmp_path, request_bytes([{"operation": "state-cleanup", "consent": "YES"}]))
    assert run(la, registry=fake) == 0
    result = result_of(root)
    assert result["status"] == "complete"
    assert result["operations"] == [{"operation": "state-cleanup", "status": "ok"}]
    assert deleted == [ntpath.join(str(la), "yasb-limitora")]
    assert fake.recorded is None  # record cleared after successful cleanup

def test_state_cleanup_refused_when_native_delete_fails(tmp_path, monkeypatch):
    import yasb_limitora._native_state_cleanup as nsc
    cleanup_mod = __import__("yasb_limitora._path_cleanup", fromlist=["_path_cleanup"])

    class FakeRegistry:
        value, recorded, notifications = "A", None, 0

        def read_user_path(self):
            return self.value, 2

        def write_user_path(self, v, t):
            self.value = v

        def compare_and_write_user_path(self, expected, v, t):
            if self.read_user_path() != expected:
                return False
            self.write_user_path(v, t)
            return True

        def read_recorded_element(self):
            return self.recorded

        def write_recorded_element(self, e):
            self.recorded = e

        def clear_recorded_element(self):
            self.recorded = None

        def notify_environment_changed(self):
            self.notifications += 1

    fake = FakeRegistry()
    cleanup_mod.append_user_path(fake, r"C:\bin")
    monkeypatch.setattr(nsc, "delete_directory", lambda p: False)
    la, root = transport(tmp_path, request_bytes([{"operation": "state-cleanup", "consent": "YES"}]))
    assert run(la, registry=fake) == 1
    result = result_of(root)
    assert result["operations"] == [{"operation": "state-cleanup", "status": "refused", "reason": "state-delete-failed"}]

# --- TOCTOU: nonce directory substituted by a junction after validation, before each I/O boundary ---

needs_nt = pytest.mark.skipif(os.name != "nt", reason="real junction substitution is Windows-only")

def make_junction(link, target):
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, AttributeError, OSError):  # pragma: no cover - fallback for exotic hosts
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)

class SwapFs:
    """Real FsView that performs the attacker swap on the first probe of `trigger`.

    Simulates the exact race the precheck cannot close: the nonce directory passes
    component/kind validation, then is replaced by a junction to an attacker-chosen
    directory before the request open or the result creation reaches the filesystem.
    """

    def __init__(self, trigger, swap):
        self.trigger, self.swap, self.done = trigger, swap, False

    def is_dir(self, path):
        return sa.discovery.REAL_FS.is_dir(path)

    def is_reparse(self, path):
        return sa.discovery.REAL_FS.is_reparse(path)

    def file_kind(self, path):
        if not self.done and ntpath.normcase(path) == ntpath.normcase(self.trigger):
            self.done = True
            self.swap()
        return sa.discovery.REAL_FS.file_kind(path)

def substitute_with_junction(root, attacker):
    """Move the validated nonce directory aside and re-create it as a junction to `attacker`."""
    attacker.mkdir(parents=True, exist_ok=True)
    os.rename(str(root), str(root) + "-orig")
    make_junction(root, attacker)
    return str(root) + "-orig"

@needs_nt
def test_request_open_rejects_nonce_directory_swapped_to_junction_after_validation(tmp_path):
    raw = request_bytes([{"operation": "discover"}])
    la, root = transport(tmp_path, raw)
    attacker = tmp_path / "attacker"
    swap_state = {"armed": True}

    def swap():
        if swap_state["armed"]:
            swap_state["armed"] = False
            attacker.mkdir(parents=True, exist_ok=True)
            (attacker / "request.json").write_bytes(request_bytes([{"operation": "yasb-running"}]))
            substitute_with_junction(root, attacker)

    fs = SwapFs(ntpath.join(str(root), "request.json"), swap)
    assert sa._run_setup_assist({sa._NONCE_ENV: NONCE}, local_appdata=str(la), fs=fs) == 1
    assert fs.done and swap_state["armed"] is False  # the race actually fired
    assert not (attacker / "result.json").exists()  # nothing written through the junction
    assert not (root.parent / (root.name + "-orig") / "result.json").exists()
    assert sorted(entry.name for entry in attacker.iterdir()) == ["request.json"]  # no stray artifacts

@needs_nt
def test_result_creation_rejects_nonce_directory_swapped_to_junction_after_request_read(tmp_path):
    raw = request_bytes([{"operation": "discover"}])
    la, root = transport(tmp_path, raw)
    attacker = tmp_path / "attacker"
    swap_state = {"armed": True}

    def swap():
        if swap_state["armed"]:
            swap_state["armed"] = False
            attacker.mkdir(parents=True, exist_ok=True)
            substitute_with_junction(root, attacker)

    fs = SwapFs(ntpath.join(str(root), "result.json"), swap)
    assert sa._run_setup_assist({sa._NONCE_ENV: NONCE}, local_appdata=str(la), fs=fs) == 1
    assert fs.done and swap_state["armed"] is False  # the swap fired at the result boundary
    assert list(attacker.iterdir()) == []  # no result.json and no stray exclusive-created remnant
    preserved = root.parent / (root.name + "-orig")
    assert (preserved / "request.json").read_bytes() == raw and not (preserved / "result.json").exists()

@needs_nt
def test_read_request_fails_closed_when_parent_is_already_a_junction(tmp_path):
    _la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    (attacker / "request.json").write_bytes(request_bytes([{"operation": "yasb-running"}]))
    os.rename(str(root), str(root) + "-orig")
    make_junction(root, attacker)
    data, defect = sa._read_request(ntpath.join(str(root), "request.json"), sa.discovery.REAL_FS)
    assert data is None and defect == "request-unsafe"  # planted bytes behind the junction are never consumed

@needs_nt
def test_write_result_fails_closed_and_removes_stray_when_root_is_a_junction(tmp_path):
    _la, root = transport(tmp_path)
    attacker = tmp_path / "attacker"
    substitute_with_junction(root, attacker)
    assert sa._write_result(str(root), {"schema": "x"}, sa.discovery.REAL_FS) is False
    assert list(attacker.iterdir()) == []  # exclusively created remnant removed; attacker gains nothing

# --- Environment-carried request transport (active path) ---

def test_env_carried_request_with_valid_operations_exits_zero():
    raw = request_bytes([{"operation": "discover"}])
    assert sa._run_setup_assist({sa._REQUEST_ENV: raw.decode(), "USERPROFILE": r"C:\Users\u"}) == 0

def test_env_carried_request_with_schema_violation_exits_one():
    raw = request_bytes([{"operation": "unknown-op"}])
    assert sa._run_setup_assist({sa._REQUEST_ENV: raw.decode()}) == 1

def test_env_carried_request_empty_falls_through_to_nonce_path():
    # Empty request env falls through to the legacy nonce path, which also fails
    assert sa._run_setup_assist({sa._REQUEST_ENV: ""}) == 1

def test_env_carried_request_no_filesystem_artifacts(tmp_path):
    raw = request_bytes([{"operation": "discover"}])
    la = tmp_path / "la"
    la.mkdir()
    assert sa._run_setup_assist({sa._REQUEST_ENV: raw.decode(), "USERPROFILE": str(tmp_path)}, local_appdata=str(la)) == 0
    # No request.json or result.json created
    assert not (la / "Temp").exists()

def test_nonce_only_does_not_dispatch_setup_assist(monkeypatch):
    dispatched = False

    def unexpected_dispatch(_environment):
        nonlocal dispatched
        dispatched = True
        return 0

    monkeypatch.setattr(cli, "_run_setup_assist", unexpected_dispatch)
    assert cli.main(
        argv=(sa._SETUP_ASSIST_FLAG,),
        environment={sa._NONCE_ENV: NONCE},
        stdout=io.BytesIO(),
        stderr=io.StringIO(),
        platform_is_windows=lambda: True,
    ) == 2
    assert not dispatched

# --- C1: Inno/Python request-schema alignment regression tests ---
# The Inno Setup producer must generate typed operation objects that satisfy
# Python's strict {schema, operations} validator. The old format used a
# separate "choices" array and string-typed operations, which the validator
# correctly rejects as schema-violation. These tests lock the aligned format.

def _inno_post_install_request(
    add_path: bool,
    env_block: bool,
    config_wizard: bool = False,
    codex_choice: str = "unchanged",
    opencode_choice: str = "unchanged",
    codex_runner: str = "",
) -> bytes:
    """Build the exact request bytes the Slice 2 Inno InvokePostCommitAssist produces.

    Runner is serialized only when codex_choice == "enabled".
    """
    ops: list[dict[str, object]] = []
    if add_path:
        ops.append({"operation": "path-add"})
    if env_block:
        ops.append({"operation": "env-block-apply", "consent": True})
    if config_wizard:
        selection: dict[str, object] = {}
        if codex_choice != "unchanged":
            entry: dict[str, object] = {"enabled": codex_choice == "enabled"}
            if codex_choice == "enabled" and codex_runner:
                entry["runner"] = codex_runner
            selection["codex"] = entry
        if opencode_choice != "unchanged":
            selection["opencode_go"] = {"enabled": opencode_choice == "enabled"}
        if selection:
            ops.append({"operation": "config-apply", "selection": selection})
    if not ops:
        ops.append({"operation": "discover"})
    return json.dumps({"schema": V1, "operations": ops}).encode()

def _inno_uninstall_request() -> bytes:
    """Build the exact request bytes the fixed Inno InvokeUninstallAssist produces."""
    return json.dumps({"schema": V1, "operations": [{"operation": "state-cleanup", "consent": "YES"}]}).encode()

def test_c1_inno_post_install_request_with_path_and_env_passes_validation():
    """The aligned Inno post-install request (path-add + env-block-apply) passes validation."""
    raw = _inno_post_install_request(add_path=True, env_block=True)
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    assert names == (("path-add", True), ("env-block-apply", True))

def test_slice2_all_unchanged_falls_back_to_discover():
    """When all provider choices are unchanged, configassist uses discover fallback."""
    raw = _inno_post_install_request(add_path=False, env_block=False, config_wizard=True)
    payload = json.loads(raw)
    op_names = [op["operation"] for op in payload["operations"]]
    assert "config-apply" not in op_names
    assert "discover" in op_names


def test_slice2_explicit_codex_enabled_emits_config_apply_with_runner():
    """Explicit codex enabled emits config-apply with selection including runner."""
    raw = _inno_post_install_request(
        add_path=False, env_block=False, config_wizard=True,
        codex_choice="enabled", codex_runner=r"C:\tools\codex.exe",
    )
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    payload = json.loads(raw)
    config_op = next(op for op in payload["operations"] if op["operation"] == "config-apply")
    assert config_op["selection"]["codex"]["enabled"] is True
    assert config_op["selection"]["codex"]["runner"] == r"C:\tools\codex.exe"


def test_slice2_codex_disabled_omits_runner():
    """Codex disabled must not serialize runner, even if stale text is present."""
    raw = _inno_post_install_request(
        add_path=False, env_block=False, config_wizard=True,
        codex_choice="disabled", codex_runner=r"C:\stale\codex.exe",
    )
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    payload = json.loads(raw)
    config_op = next(op for op in payload["operations"] if op["operation"] == "config-apply")
    assert config_op["selection"]["codex"]["enabled"] is False
    assert "runner" not in config_op["selection"]["codex"]


def test_slice2_unchanged_provider_omitted_from_selection():
    """unchanged means the provider key is omitted from selection."""
    raw = _inno_post_install_request(
        add_path=False, env_block=False, config_wizard=True,
        codex_choice="enabled", codex_runner=r"C:\x.exe",
        opencode_choice="unchanged",
    )
    payload = json.loads(raw)
    config_op = next(op for op in payload["operations"] if op["operation"] == "config-apply")
    assert "codex" in config_op["selection"]
    assert "opencode_go" not in config_op["selection"]


def test_slice2_opencode_disabled_passes_validation():
    """Explicit opencode_go disabled passes Python validation."""
    raw = _inno_post_install_request(
        add_path=False, env_block=False, config_wizard=True,
        opencode_choice="disabled",
    )
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    payload = json.loads(raw)
    config_op = next(op for op in payload["operations"] if op["operation"] == "config-apply")
    assert config_op["selection"]["opencode_go"]["enabled"] is False


def test_slice2_configassist_with_path_env_and_codex_enabled():
    """Combined: path-add + env-block-apply + config-apply with codex enabled."""
    raw = _inno_post_install_request(
        add_path=True, env_block=True, config_wizard=True,
        codex_choice="enabled", codex_runner=r"C:\tools\codex.exe",
    )
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    assert names == (
        ("path-add", True),
        ("env-block-apply", True),
        ("config-apply", {"codex": {"enabled": True, "runner": r"C:\tools\codex.exe"}}),
    )

def test_c1_inno_post_install_request_discover_only_passes_validation():
    """When no user operations are selected, Inno sends discover only."""
    raw = _inno_post_install_request(add_path=False, env_block=False)
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    assert names == (("discover", True),)

def test_c1_inno_uninstall_request_passes_validation():
    """The aligned Inno uninstall request (state-cleanup with YES consent) passes validation."""
    raw = _inno_uninstall_request()
    names, violation = sa._validate_request(raw)
    assert violation is None and names is not None
    assert names == (("state-cleanup", "YES"),)

def test_c1_old_inno_format_with_choices_is_rejected():
    """Regression guard: the old Inno format with a choices key is rejected."""
    old_request = json.dumps({
        "schema": V1,
        "operations": ["path-add", "env-block-apply"],
        "choices": ["addtopath", "envassist"]
    }).encode()
    names, violation = sa._validate_request(old_request)
    assert violation == "schema-violation" and names is None

def test_c1_old_inno_string_operations_are_rejected():
    """Regression guard: string-typed operations (old Inno format) are rejected."""
    old_request = json.dumps({
        "schema": V1,
        "operations": ["state-cleanup"]
    }).encode()
    names, violation = sa._validate_request(old_request)
    assert violation == "schema-violation" and names is None


def test_reason_not_written_when_env_not_set(tmp_path):
    reason_file = tmp_path / "reason.txt"
    raw = request_bytes([{"operation": "unknown-op"}])
    assert sa._run_setup_assist({sa._REQUEST_ENV: raw.decode(), "_YASB_SETUP_ASSIST_REASON": str(reason_file)}) == 1
    assert not reason_file.exists() and not hasattr(sa, "_REASON_ENV")
