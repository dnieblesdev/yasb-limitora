"""Generate and verify immutable release-manifest/v1 identity records (S03).

Usage:
  python scripts/make_release_manifest.py CANDIDATE_ROOT OUT_DIR ARTIFACT...
  python scripts/make_release_manifest.py --verify MANIFEST_JSON CANDIDATE_ROOT

Build-time identity/integrity metadata only: no gate, approval, evidence, custody,
acceptance, or post-publication field; no absolute paths or secret-bearing records;
never a public -rc identity. Writes rc-manifest.json and coreutils-style SHA256SUMS
from sbom.cdx.json and _internal/build-info.json under CANDIDATE_ROOT; existing
outputs are never overwritten. Exit codes: 0 ok; 1 validation/digest mismatch;
2 usage or missing/invalid input.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

SCHEMA = "gentle-ai.yasb-limitora.release-manifest/v1"
_SBOM_NAME, _BUILD_INFO_NAME = "sbom.cdx.json", "_internal/build-info.json"
_TOOL_KEYS = ("python", "pyinstaller", "limitora")
_ROOT_KEYS = {"schema", "version", "source_commit", "source_date_epoch", "tools", "artifacts", "sbom", "build_info"}
_FORBIDDEN_KEY_PARTS = ("gate", "approval", "approve", "evidence", "custody", "acceptance",
                        "status", "publish", "publication", "run_id", "verdict", "review")
_SECRET_KEY_PARTS = ("token", "secret", "password", "credential", "api_key", "apikey", "session", "cookie")
_FINAL_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
_COMMIT_RE = re.compile(r"[0-9a-f]{7,64}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]|^\\\\|^/")


class ManifestError(RuntimeError):
    """Bounded, sanitized manifest failure with a machine-readable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code, self.detail = reason_code, detail


