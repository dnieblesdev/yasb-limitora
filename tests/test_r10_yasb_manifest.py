from __future__ import annotations

import copy

import pytest

from tests.r10_yasb_manifest import (
    APPROVED_SOURCES,
    MANIFEST_SHA256,
    PACKAGE_NAMES,
    _canonical_digest,
    canonical_manifest_bytes,
    load_manifest,
    validate_manifest,
)


def test_manifest_accepts_the_approved_identity_and_complete_closure():
    manifest = load_manifest()
    validate_manifest(manifest)
    assert load_manifest() == manifest
    assert canonical_manifest_bytes(manifest) == __import__("pathlib").Path(__file__).with_name("r10_yasb_lock_manifest.json").read_bytes()
    assert manifest["manifest_sha256"] == MANIFEST_SHA256
    assert len(manifest["sources"]) == 3
    assert len(manifest["artifacts"]) == 57
    assert {item["name"] for item in manifest["artifacts"]} == PACKAGE_NAMES
    assert {item["tag"] for item in manifest["artifacts"]} <= set(manifest["wheel_tags"])


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("sources", 0, "commit"), "0123456789abcdef0123456789abcdef01234567"),
        (("sources", 0, "repository"), "https://github.com/other/yasb"),
        (("sources", 0, "archive_url"), "https://codeload.github.com/other/yasb/tar.gz/0123456789abcdef0123456789abcdef01234567"),
        (("sources", 0, "archive_sha256"), "0" * 64),
        (("sources", 0, "module_sha256"), "1" * 64),
        (("artifacts", 0, "version"), "9.9.9"),
        (("artifacts", 0, "filename"), "annotated_types-9.9.9-py3-none-any.whl"),
        (("artifacts", 0, "url"), "https://files.pythonhosted.org/packages/00/00/other.whl"),
        (("artifacts", 0, "sha256"), "2" * 64),
        (("artifacts", 0, "tag"), "py2.py3-none-any"),
        (("artifacts", 0, "metadata_sha256"), "3" * 64),
    ),
)
def test_manifest_rejects_syntactically_valid_substitutions(path, value):
    manifest = copy.deepcopy(load_manifest())
    target = manifest
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_manifest_rejects_substitution_even_when_attacker_recomputes_embedded_digest():
    manifest = copy.deepcopy(load_manifest())
    manifest["artifacts"][0]["sha256"] = "4" * 64
    manifest["manifest_sha256"] = _canonical_digest(manifest)
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_manifest_rejects_duplicate_source_entries():
    manifest = copy.deepcopy(load_manifest())
    manifest["sources"].append(copy.deepcopy(manifest["sources"][0]))
    with pytest.raises(ValueError):
        validate_manifest(manifest)


@pytest.mark.parametrize("operation", ("missing", "extra"))
def test_manifest_rejects_missing_or_extra_packages(operation):
    manifest = copy.deepcopy(load_manifest())
    if operation == "missing":
        manifest["artifacts"].pop()
    else:
        extra = copy.deepcopy(manifest["artifacts"][0])
        extra["name"] = "unapproved-package"
        manifest["artifacts"].append(extra)
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_manifest_rejects_dependency_metadata_closure_mutations():
    manifest = copy.deepcopy(load_manifest())
    manifest["artifacts"][1]["requires"].append("unapproved-package")
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_manifest_records_source_dependency_edges_without_runtime_actions():
    manifest = load_manifest()
    assert set(manifest["sources"][0]["requires"]) >= {"pyvda", "qt-css-engine", "pyqt6"}
    assert set(manifest["sources"][1]["requires"]) == {"pywin32", "comtypes"}
    assert set(manifest["sources"][2]["requires"]) == {"tinycss2"}


@pytest.mark.parametrize("variant", ("top-level-duplicate", "nested-duplicate"))
def test_manifest_rejects_duplicate_json_keys_at_every_object_level(tmp_path, variant):
    raw = canonical_manifest_bytes(load_manifest())
    if variant == "top-level-duplicate":
        raw = raw.replace(b'  "schema": "r10-yasb-lock-manifest/v1",', b'  "schema": "r10-yasb-lock-manifest/v1","schema": "r10-yasb-lock-manifest/v1",', 1)
    else:
        raw = raw.replace(b'"name":"annotated-types","version":"0.8.0"', b'"name":"annotated-types","version":"0.8.0","version":"0.8.0"', 1)
    path = tmp_path / "duplicate.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(path)


@pytest.mark.parametrize("variant", ("leading", "trailing", "indentation"))
def test_manifest_rejects_noncanonical_whitespace(tmp_path, variant):
    raw = canonical_manifest_bytes(load_manifest())
    if variant == "leading":
        raw = b" " + raw
    elif variant == "trailing":
        raw += b"\n"
    else:
        raw = raw.replace(b'  "schema"', b'    "schema"', 1)
    path = tmp_path / "noncanonical.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="canonical"):
        load_manifest(path)
