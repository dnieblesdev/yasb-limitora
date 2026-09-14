"""S03 contract: immutable, deterministic release-manifest/v1 identity records — schema/identity,
exact digests/sizes, SBOM/build-info bindings, coreutils SHA256SUMS, bounded CLI exits, fail-closed
rejection of forbidden/secret fields, absolute/UNC/`..` names, `-rc` identity, overwrite, tampering."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA = "gentle-ai.yasb-limitora.release-manifest/v1"
_ARTIFACTS = ["yasb-limitora-0.2.0-setup.exe", "extra-artifact.bin"]
_BUILD_INFO = {"version": "0.2.0", "source_commit": "528313c972e14ef72f784ada0284ac7fdf5a5d82",
               "python": "3.13.1", "pyinstaller": "6.11.1", "limitora": "0.3.1",
               "source_date_epoch": "1700000000"}
_REJECTED_FIELDS = ([(key, "forbidden_field") for key in (
    "gates", "gate_status", "approval", "evidence_refs", "custody_location", "acceptance_run_id",
    "build_run_id", "post_publication", "status", "published_at", "verdict")]
    + [(key, "secret_bearing") for key in ("build_token", "api_key", "provider_secret", "password")])


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("s03_manifest", _ROOT / "scripts" / "make_release_manifest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def candidate(tmp_path: Path) -> Path:
    root = tmp_path / "candidate"
    (root / "_internal").mkdir(parents=True)
    files = {"_internal/build-info.json": json.dumps(_BUILD_INFO, indent=2, sort_keys=True) + "\n",
             "sbom.cdx.json": '{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}',
             "yasb-limitora-0.2.0-setup.exe": "MZ-setup-candidate-bytes", "extra-artifact.bin": "extra-artifact-bytes"}
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


@pytest.fixture()
def generated(mod, candidate, tmp_path) -> SimpleNamespace:
    out = tmp_path / "out"
    mod.generate(candidate_root=candidate, out_dir=out, artifact_names=list(_ARTIFACTS))
    text = (out / "rc-manifest.json").read_text(encoding="utf-8")
    return SimpleNamespace(mod=mod, candidate=candidate, out=out, text=text,
                           manifest_path=out / "rc-manifest.json", manifest=json.loads(text))


class TestGeneration:
    def test_schema_identity_and_deterministic_bytes(self, mod, candidate, generated, tmp_path):
        manifest = generated.manifest
        assert manifest["schema"] == _SCHEMA and manifest["version"] == "0.2.0" and "-rc" not in generated.text
        assert list(manifest) == sorted({"schema", "version", "source_commit", "source_date_epoch",
                                         "tools", "artifacts", "sbom", "build_info"})
        assert [entry["name"] for entry in manifest["artifacts"]] == sorted(_ARTIFACTS)
        assert manifest["source_commit"] == _BUILD_INFO["source_commit"]
        assert manifest["source_date_epoch"] == _BUILD_INFO["source_date_epoch"]
        assert manifest["tools"] == {"python": "3.13.1", "pyinstaller": "6.11.1", "limitora": "0.3.1"}
        second = tmp_path / "o2"
        mod.generate(candidate_root=candidate, out_dir=second, artifact_names=list(_ARTIFACTS))
        assert generated.text == (second / "rc-manifest.json").read_text(encoding="utf-8")

    def test_exact_sha256_sizes_and_bindings(self, generated):
        manifest = generated.manifest
        for entry in [*manifest["artifacts"], manifest["sbom"], manifest["build_info"]]:
            blob = (generated.candidate / entry["name"]).read_bytes()
            assert entry["sha256"] == hashlib.sha256(blob).hexdigest()
        for entry in manifest["artifacts"]:
            assert entry["size"] == (generated.candidate / entry["name"]).stat().st_size

    def test_sha256sums_coreutils_format(self, generated):
        lines = (generated.out / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        names = [line.split("  ", 1)[1] for line in lines]
        assert names == sorted(names)
        assert set(names) == set(_ARTIFACTS) | {"sbom.cdx.json", "_internal/build-info.json"}
        for line in lines:
            digest, name = line.split("  ", 1)
            assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
            assert hashlib.sha256((generated.candidate / name).read_bytes()).hexdigest() == digest

    def test_refuses_to_overwrite_existing_records(self, mod, candidate, generated):
        with pytest.raises(mod.ManifestError, match="manifest_exists"):
            mod.generate(candidate_root=candidate, out_dir=generated.out, artifact_names=list(_ARTIFACTS))
        assert generated.manifest_path.read_text(encoding="utf-8") == generated.text

    @pytest.mark.parametrize(("mutate", "reason"), [
        (lambda root: (root / "_internal" / "build-info.json").unlink(), "build_info_missing"),
        (lambda root: (root / "sbom.cdx.json").unlink(), "sbom_missing"),
        (lambda root: (root / "extra-artifact.bin").unlink(), "artifact_missing"),
        (lambda root: (root / "_internal" / "build-info.json").write_text(json.dumps({**_BUILD_INFO, "version": "0.2.0-rc1"}), encoding="utf-8"), "version_invalid"),
    ])
    def test_bad_inputs_fail_closed(self, mod, candidate, tmp_path, mutate, reason):
        mutate(candidate)
        with pytest.raises(mod.ManifestError, match=reason):
            mod.generate(candidate_root=candidate, out_dir=tmp_path / "out", artifact_names=list(_ARTIFACTS))
        assert not (tmp_path / "out" / "rc-manifest.json").exists()


class TestValidation:
    @pytest.mark.parametrize(("mutate", "reason"), [
        *[(lambda m, key=key: {**m, key: "whatever"}, reason) for key, reason in _REJECTED_FIELDS],
        *[(lambda m, name=name: {**m, "artifacts": [{**m["artifacts"][0], "name": name}, *m["artifacts"][1:]]},
            "absolute_path|schema_invalid")
         for name in (r"C:\build\dist\setup.exe", r"\\machine\share\setup.exe",
                      "/home/runner/work/dist/setup.exe", "../escape/setup.exe")],
        (lambda m: {**m, "unexpected": 1}, "schema_invalid"),
        (lambda m: {key: value for key, value in m.items() if key != "tools"}, "schema_invalid"),
    ])
    def test_validate_rejects_tainted_manifests(self, mod, generated, mutate, reason):
        with pytest.raises(mod.ManifestError, match=reason):
            mod.validate_manifest(mutate(dict(generated.manifest)))


class TestVerification:
    @pytest.mark.parametrize(("target", "payload"), [
        ("yasb-limitora-0.2.0-setup.exe", b"tampered"), ("extra-artifact.bin", b"tampered"),
        ("sbom.cdx.json", b"{}"), ("_internal/build-info.json", b"{}")])
    def test_verify_binds_bytes_then_detects_tampering(self, generated, target, payload):
        assert generated.mod.verify_manifest(generated.manifest_path, generated.candidate)["schema"] == _SCHEMA
        (generated.candidate / target).write_bytes(payload)
        with pytest.raises(generated.mod.ManifestError, match="digest_mismatch"):
            generated.mod.verify_manifest(generated.manifest_path, generated.candidate)

    def test_verify_rejects_injected_acceptance_field(self, generated):
        generated.manifest_path.write_text(json.dumps({**generated.manifest, "acceptance_run_id": "42"}), encoding="utf-8")
        with pytest.raises(generated.mod.ManifestError, match="forbidden_field"):
            generated.mod.verify_manifest(generated.manifest_path, generated.candidate)


class TestCli:
    def test_main_generate_verify_and_exit_codes(self, mod, candidate, tmp_path):
        out = tmp_path / "out"
        assert mod.main([str(candidate), str(out), *_ARTIFACTS]) == 0
        assert (out / "rc-manifest.json").is_file() and (out / "SHA256SUMS.txt").is_file()
        assert mod.main(["--verify", str(out / "rc-manifest.json"), str(candidate)]) == 0
        (candidate / "extra-artifact.bin").write_bytes(b"tampered")
        assert mod.main(["--verify", str(out / "rc-manifest.json"), str(candidate)]) == 1
        assert mod.main([str(candidate)]) == 2 and mod.main([str(candidate), str(tmp_path / "out2")]) == 2
        assert mod.main([str(tmp_path / "absent"), str(tmp_path / "out3"), "x.exe"]) == 2