def _require(ok: bool, code: str, detail: str = "") -> None:
    if not ok:
        raise ManifestError(code, detail)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan(node: object, path: str = "") -> None:
    """Recursively reject forbidden-field keys, secret-bearing keys, and absolute paths."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            name = str(key).lower()
            joined = f"{path}.{name}" if path else name
            if any(part in name for part in _SECRET_KEY_PARTS):
                raise ManifestError("secret_bearing", joined)
            if any(part in name for part in _FORBIDDEN_KEY_PARTS):
                raise ManifestError("forbidden_field", joined)
            _scan(value, joined)
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
        for index, item in enumerate(node):
            _scan(item, f"{path}[{index}]")
    elif isinstance(node, str) and (_ABSOLUTE_RE.search(node) or ":\\" in node or "\\\\" in node):
        raise ManifestError("absolute_path", path)


def _relative_name(name: str) -> bool:
    return bool(name) and not _ABSOLUTE_RE.search(name) and ".." not in Path(name).parts


def validate_manifest(manifest: object) -> dict:
    _scan(manifest)
    if not isinstance(manifest, Mapping) or set(manifest) != _ROOT_KEYS or manifest["schema"] != SCHEMA:
        raise ManifestError("schema_invalid", "root key set or schema constant mismatch")
    version, commit = manifest["version"], manifest["source_commit"]
    epoch, tools, artifacts = manifest["source_date_epoch"], manifest["tools"], manifest["artifacts"]
    _require(isinstance(version, str) and bool(_FINAL_VERSION_RE.fullmatch(version)),
             "version_invalid", "final numeric version required; no -rc identity")
    _require(isinstance(commit, str) and bool(_COMMIT_RE.fullmatch(commit)), "schema_invalid", "source_commit")
    _require(isinstance(epoch, str) and epoch.isdigit(), "schema_invalid", "source_date_epoch")
    _require(isinstance(tools, Mapping) and set(tools) == set(_TOOL_KEYS)
             and all(isinstance(v, str) and v for v in tools.values()), "schema_invalid", "tools")
    _require(isinstance(artifacts, Sequence) and bool(artifacts), "schema_invalid", "artifacts must be a non-empty list")
    seen: set[str] = set()
    for entry in artifacts:
        _require(isinstance(entry, Mapping) and set(entry) == {"name", "size", "sha256"}, "schema_invalid", "artifact entry keys")
        name, size, digest = entry["name"], entry["size"], entry["sha256"]
        _require(isinstance(name, str) and _relative_name(name) and name not in seen, "schema_invalid", "artifact name")
        seen.add(name)
        _require(isinstance(size, int) and not isinstance(size, bool) and size >= 0, "schema_invalid", f"artifact size for {name}")
        _require(isinstance(digest, str) and bool(_SHA256_RE.fullmatch(digest)), "schema_invalid", f"artifact sha256 for {name}")
    for bound, expected in ((manifest["sbom"], _SBOM_NAME), (manifest["build_info"], _BUILD_INFO_NAME)):
        _require(isinstance(bound, Mapping) and set(bound) == {"name", "sha256"} and bound["name"] == expected
                 and isinstance(bound["sha256"], str) and bool(_SHA256_RE.fullmatch(bound["sha256"])), "schema_invalid", expected)
    return dict(manifest)


def generate(*, candidate_root: Path, out_dir: Path, artifact_names: Sequence[str]) -> dict:
    build_info_path, sbom_path = candidate_root / _BUILD_INFO_NAME, candidate_root / _SBOM_NAME
    _require(build_info_path.is_file(), "build_info_missing", _BUILD_INFO_NAME)
    _require(sbom_path.is_file(), "sbom_missing", _SBOM_NAME)
    try:
        record = json.loads(build_info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError("build_info_invalid", type(error).__name__) from error
    _require(isinstance(record, Mapping) and all(isinstance(record.get(key), str) and record.get(key)
                 for key in ("version", "source_commit", "source_date_epoch", *_TOOL_KEYS)),
             "build_info_invalid", "required identity/tool fields")
    artifacts = []
    for name in artifact_names:
        _require(_relative_name(name), "absolute_path", "artifact name must be relative")
        path = candidate_root / name
        _require(path.is_file(), "artifact_missing", name)
        artifacts.append({"name": name, "size": path.stat().st_size, "sha256": sha256_file(path)})
    artifacts.sort(key=lambda entry: entry["name"])
    manifest = {"schema": SCHEMA, "version": record["version"],
                "source_commit": record["source_commit"],
                "source_date_epoch": record["source_date_epoch"],
                "tools": {key: record[key] for key in _TOOL_KEYS}, "artifacts": artifacts,
                "sbom": {"name": _SBOM_NAME, "sha256": sha256_file(sbom_path)},
                "build_info": {"name": _BUILD_INFO_NAME, "sha256": sha256_file(build_info_path)}}
    validate_manifest(manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path, sums_path = out_dir / "rc-manifest.json", out_dir / "SHA256SUMS.txt"
    if manifest_path.exists() or sums_path.exists():
        raise ManifestError("manifest_exists", "immutable records are never overwritten")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    entries = sorted([*artifacts, manifest["sbom"], manifest["build_info"]], key=lambda item: item["name"])
    sums_path.write_text("".join(f"{entry['sha256']}  {entry['name']}\n" for entry in entries), encoding="utf-8")
    return manifest


def verify_manifest(manifest_path: Path, candidate_root: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError("manifest_invalid", type(error).__name__) from error
    validate_manifest(manifest)
    for entry in [*manifest["artifacts"], manifest["sbom"], manifest["build_info"]]:
        path = candidate_root / entry["name"]
        _require(path.is_file(), "artifact_missing", entry["name"])
        actual = path.stat().st_size
        if entry.get("size", actual) != actual or sha256_file(path) != entry["sha256"]:
            raise ManifestError("digest_mismatch", entry["name"])
    return dict(manifest)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 3 and args[0] == "--verify":
            manifest = verify_manifest(Path(args[1]), Path(args[2]))
            print(f"make-release-manifest: verify ok version={manifest['version']} artifacts={len(manifest['artifacts'])}")
        elif len(args) >= 3:
            manifest = generate(candidate_root=Path(args[0]), out_dir=Path(args[1]), artifact_names=args[2:])
            print(f"make-release-manifest: ok version={manifest['version']} artifacts={len(manifest['artifacts'])} out={args[1]}")
        else:
            print("usage: make_release_manifest.py CANDIDATE_ROOT OUT_DIR ARTIFACT...\n"
                  "       make_release_manifest.py --verify MANIFEST_JSON CANDIDATE_ROOT", file=sys.stderr)
            return 2
        return 0
    except ManifestError as error:
        print(f"make-release-manifest: {error.reason_code}: {error.detail}", file=sys.stderr)
        return 2 if error.reason_code.endswith(("missing", "unavailable", "invalid")) else 1
    except OSError as error:
        print(f"make-release-manifest: io_error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
