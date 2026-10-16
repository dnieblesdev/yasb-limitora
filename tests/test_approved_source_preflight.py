"""Trust-model tests for the approved-source preflight.

The central property is that a candidate cannot certify itself: authority must arrive as
an out-of-band frozen anchor authenticated by a separately pinned digest. These tests use
the pure comparison seam so no dedicated interpreter is required, and they drive the CLI
for the self-declaration and digest-binding paths.
"""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


preflight = _load("approved_source_preflight")
anchor_mod = _load("approved_source_anchor")

PACKAGE = "src/yasb_limitora"
MODULES = ("__init__.py", "_native_proof_observability.py", "model.py")


def _write_candidate(root: Path, body: dict[str, str]) -> Path:
    package = root / PACKAGE
    package.mkdir(parents=True)
    for name, text in body.items():
        # Binary write keeps the fixture byte-exact; text mode would inject CRLF here and
        # make every hash comparison fail for the wrong reason.
        (package / name).write_bytes(text.encode("utf-8"))
    return root


def _anchor_for(root: Path, body: dict[str, str], **overrides) -> dict:
    anchor = {
        "schema": 1,
        "approved_revision": "a" * 40,
        "approved_tree": "b" * 40,
        "version": "0.2.0",
        "files": {
            f"{PACKAGE}/{name}": hashlib.sha256(text.encode("utf-8")).hexdigest()
            for name, text in body.items()
        },
    }
    anchor.update(overrides)
    return anchor


BODY = {"__init__.py": '__version__ = "0.2.0"\n',
        "_native_proof_observability.py": "# observer\n",
        "model.py": "# model\n"}


# --- The trust boundary: a candidate must not certify itself ----------------------

def test_anchor_inside_candidate_is_refused(tmp_path: Path) -> None:
    """Self-declaration: an anchor shipped by the candidate is not authority."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    anchor = _anchor_for(root, BODY)
    inside = root / "approved-anchor.json"
    inside.write_bytes(preflight.canonical_anchor_bytes(anchor))
    digest = hashlib.sha256(inside.read_bytes()).hexdigest()
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.load_anchor(inside, digest, root)
    assert str(excinfo.value) == "ANCHOR_INSIDE_CANDIDATE"


def test_anchor_digest_must_match_the_pinned_value(tmp_path: Path) -> None:
    """Even an honest external anchor is rejected if it is not the pinned one."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    outside = tmp_path / "anchor.json"
    outside.write_bytes(preflight.canonical_anchor_bytes(_anchor_for(root, BODY, version="9.9.9")))
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.load_anchor(outside, "0" * 64, root)
    assert str(excinfo.value) == "ANCHOR_DIGEST_MISMATCH"


def test_noncanonical_anchor_bytes_are_refused(tmp_path: Path) -> None:
    """The digest must cover the exact published bytes, not an equivalent encoding."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    outside = tmp_path / "anchor.json"
    anchor = _anchor_for(root, BODY)
    padded = json.dumps(anchor, sort_keys=True, separators=(",", ":"), indent=1).encode("utf-8")
    outside.write_bytes(padded)
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.load_anchor(outside, hashlib.sha256(padded).hexdigest(), root)
    assert str(excinfo.value) == "ANCHOR_NONCANONICAL"


def test_anchor_missing_a_required_module_is_refused(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    outside = tmp_path / "anchor.json"
    broken = _anchor_for(root, BODY)
    broken["files"].pop(f"{PACKAGE}/_native_proof_observability.py")
    outside.write_bytes(preflight.canonical_anchor_bytes(broken))
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.load_anchor(outside, hashlib.sha256(outside.read_bytes()).hexdigest(), root)
    assert str(excinfo.value) == "ANCHOR_INVALID"


# --- Fail-closed comparison -------------------------------------------------------

def test_matching_candidate_is_accepted(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    verified = preflight.compare_candidate(root, _anchor_for(root, BODY))
    assert set(verified) == set(_anchor_for(root, BODY)["files"])


def test_crlf_checkout_is_not_a_divergence(tmp_path: Path) -> None:
    """A Windows checkout with core.autocrlf stores CRLF where the blob is LF.

    The anchor is derived from Git blobs, so a legitimate CRLF working tree must still be
    accepted; otherwise every Windows checkout would fail for a reason unrelated to the
    candidate being trusted.
    """
    root = tmp_path / "candidate"
    package = root / PACKAGE
    package.mkdir(parents=True)
    for name, text in BODY.items():
        (package / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    verified = preflight.compare_candidate(root, _anchor_for(root, BODY))
    assert len(verified) == len(BODY)


def test_line_ending_only_change_is_documented_as_accepted(tmp_path: Path) -> None:
    """Explicit documented limit: normalising to canonical form ignores EOL-only edits."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    (root / PACKAGE / "model.py").write_bytes(b"# model\r\n")
    verified = preflight.compare_candidate(root, _anchor_for(root, BODY))
    assert f"{PACKAGE}/model.py" in verified


