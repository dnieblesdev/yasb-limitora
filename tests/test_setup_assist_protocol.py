"""S05 setup-assist protocol: nonce grammar, independent transport derivation, exclusive bounded request/result, strict schema refusal, sanitized non-stdout results."""

from __future__ import annotations

import inspect
import json
import ntpath

import pytest  # pyright: ignore[reportMissingImports]

import yasb_limitora.setup_assist as sa

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

def test_unimplemented_operation_is_bounded_nonfatal_refusal(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "path-add"}, {"operation": "discover"}]))
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 1
    result = result_of(root)
    assert result["status"] == "partial" and result["operations"][1]["status"] == "ok"
    assert result["operations"][0] == {"operation": "path-add", "status": "refused", "reason": "operation-unavailable"}

def test_preexisting_result_is_never_overwritten(tmp_path):
    la, root = transport(tmp_path, request_bytes([{"operation": "discover"}]))
    (root / "result.json").write_bytes(b"SENTINEL")
    assert run(la, {"USERPROFILE": str(tmp_path)}) == 1 and (root / "result.json").read_bytes() == b"SENTINEL"
