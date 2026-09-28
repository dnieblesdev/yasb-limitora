"""T1 custody checks for the versioned reusable VM proof harness source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "proof-harness"
MANIFEST = HARNESS / "source-manifest.json"
FIXTURE = HARNESS / "fixtures" / "scenario.json"

EXPECTED_MIGRATED_SOURCE_PATHS = {
    "guest/capture-state.ps1",
    "guest/hold-locked-file.ps1",
    "guest/run-setup-uninstall.ps1",
    "guest/watch-scenarios.ps1",
    "host/orchestrate-lifecycle.ps1",
    "host/verify-evidence.py",
    "host/roundtrip-verify.ps1",
}
EXPECTED_AUTHORED_SOURCE_PATHS = {
    "guest/bootstrap-watch.ps1",
    "host/run-reusable-vm.ps1",
    "host/new-run-volumes.ps1",
    "host/verify-reusable-evidence.py",
}
EXPECTED_SOURCE_PATHS = EXPECTED_MIGRATED_SOURCE_PATHS | EXPECTED_AUTHORED_SOURCE_PATHS

FORBIDDEN_GENERATED_SUFFIXES = {
    ".7z",
    ".exe",
    ".iso",
    ".log",
    ".vhdx",
}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_authored_source_manifest_is_complete_and_byte_bound() -> None:
    manifest = _manifest()
    entries = manifest["sources"]
    assert {entry["path"] for entry in entries} == EXPECTED_SOURCE_PATHS
    assert len(entries) == len(EXPECTED_SOURCE_PATHS)

    for entry in entries:
        path = HARNESS / entry["path"]
        payload = path.read_bytes()
        assert path.is_file()
        assert entry["size"] == len(payload)
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
        if entry["path"] in EXPECTED_MIGRATED_SOURCE_PATHS:
            assert entry["origin"].startswith("../yasb-limitora-")
            assert "build/" in entry["origin"]
        else:
            assert entry.get("kind") == "authored"
            assert entry["origin"] == "proof-harness/" + entry["path"]
            if entry["path"] == "guest/bootstrap-watch.ps1":
                assert entry.get("securityCritical") is True


def test_harness_tree_contains_no_generated_or_historical_payloads() -> None:
    files = [path for path in HARNESS.rglob("*") if path.is_file() and path.suffix.lower() != ".pyc"]
    assert all(path.suffix.lower() not in FORBIDDEN_GENERATED_SUFFIXES for path in files)
    assert not any(path.name.endswith(".tmp") for path in files)
    assert not any("evidence" in path.parts for path in files)
    assert not any("iso-staging" in path.parts for path in files)
    assert not any("#299" in path.read_text(encoding="utf-8", errors="ignore") for path in files)


def test_reusable_fixture_binds_runner_and_artifact_hashes() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema"] == "gentle-ai.yasb-limitora.reusable-vm-fixture/v1"
    assert fixture["inputVolumeLabel"] == "S11BINPUTS"
    assert fixture["evidenceVolumeLabel"] == "S11BEVIDENCE"
    assert fixture["scenario"] == "reusable-smoke"

    for name in ("runner", "expectedArtifact"):
        relative = Path(fixture[name]["path"])
        assert not relative.is_absolute()
        assert ".." not in relative.parts
        path = HARNESS / "fixtures" / relative
        payload = path.read_bytes()
        assert fixture[name]["size"] == len(payload)
        assert fixture[name]["sha256"] == hashlib.sha256(payload).hexdigest()

    assert fixture["runner"]["path"] == "runner.ps1"
    assert fixture["expectedArtifact"]["path"] == "expected-artifact.txt"
    assert fixture["runner"]["sha256"] != fixture["expectedArtifact"]["sha256"]


def test_t4_contract_fixtures_are_valid_and_deterministic() -> None:
    scenario_path = HARNESS / "fixtures" / "reusable-scenario.json"
    manifest_path = HARNESS / "fixtures" / "expected-artifacts.json"
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert scenario == {"schema": "gentle-ai.yasb-limitora.reusable-vm-run/v1", "scenario": "reusable-smoke"}
    assert manifest["schema"] == "gentle-ai.yasb-limitora.reusable-artifact-manifest/v1"
    for artifact in manifest["artifacts"]:
        path = HARNESS / "fixtures" / artifact["path"]
        assert path.is_file()
        assert artifact["size"] == path.stat().st_size
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (scenario_path, manifest_path):
        raw = path.read_bytes()
        assert raw.replace(b"\r\n", b"\n") == json.dumps(json.loads(raw), indent=2).encode() + b"\n"


def test_fixture_is_json_deterministic_and_declares_no_runtime_artifacts() -> None:
    raw = FIXTURE.read_bytes()
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    assert raw.replace(b"\r\n", b"\n") == canonical
    assert set(parsed) == {
        "schema",
        "scenario",
        "inputVolumeLabel",
        "evidenceVolumeLabel",
        "runner",
        "expectedArtifact",
    }
    assert not list((HARNESS / "fixtures").glob("*.iso"))
    assert not list((HARNESS / "fixtures").glob("*.vhdx"))