def test_modified_module_hash_is_refused(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    (root / PACKAGE / "model.py").write_bytes(b"# tampered\n")
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.compare_candidate(root, _anchor_for(root, BODY))
    assert str(excinfo.value) == "HASH_MISMATCH"


@pytest.mark.parametrize("name", ["__init__.py", "_native_proof_observability.py"])
def test_missing_required_module_is_refused(tmp_path: Path, name: str) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    (root / PACKAGE / name).unlink()
    with pytest.raises(preflight.Rejected):
        preflight.compare_candidate(root, _anchor_for(root, BODY))


def test_unexpected_extra_module_is_refused(tmp_path: Path) -> None:
    """A candidate that adds a module is not the anchored tree."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    (root / PACKAGE / "injected.py").write_bytes(b"# unexpected\n")
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.compare_candidate(root, _anchor_for(root, BODY))
    assert str(excinfo.value) == "CANDIDATE_EXTRA_MODULE"


def test_path_escaping_the_package_is_refused(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    outside_file = root / "outside.py"
    outside_file.write_bytes(b"# outside\n")
    anchor = _anchor_for(root, BODY)
    anchor["files"]["outside.py"] = hashlib.sha256(outside_file.read_bytes()).hexdigest()
    with pytest.raises(preflight.Rejected) as excinfo:
        preflight.compare_candidate(root, anchor)
    assert str(excinfo.value) == "ANCHOR_INVALID"


# --- The anchor carrier itself ----------------------------------------------------

@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_anchor_freeze_matches_a_real_revision(tmp_path: Path) -> None:
    """The carrier derives tree, revision and hashes from Git, not from the candidate."""
    anchor = anchor_mod.collect(ROOT, "HEAD", "0.2.0")
    assert anchor["schema"] == 1
    assert len(anchor["approved_tree"]) == 40 and len(anchor["approved_revision"]) == 40
    assert f"{PACKAGE}/__init__.py" in anchor["files"]
    assert f"{PACKAGE}/_native_proof_observability.py" in anchor["files"]
    text = (ROOT / PACKAGE / "__init__.py").read_text(encoding="utf-8")
    assert anchor["files"][f"{PACKAGE}/__init__.py"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_anchor_digest_is_stable_and_content_bound() -> None:
    anchor = {"schema": 1, "approved_revision": "a" * 40, "approved_tree": "b" * 40,
              "version": "0.2.0", "files": {f"{PACKAGE}/__init__.py": "c" * 64}}
    first = anchor_mod.anchor_digest(anchor)
    assert first == anchor_mod.anchor_digest(dict(anchor))
    changed = dict(anchor, version="0.2.1")
    assert anchor_mod.anchor_digest(changed) != first


def test_anchor_script_rejects_an_unresolvable_revision(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-E", str(SCRIPTS / "approved_source_anchor.py"),
         "--repo", str(ROOT), "--revision", "0" * 40, "--version", "0.2.0",
         "--output", str(tmp_path / "anchor.json")],
        capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert payload["reason"] in {"ANCHOR_UNKNOWN", "CLI_INVALID"}
    assert not (tmp_path / "anchor.json").exists()


def test_preflight_cli_refuses_self_declared_anchor(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    inside = root / "anchor.json"
    inside.write_bytes(preflight.canonical_anchor_bytes(_anchor_for(root, BODY)))
    digest = hashlib.sha256(inside.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-E", str(SCRIPTS / "approved_source_preflight.py"),
         "--candidate-root", str(root), "--anchor", str(inside), "--anchor-sha256", digest,
         "--expected-executable", sys.executable],
        capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["reason"] == "ANCHOR_INSIDE_CANDIDATE"


def test_module_names_are_unique_for_nested_packages() -> None:
    """Subpackage __init__ files must not collide on the file stem."""
    assert preflight.module_name(f"{PACKAGE}/__init__.py") == "yasb_limitora"
    assert preflight.module_name(f"{PACKAGE}/model.py") == "yasb_limitora.model"
    assert preflight.module_name(f"{PACKAGE}/isolation/__init__.py") == "yasb_limitora.isolation"
    assert preflight.module_name(f"{PACKAGE}/isolation/fakes.py") == "yasb_limitora.isolation.fakes"
    names = [preflight.module_name(f"{PACKAGE}/isolation/__init__.py"),
             preflight.module_name(f"{PACKAGE}/widget/__init__.py"),
             preflight.module_name(f"{PACKAGE}/__init__.py")]
    assert len(set(names)) == len(names)


def test_self_declaration_is_reported_before_interpreter_gates(tmp_path: Path) -> None:
    """The trust violation must surface even when the interpreter is a plain venv/python.

    CI runs the suite under a non-dedicated interpreter, so if the interpreter gates ran
    first the self-declaration refusal would be masked by VENV_REQUIRED and the trust model
    would go untested in exactly the environment that matters.
    """
    root = _write_candidate(tmp_path / "candidate", BODY)
    inside = root / "anchor.json"
    inside.write_bytes(preflight.canonical_anchor_bytes(_anchor_for(root, BODY)))
    digest = hashlib.sha256(inside.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-E", str(SCRIPTS / "approved_source_preflight.py"),
         "--candidate-root", str(root), "--anchor", str(inside), "--anchor-sha256", digest,
         "--expected-executable", sys.executable],
        capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["reason"] == "ANCHOR_INSIDE_CANDIDATE"


def test_interpreter_gates_still_fail_closed_after_trust(tmp_path: Path) -> None:
    """A trustworthy anchor still does not pass without the dedicated interpreter."""
    root = _write_candidate(tmp_path / "candidate", BODY)
    outside = tmp_path / "anchor.json"
    outside.write_bytes(preflight.canonical_anchor_bytes(_anchor_for(root, BODY)))
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-E", str(SCRIPTS / "approved_source_preflight.py"),
         "--candidate-root", str(root), "--anchor", str(outside), "--anchor-sha256", digest,
         "--expected-executable", sys.executable],
        capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    # On a plain interpreter this is VENV_REQUIRED; under a venv other gates may apply.
    assert payload["reason"] in {"VENV_REQUIRED", "SYSTEM_SITE_FORBIDDEN", "FLAGS_INVALID",
                                 "EXECUTABLE_MISMATCH", "DISTRIBUTION_MISMATCH",
                                 "METADATA_UNKNOWN", "ORIGIN_MISMATCH"}


def test_failure_output_never_leaks_paths_or_details(tmp_path: Path) -> None:
    root = _write_candidate(tmp_path / "candidate", BODY)
    (root / PACKAGE / "model.py").write_bytes(b"# tampered\n")
    outside = tmp_path / "anchor.json"
    outside.write_bytes(preflight.canonical_anchor_bytes(_anchor_for(root, BODY)))
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-E", str(SCRIPTS / "approved_source_preflight.py"),
         "--candidate-root", str(root), "--anchor", str(outside), "--anchor-sha256", digest,
         "--expected-executable", sys.executable],
        capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"status", "reason"}
    assert payload["status"] == "FAIL"
    assert str(tmp_path) not in result.stdout
    assert "candidate" not in result.stdout
