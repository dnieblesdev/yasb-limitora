"""Immutable, metadata-only R10 dependency manifest validation."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from pathlib import Path

MANIFEST_PATH = Path(__file__).with_name("r10_yasb_lock_manifest.json")
MANIFEST_SHA256 = "2ff3fbcc941d13c18258d77c485ad304cc8d3204c8b781187a92a3dd25c79ef6"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
WHEEL_TAGS = frozenset(("cp314-cp314-win_amd64", "cp314-abi3-win_amd64", "cp39-abi3-win_amd64", "cp37-abi3-win_amd64", "py3-none-win_amd64", "py3-none-any", "py2.py3-none-any"))
PACKAGE_NAMES = frozenset("""annotated-types anyio certifi colorama comtypes distro github-copilot-sdk h11 holidays httpcore httpx humanize idna jiter openai pillow psutil pycaw pydantic pydantic-core pyqt6 pyqt6-qt6 pyqt6-sip python-dateutil python-dotenv pywin32 pyyaml qasync six sniffio tinycss2 tqdm typing-extensions typing-inspection tzdata watchdog webencodings winrt-runtime winrt-windows-applicationmodel winrt-windows-applicationmodel-core winrt-windows-applicationmodel-datatransfer winrt-windows-data-xml-dom winrt-windows-devices-wifi winrt-windows-foundation winrt-windows-foundation-collections winrt-windows-management-deployment winrt-windows-media winrt-windows-media-control winrt-windows-networking winrt-windows-networking-connectivity winrt-windows-security-credentials winrt-windows-storage winrt-windows-storage-streams winrt-windows-ui winrt-windows-ui-notifications winrt-windows-ui-notifications-management winrt-windows-ui-viewmanagement""".split())
APPROVED_SOURCES = {
    "yasb": {"repository": "https://github.com/amnweb/yasb", "tag": "v2.0.5", "commit": "ee8ea9e683f3a4c41a27476adaab4c799a856643", "archive_url": "https://codeload.github.com/amnweb/yasb/tar.gz/ee8ea9e683f3a4c41a27476adaab4c799a856643", "archive_sha256": "5c743e06ee1e216c27f9b499bd7b0216d2d0d6f674c4e5ef4b8b71635ce93d98", "module": "core/widgets/yasb/custom.py", "module_sha256": "02ae36af55e4b72d430eb7d64337df0b085f714e13c1a00580e7fecec3279355"},
    "pyvda": {"repository": "https://github.com/amnweb/pyvda", "commit": "5d549eb5f8427ec771af98ae7b2c7ee38b98da6a", "archive_url": "https://codeload.github.com/amnweb/pyvda/tar.gz/5d549eb5f8427ec771af98ae7b2c7ee38b98da6a", "archive_sha256": "585dbdc6715b1e6ba158a4ab06e73327676005e3871f4825c2bc54210293b75e"},
    "qt-css-engine": {"repository": "https://github.com/Video-Nomad/qt-css-engine", "commit": "2a178cf7c994c63cab46224554bedf21e9639541", "archive_url": "https://codeload.github.com/Video-Nomad/qt-css-engine/tar.gz/2a178cf7c994c63cab46224554bedf21e9639541", "archive_sha256": "bd9809413c1c7b238b4c840a3f6f8730672d2727c168d2e1c2935eaec54db0d9"},
}
DIRECT_REQUIREMENTS = ("pyqt6==6.10.2", "pydantic==2.13.4", "humanize==4.15.0", "pywin32==312", "pyyaml==6.0.3", "holidays==0.99", "watchdog==6.0.0", "pycaw==20251023", "pillow==12.2.0", "qasync==0.28.0", "github-copilot-sdk==1.0.2", "openai==2.43.0", "python-dotenv==1.2.2", "tzdata==2026.2", "tinycss2==1.5.1")
SOURCE_FIELDS = ("name", "repository", "tag", "commit", "archive_url", "archive_sha256", "module", "module_sha256", "requires")
DEPENDENCY_SOURCE_FIELDS = ("name", "repository", "commit", "archive_url", "archive_sha256", "requires")
ARTIFACT_FIELDS = ("name", "version", "filename", "url", "sha256", "tag", "requires_python", "metadata_sha256", "requires")


def _compact_object(value: dict, fields: tuple[str, ...]) -> str:
    return json.dumps({field: value[field] for field in fields}, ensure_ascii=False, separators=(",", ":"))


def canonical_manifest_bytes(manifest: dict) -> bytes:
    lines = ["{"]
    for field in ("schema", "manifest_sha256", "python", "platform", "wheel_tags", "direct_requirements"):
        lines.append(f"  {json.dumps(field)}: {json.dumps(manifest[field], ensure_ascii=False, separators=(',', ':'))},")
    lines.append('  "sources": [')
    for index, source in enumerate(manifest["sources"]):
        fields = SOURCE_FIELDS if source.get("name") == "yasb" else DEPENDENCY_SOURCE_FIELDS
        lines.append(f"    {_compact_object(source, fields)}{',' if index < len(manifest['sources']) - 1 else ''}")
    lines.append("  ],")
    lines.append('  "artifacts": [')
    for index, artifact in enumerate(manifest["artifacts"]):
        lines.append(f"    {_compact_object(artifact, ARTIFACT_FIELDS)}{',' if index < len(manifest['artifacts']) - 1 else ''}")
    lines.extend(["  ]", "}"])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("manifest JSON is invalid or contains duplicate keys") from error
    if raw != canonical_manifest_bytes(manifest):
        raise ValueError("manifest bytes are not canonical")
    return manifest


def _canonical_digest(manifest: dict) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _package_name(requirement: str) -> str:
    match = re.match(r"([A-Za-z0-9_.-]+)", requirement)
    if not match:
        raise ValueError("invalid dependency metadata")
    return match.group(1).lower().replace("_", "-").replace(".", "-")


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema") != "r10-yasb-lock-manifest/v1" or manifest.get("python") != "3.14" or manifest.get("platform") != "win_amd64":
        raise ValueError("invalid manifest target")
    if manifest.get("manifest_sha256") != MANIFEST_SHA256 or _canonical_digest(manifest) != MANIFEST_SHA256:
        raise ValueError("manifest identity mismatch")
    if set(manifest.get("wheel_tags", ())) != WHEEL_TAGS or tuple(manifest.get("direct_requirements", ())) != DIRECT_REQUIREMENTS:
        raise ValueError("manifest policy mismatch")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != len(APPROVED_SOURCES) or {item.get("name") for item in sources} != set(APPROVED_SOURCES):
        raise ValueError("source identity closure mismatch")
    for source in sources:
        approved = APPROVED_SOURCES[source["name"]]
        for field, value in approved.items():
            if source.get(field) != value:
                raise ValueError(f"approved source {source['name']} mismatch")
        if not COMMIT.fullmatch(source.get("commit", "")) or not SHA256.fullmatch(source.get("archive_sha256", "")):
            raise ValueError("invalid source identity hash")
    artifacts = manifest.get("artifacts")
    names = {item.get("name") for item in artifacts} if isinstance(artifacts, list) else set()
    if not isinstance(artifacts, list) or len(artifacts) != len(PACKAGE_NAMES) or names != PACKAGE_NAMES:
        raise ValueError("package dependency closure mismatch")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("tag") not in WHEEL_TAGS:
            raise ValueError("incompatible wheel metadata")
        filename = artifact.get("filename", "")
        parsed = urllib.parse.urlparse(artifact.get("url", ""))
        if not filename.endswith(".whl") or parsed.scheme != "https" or parsed.netloc != "files.pythonhosted.org" or Path(parsed.path).name != filename:
            raise ValueError("wheel URL/filename mismatch")
        if not SHA256.fullmatch(artifact.get("sha256", "")) or not SHA256.fullmatch(artifact.get("metadata_sha256", "")):
            raise ValueError("wheel hash metadata missing")
        if not isinstance(artifact.get("version"), str) or not isinstance(artifact.get("requires"), list) or any(item not in PACKAGE_NAMES for item in artifact["requires"]):
            raise ValueError("wheel dependency metadata mismatch")
    for source in sources:
        requirements = source.get("requires")
        if not isinstance(requirements, list) or any(_package_name(item) not in PACKAGE_NAMES and item not in APPROVED_SOURCES for item in requirements):
            raise ValueError("source dependency closure mismatch")


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["verify-manifest"]:
        raise SystemExit("usage: r10_yasb_manifest.py verify-manifest")
    try:
        validate_manifest(load_manifest())
    except Exception as error:
        raise SystemExit(f"R10 manifest verification failed: {type(error).__name__}") from None
