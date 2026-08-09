"""Fail-closed acquisition checks for the isolated R10 YASB admission lane."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

LOCK_PATH = Path(__file__).with_name("r10_yasb_lock.json")
RUNTIME_DEPENDENCIES = {
    "pytest==8.4.1",
    "PyQt6==6.10.2",
    "pydantic==2.13.4",
    "pywin32==312",
    "PyYAML==6.0.3",
    "winrt.windows.foundation==3.2.1",
    "winrt.windows.foundation.collections==3.2.1",
    "winrt.windows.data.xml.dom==3.2.1",
    "winrt.windows.management.deployment==3.2.1",
    "winrt.windows.ui.notifications==3.2.1",
}
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UNSAFE_DIAGNOSTIC = re.compile(
    r"(?i)(traceback|file://|(?:[A-Z]:[\\/]|\\\\[^\r\n]*[\\/]|/(?:home|users|root|runner)/)"
    r"|password|api[_-]?key|cookie|token|secret|credential)"
)


def load_lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def validate_lock(lock: dict) -> None:
    if (
        lock.get("python") != "3.14"
        or set(lock.get("runtime_dependencies", ())) != RUNTIME_DEPENDENCIES
        or not isinstance(lock.get("sources"), list)
    ):
        raise ValueError("invalid Python or source lock")
    expected = {"yasb", "pyvda", "qt-css-engine"}
    sources = {item.get("name"): item for item in lock["sources"]}
    if set(sources) != expected:
        raise ValueError("unexpected source identities")
    for name, source in sources.items():
        commit = source.get("commit")
        if not COMMIT.fullmatch(commit or ""):
            raise ValueError(f"floating or invalid {name} commit")
        if not source.get("repository", "").startswith("https://github.com/"):
            raise ValueError(f"unexpected {name} repository")
        archive_url = source.get("archive_url", "")
        if not archive_url.endswith(f"/tar.gz/{commit}"):
            raise ValueError(f"unexpected {name} archive identity")
        if not source.get("filename") or not SHA256.fullmatch(source.get("sha256", "")):
            raise ValueError(f"missing {name} artifact hash")
    yasb = sources["yasb"]
    if yasb.get("tag") != "v2.0.5" or yasb["repository"] != "https://github.com/amnweb/yasb":
        raise ValueError("unexpected YASB identity")
    if sources["pyvda"]["repository"] != "https://github.com/amnweb/pyvda":
        raise ValueError("unexpected pyvda identity")
    if sources["qt-css-engine"]["repository"] != "https://github.com/Video-Nomad/qt-css-engine":
        raise ValueError("unexpected qt-css-engine identity")
    if (
        yasb.get("module") != "core/widgets/yasb/custom.py"
        or not SHA256.fullmatch(yasb.get("module_sha256", ""))
    ):
        raise ValueError("missing YASB module identity")


def verify_archives(directory: Path) -> None:
    lock = load_lock()
    validate_lock(lock)
    for source in lock["sources"]:
        path = directory / source["filename"]
        if not path.is_file():
            raise ValueError(f"missing acquired artifact: {source['name']}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"{source['name']} artifact hash mismatch")


def materialize_yasb(archive: Path, destination: Path) -> None:
    lock = load_lock()
    validate_lock(lock)
    yasb = next(item for item in lock["sources"] if item["name"] == "yasb")
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != yasb["sha256"]:
        raise ValueError("YASB archive identity mismatch")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("YASB source destination is not empty")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as source_archive:
        for member in source_archive.getmembers():
            target = (destination / member.name).resolve()
            if destination.resolve() not in target.parents or member.issym() or member.islnk():
                raise ValueError("unsafe YASB source archive")
        source_archive.extractall(destination, filter="data")
    candidates = list(destination.glob("*/src/core/widgets/yasb/custom.py"))
    if len(candidates) != 1 or verify_yasb_module(str(candidates[0])).parent.name != "yasb":
        raise ValueError("YASB source identity unavailable")


def verify_yasb_module(path: str) -> Path:
    source = Path(path).resolve()
    expected = next(item for item in load_lock()["sources"] if item["name"] == "yasb")
    if not source.as_posix().endswith(expected["module"]):
        raise ValueError("unexpected YASB module path")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected["module_sha256"]:
        raise ValueError("YASB module hash mismatch")
    return source


def _junit_counts(report: str) -> dict[str, int]:
    root = ET.fromstring(report)
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("missing JUnit suites")
    fields = ("tests", "skipped", "failures", "errors")
    return {field: sum(int(suite.attrib.get(field, "0")) for suite in suites) for field in fields}


def _require_test(report: str, test_name: str) -> None:
    root = ET.fromstring(report)
    if not any(case.attrib.get("name") == test_name for case in root.iter("testcase")):
        raise ValueError("required admission test was not executed")


def write_safe_pytest_status(
    raw_path: Path, report_path: Path, exit_code: int, output_path: Path, required_test: str | None = None
) -> None:
    raw = raw_path.read_bytes()
    report = report_path.read_bytes()
    raw_text = raw.decode("utf-8", errors="replace")
    report_text = report.decode("utf-8", errors="replace")
    if UNSAFE_DIAGNOSTIC.search(raw_text) or UNSAFE_DIAGNOSTIC.search(report_text):
        raise ValueError("pytest diagnostics failed privacy scan")
    if required_test is not None:
        _require_test(report_text, required_test)
    status = {
        "schema": "r10-admission-status/v1",
        "pytest_exit": int(exit_code),
        **_junit_counts(report_text),
        "privacy": "passed",
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "junit_sha256": hashlib.sha256(report).hexdigest(),
    }
    output_path.write_text(json.dumps(status, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["verify-lock"]:
            validate_lock(load_lock())
        elif len(sys.argv) == 3 and sys.argv[1] == "verify-archives":
            verify_archives(Path(sys.argv[2]))
        elif len(sys.argv) == 4 and sys.argv[1] == "materialize-yasb":
            materialize_yasb(Path(sys.argv[2]), Path(sys.argv[3]))
        elif len(sys.argv) == 6 and sys.argv[1] == "summarize-pytest":
            write_safe_pytest_status(
                Path(sys.argv[2]),
                Path(sys.argv[3]),
                int(sys.argv[4]),
                Path(sys.argv[5]),
                "test_real_yasb_205_custom_widget_is_imported_constructed_and_observed",
            )
        else:
            raise ValueError("invalid verification command")
    except Exception as error:
        raise SystemExit(f"R10 admission verification failed: {type(error).__name__}") from None
