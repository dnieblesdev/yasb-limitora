from __future__ import annotations
import hashlib, inspect, io, stat, traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
import pytest
from tests import r10_yasb_acquisition as acquisition

class _Response:
    def __init__(self, url, payload):
        self.url, self.stream, self.headers = url, io.BytesIO(payload), {"Content-Length": str(len(payload))}
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return self.url
    def read(self, size): return self.stream.read(size)

def _fixture():
    payloads, artifacts, sources = {}, [], []
    for kind, name in (("wheel", "demo.whl"), ("source", "yasb")):
        url, payload = f"https://example.invalid/{name}", kind.encode(); payloads[url] = payload
        target = {"filename": name, "url": url, "sha256": hashlib.sha256(payload).hexdigest()} if kind == "wheel" else {"name": name, "archive_url": url, "archive_sha256": hashlib.sha256(payload).hexdigest()}
        (artifacts if kind == "wheel" else sources).append(target)
    return {"artifacts": artifacts, "sources": sources}, payloads

def _open(payloads): return lambda url, **_: _Response(url, payloads[url])
def _expected(): return {Path("wheelhouse/demo.whl"): ("u", "h"), Path("sources/yasb.tar.gz"): ("u", "h")}
def _bundle(tmp_path, files=()):
    root = tmp_path / "bundle"; (root / "wheelhouse").mkdir(parents=True); (root / "sources").mkdir()
    for relative in files: (root / relative).write_bytes(b"x")
    return root
def _configure(monkeypatch, tmp_path):
    manifest, payloads = _fixture(); monkeypatch.setattr(acquisition, "validate_manifest", lambda _: None)
    monkeypatch.setattr(acquisition.tempfile, "gettempdir", lambda: str(tmp_path)); return manifest, payloads

def test_success_consumes_merged_manifest_and_removes_bundle(monkeypatch, tmp_path):
    manifest, payloads = _configure(monkeypatch, tmp_path)
    with acquisition.acquire_artifact_bundle(manifest=manifest, opener=_open(payloads)) as bundle:
        assert sorted(p.name for p in bundle.rglob("*")) == ["demo.whl", "sources", "wheelhouse", "yasb.tar.gz"]
        retained = bundle
    assert not retained.exists()

def test_primary_failure_keeps_instance_and_causal_trace(monkeypatch, tmp_path):
    manifest, payloads = _configure(monkeypatch, tmp_path); primary = ValueError("primary")
    def raise_primary(): raise primary
    with pytest.raises(ValueError) as raised:
        with acquisition.acquire_artifact_bundle(manifest=manifest, opener=_open(payloads)): raise_primary()
    assert raised.value is primary and any(f.name == "raise_primary" for f in traceback.extract_tb(primary.__traceback__))

def test_cleanup_only_exception_is_chained_and_path_free(monkeypatch, tmp_path):
    manifest, payloads = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(Path, "unlink", lambda *_: (_ for _ in ()).throw(OSError("private cleanup detail")))
    with pytest.raises(acquisition.ArtifactCleanupError) as raised:
        with acquisition.acquire_artifact_bundle(manifest=manifest, opener=_open(payloads)): pass
    error = raised.value
    assert isinstance(error.__cause__, OSError) and error.evidence.residue == "unknown"
    assert error.evidence is error.cleanup_evidence
    assert "private cleanup detail" not in repr(error.evidence) and error.__notes__.count(acquisition.NOTE) == 1

def test_both_failures_keep_primary_and_attach_one_immutable_evidence(monkeypatch, tmp_path):
    manifest, payloads = _configure(monkeypatch, tmp_path); primary = RuntimeError("primary")
    cause = OSError("cause")
    def raise_primary():
        try: raise cause
        except OSError as error: raise primary from error
    monkeypatch.setattr(Path, "unlink", lambda *_: (_ for _ in ()).throw(OSError("cleanup")))
    with pytest.raises(RuntimeError) as raised:
        with acquisition.acquire_artifact_bundle(manifest=manifest, opener=_open(payloads)): raise_primary()
    assert raised.value is primary and raised.value.__cause__ is cause and raised.value.cleanup_evidence.residue == "unknown"
    assert any(frame.name == "raise_primary" for frame in traceback.extract_tb(primary.__traceback__))
    evidence = raised.value.cleanup_evidence
    acquisition._attach(primary, evidence)
    assert primary.cleanup_evidence is evidence and primary.__notes__.count(acquisition.NOTE) == 1
    with pytest.raises(FrozenInstanceError): raised.value.cleanup_evidence.residue = "absent"

@pytest.mark.parametrize("interruption", (KeyboardInterrupt, SystemExit))
def test_cleanup_interruptions_are_not_swallowed(monkeypatch, tmp_path, interruption):
    root = _bundle(tmp_path, ("wheelhouse/demo.whl",)); monkeypatch.setattr(Path, "unlink", lambda *_: (_ for _ in ()).throw(interruption()))
    with pytest.raises(interruption) as raised: acquisition._cleanup(root, _expected())
    assert raised.value.cleanup_evidence.residue == "unknown"

@pytest.mark.parametrize("unsafe", ("unexpected", "root-unexpected", "symlink", "reparse", "nonregular"))
def test_full_preflight_rejects_unsafe_tree_before_mutation(tmp_path, monkeypatch, unsafe):
    root = _bundle(tmp_path, ("wheelhouse/demo.whl",))
    if unsafe in ("unexpected", "root-unexpected"): (root / ("other" if unsafe == "root-unexpected" else "sources/other")).write_bytes(b"x")
    elif unsafe == "symlink": (root / "sources/yasb.tar.gz").symlink_to(root / "wheelhouse/demo.whl")
    elif unsafe == "nonregular": (root / "sources/yasb.tar.gz").mkdir()
    else:
        real = acquisition._classify; monkeypatch.setattr(acquisition, "_classify", lambda path, info: "reparse" if path.name == "demo.whl" else real(path, info))
    with pytest.raises(acquisition.ArtifactCleanupError) as raised: acquisition._cleanup(root, _expected())
    assert (root / "wheelhouse/demo.whl").is_file() and raised.value.evidence.removed_files == 0

def test_late_unsafe_entry_has_no_prior_mutation(tmp_path):
    root = _bundle(tmp_path, ("wheelhouse/demo.whl", "sources/yasb.tar.gz")); (root / "sources/late").write_bytes(b"x")
    with pytest.raises(acquisition.ArtifactCleanupError): acquisition._cleanup(root, _expected())
    assert (root / "wheelhouse/demo.whl").is_file() and (root / "sources/yasb.tar.gz").is_file()

def test_partials_are_allowed_but_final_and_part_together_are_not(tmp_path):
    root = _bundle(tmp_path, ("wheelhouse/demo.whl.part",)); evidence = acquisition._cleanup(root, _expected())
    assert evidence.residue == "absent" and evidence.removed_files == 1
    root = _bundle(tmp_path / "both", ("wheelhouse/demo.whl", "wheelhouse/demo.whl.part"))
    with pytest.raises(acquisition.ArtifactCleanupError) as raised: acquisition._cleanup(root, _expected())
    assert raised.value.evidence.residue == "present"

def test_postcondition_and_truthful_absent_present_unknown(monkeypatch, tmp_path):
    assert acquisition._cleanup(tmp_path / "missing", _expected()).residue == "absent"
    root = _bundle(tmp_path / "post", ("wheelhouse/demo.whl",)); monkeypatch.setattr(Path, "unlink", lambda *_: None)
    with pytest.raises(acquisition.ArtifactCleanupError) as raised: acquisition._cleanup(root, _expected())
    assert raised.value.evidence.residue == "present"
    root = _bundle(tmp_path / "unknown", ("wheelhouse/demo.whl",)); original = acquisition._lstat
    monkeypatch.setattr(acquisition, "_lstat", lambda path: (_ for _ in ()).throw(OSError("unknown")) if path == root else original(path))
    with pytest.raises(acquisition.ArtifactCleanupError) as raised: acquisition._cleanup(root, _expected())
    assert raised.value.evidence.residue == "unknown"

def test_cleanup_contract_is_bounded_and_no_following_recursive_api():
    source = inspect.getsource(acquisition)
    assert not {"rmtree", "ignore_errors", ".exists("} & {word for word in ("rmtree", "ignore_errors", ".exists(") if word in source}
    assert acquisition.REPARSE_POINT == 0x400 and acquisition._classify(Path("x"), SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0)) == "file"
