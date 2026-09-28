#!/usr/bin/env python3
"""Fail-closed offline verifier for the C5 silent-uninstall proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

SCENARIO_NAME = "silent-uninstall-with-state-root"
SETUP_NAME = "yasb-limitora-0.2.0-setup.exe"
SETUP_SIZE = 11_054_574
SETUP_SHA256 = "1d58f3618f5b22ddccacc7be2dcf8e3a1e9a90dba57dffe431d8ca8ae6df3394"
LEGACY_SCENARIO_SHA256 = "8aca8127167fc5ec0ec143c563e1b14c1d77bf763c8203d2095bd1c515a37c93"
SCENARIO_SHA256 = "1bea8063e7797ece35d01f70e5c3648e420942eae48fba5f02b3067c033e4870"
FIXTURE_SHA256 = "e16c422f5a2593dd4bfcc1cf5979cfad382769422953ff10202986be8f0a1795"
SILENT_ARGUMENTS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FIXTURE_FILES = {
    "config.json": (32, FIXTURE_SHA256),
    "quota-v2-cache.json": (32, FIXTURE_SHA256),
}


def load(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable or malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_bool(value: object, label: str, failures: list[str]) -> bool:
    if type(value) is not bool:
        failures.append(f"{label} must be a boolean")
        return False
    return value


def exact_exit(value: object, label: str, failures: list[str]) -> int | None:
    if type(value) is not int:
        failures.append(f"{label} must be an integer exit code, not a boolean or string")
        return None
    return value


def load_or_record(path: pathlib.Path, label: str, failures: list[str]) -> dict[str, Any] | None:
    try:
        return load(path, label)
    except ValueError as exc:
        failures.append(str(exc))
        return None


def require_equal(actual: object, expected: object, label: str, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def state_files(capture: dict[str, Any], label: str, failures: list[str]) -> dict[str, tuple[int, str]]:
    trees = capture.get("trees")
    if not isinstance(trees, dict):
        failures.append(f"{label} has no trees")
        return {}
    state = trees.get("state")
    if not isinstance(state, dict):
        failures.append(f"{label} has no state tree")
        return {}
    if not exact_bool(state.get("present"), f"{label} state.present", failures):
        failures.append(f"{label} state root is absent; state deletion is not claimed or accepted")
    raw_files = state.get("files")
    if not isinstance(raw_files, list):
        failures.append(f"{label} state.files is missing")
        return {}
    result: dict[str, tuple[int, str]] = {}
    for entry in raw_files:
        if not isinstance(entry, dict):
            failures.append(f"{label} contains a malformed state-file record")
            continue
        path = entry.get("path")
        size = entry.get("size")
        digest = entry.get("sha256")
        if not isinstance(path, str) or not path or pathlib.PurePosixPath(path).is_absolute() or ".." in pathlib.PurePosixPath(path).parts:
            failures.append(f"{label} contains an unsafe state-file path")
            continue
        if type(size) is not int or type(digest) is not str:
            failures.append(f"{label} contains a malformed state-file identity")
            continue
        result[path.replace("\\", "/")] = (size, digest.lower())
    return result


def verify_state_captures(evidence: pathlib.Path, failures: list[str]) -> None:
    root = evidence / SCENARIO_NAME
    captures: dict[str, dict[str, Any]] = {}
    for phase in ("before", "after"):
        path = root / phase / "state-capture.json"
        if not path.is_file():
            failures.append(f"missing {phase} state capture")
            continue
        capture = load_or_record(path, f"{phase} state capture", failures)
        if capture is None:
            continue
        require_equal(capture.get("scenario"), SCENARIO_NAME, f"{phase} capture scenario", failures)
        require_equal(capture.get("phase"), phase, f"{phase} capture phase", failures)
        if not str(capture.get("schema", "")).startswith("gentle-ai.yasb-limitora.s11b-guest-state/"):
            failures.append(f"{phase} capture has an unsupported schema")
        captures[phase] = capture

    if set(captures) != {"before", "after"}:
        return
    before, after = captures["before"], captures["after"]
    before_trees = before.get("trees")
    after_trees = after.get("trees")
    if not isinstance(before_trees, dict) or not isinstance(after_trees, dict):
        failures.append("before/after captures have no trees")
        return
    before_app = before_trees.get("app")
    after_app = after_trees.get("app")
    if not isinstance(before_app, dict) or not isinstance(after_app, dict):
        failures.append("before/after captures have no application trees")
    else:
        if not exact_bool(before_app.get("present"), "before application.present", failures):
            failures.append("application was not present before install/uninstall")
        if exact_bool(after_app.get("present"), "after application.present", failures):
            failures.append("application remains after uninstall")

    before_key = before.get("uninstallKey")
    after_key = after.get("uninstallKey")
    if not isinstance(before_key, dict) or not isinstance(after_key, dict):
        failures.append("before/after captures have no uninstall-key records")
    else:
        if not exact_bool(before_key.get("present"), "before uninstall-key.present", failures):
            failures.append("uninstall registration was not present before uninstall")
        if exact_bool(after_key.get("present"), "after uninstall-key.present", failures):
            failures.append("uninstall key remains after uninstall")

    before_files = state_files(before, "before capture", failures)
    after_files = state_files(after, "after capture", failures)
    expected = dict(FIXTURE_FILES)
    if before_files != expected:
        failures.append(f"before state files do not match the two declared fixture files: {before_files!r}")
    if after_files != expected:
        failures.append(f"after state files do not match the two declared fixture files: {after_files!r}")
    if before_files != after_files:
        failures.append("declared state fixture files did not survive byte-identically")


def verify_setup_binding(input_root: pathlib.Path | None, steps: dict[str, Any], result: dict[str, Any], failures: list[str]) -> None:
    setup = steps.get("setup")
    if not isinstance(setup, dict):
        failures.append("scenario has no setup binding")
        return
    require_equal(setup.get("name"), SETUP_NAME, "scenario setup name", failures)
    require_equal(setup.get("size"), SETUP_SIZE, "scenario setup size", failures)
    require_equal(setup.get("sha256"), SETUP_SHA256, "scenario setup SHA-256", failures)
    result_setup = result.get("setup")
    if not isinstance(result_setup, dict):
        failures.append("c5-result has no setup identity")
    else:
        require_equal(result_setup.get("name"), SETUP_NAME, "result setup name", failures)
        require_equal(result_setup.get("size"), SETUP_SIZE, "result setup size", failures)
        require_equal(result_setup.get("sha256"), SETUP_SHA256, "result setup SHA-256", failures)
    if input_root is not None:
        setup_path = input_root / SETUP_NAME
        if not setup_path.is_file():
            failures.append("staged setup executable is missing")
        else:
            if setup_path.stat().st_size != SETUP_SIZE:
                failures.append("staged setup executable size mismatch")
            if sha256(setup_path) != SETUP_SHA256:
                failures.append("staged setup executable SHA-256 mismatch")


def verify_process_records(evidence: pathlib.Path, failures: list[str]) -> None:
    root = evidence / SCENARIO_NAME
    records: dict[str, dict[str, Any]] = {}
    for phase in ("install", "uninstall"):
        path = root / phase / "run-record.json"
        if not path.is_file():
            failures.append(f"missing {phase} run record")
            continue
        record = load_or_record(path, f"{phase} run record", failures)
        if record is None:
            continue
        records[phase] = record
        require_equal(record.get("schema"), "gentle-ai.yasb-limitora.c5-run/v1", f"{phase} run schema", failures)
        require_equal(record.get("kind"), phase, f"{phase} run kind", failures)
        require_equal(record.get("phase"), phase, f"{phase} run phase", failures)
        code = exact_exit(record.get("exitCode"), f"{phase} run exitCode", failures)
        if code is not None and code != 0:
            failures.append(f"{phase} returned unexpected exit code {code}")
        if record.get("arguments") != SILENT_ARGUMENTS:
            failures.append(f"{phase} did not use the required silent arguments")
        if "dialogObserved" in record:
            failures.append(f"{phase} must not claim dialog observation")
        if "dialogAnswerAttempted" not in record:
            failures.append(f"{phase} is missing dialogAnswerAttempted")
        elif type(record.get("dialogAnswerAttempted")) is not bool:
            failures.append(f"{phase} dialogAnswerAttempted must be a boolean")
        elif record.get("dialogAnswerAttempted"):
            failures.append(f"{phase} attempted a dialog answer unexpectedly")
        executable = record.get("executable")
        if not isinstance(executable, dict):
            failures.append(f"{phase} has no executable identity")
        else:
            if not isinstance(executable.get("path"), str) or not executable["path"]:
                failures.append(f"{phase} executable identity has no stable path")
            if not exact_bool(executable.get("present"), f"{phase} executable.present", failures):
                failures.append(f"{phase} executable identity was not captured before start")
            if type(executable.get("size")) is not int or executable["size"] < 0:
                failures.append(f"{phase} executable identity has an invalid size")
            if not isinstance(executable.get("sha256"), str) or SHA256_RE.fullmatch(executable["sha256"].lower()) is None:
                failures.append(f"{phase} executable identity has an invalid SHA-256")
            if not isinstance(executable.get("name"), str) or not executable["name"]:
                failures.append(f"{phase} has a malformed executable identity")
    if "install" in records:
        require_equal(records["install"].get("executable", {}).get("name"), SETUP_NAME, "install executable name", failures)
        require_equal(records["install"].get("executable", {}).get("size"), SETUP_SIZE, "install executable size", failures)
        require_equal(records["install"].get("executable", {}).get("sha256"), SETUP_SHA256, "install executable SHA-256", failures)


def verify_generic_records(evidence: pathlib.Path, failures: list[str]) -> None:
    done_path = evidence / "done.json"
    exit_path = evidence / "exit.json"
    if not done_path.is_file():
        failures.append("missing generic done.json run record")
        return
    if not exit_path.is_file():
        failures.append("missing generic exit.json run record")
        return
    done = load_or_record(done_path, "done.json", failures)
    exit_record = load_or_record(exit_path, "exit.json", failures)
    if done is None or exit_record is None:
        return
    require_equal(done.get("schema"), "gentle-ai.yasb-limitora.reusable-vm-done/v1", "done schema", failures)
    require_equal(exit_record.get("schema"), "gentle-ai.yasb-limitora.reusable-vm-exit/v1", "exit schema", failures)
    require_equal(done.get("scenario"), SCENARIO_NAME, "done scenario", failures)
    require_equal(exit_record.get("scenario"), SCENARIO_NAME, "exit scenario", failures)
    require_equal(done.get("result"), "success", "generic result", failures)
    if not exact_bool(exit_record.get("success"), "generic success", failures):
        failures.append("generic success is not true")
    done_code = exact_exit(done.get("runnerExitCode"), "done.runnerExitCode", failures)
    exit_code = exact_exit(exit_record.get("exitCode"), "exit.exitCode", failures)
    runner_code = exact_exit(exit_record.get("runnerExitCode"), "exit.runnerExitCode", failures)
    for label, code in (("done.runnerExitCode", done_code), ("exit.exitCode", exit_code), ("exit.runnerExitCode", runner_code)):
        if code is not None and code != 0:
            failures.append(f"{label} is not zero")
    if not exact_bool(done.get("inputUnchanged"), "done.inputUnchanged", failures):
        failures.append("generic input-integrity record does not prove unchanged input")
    input_digest = done.get("inputTreeSha256")
    if not isinstance(input_digest, str) or SHA256_RE.fullmatch(input_digest.lower()) is None:
        failures.append("generic input-integrity record has a malformed inputTreeSha256")
    if not exact_bool(done.get("shutdownRequested"), "done.shutdownRequested", failures) or not exact_bool(exit_record.get("shutdownRequested"), "exit.shutdownRequested", failures):
        failures.append("generic shutdown record does not request clean shutdown")


def verify_c5(archive_root: pathlib.Path) -> list[str]:
    failures: list[str] = []
    input_root = archive_root / "input"
    evidence_root = archive_root / "evidence"
    if not input_root.is_dir():
        failures.append("archive input directory is missing")
    if not evidence_root.is_dir():
        failures.append("archive evidence directory is missing")
    scenario_path = input_root / "scenario.json"
    try:
        scenario = load(scenario_path, "archive input scenario.json")
    except ValueError as exc:
        return failures + [str(exc)]
    try:
        steps = load(input_root / "c5-steps.json", "archive input c5-steps.json")
        result = load(evidence_root / "c5-result.json", "archive evidence c5-result.json")
    except ValueError as exc:
        return failures + [str(exc)]

    try:
        require_equal(sha256(scenario_path), SCENARIO_SHA256, "archive scenario SHA-256", failures)
    except OSError as exc:
        failures.append(f"archive scenario SHA-256 is unavailable: {exc}")
    for name, (expected_size, expected_sha256) in FIXTURE_FILES.items():
        fixture_path = input_root / "state-root" / name
        try:
            require_equal(fixture_path.stat().st_size, expected_size, f"archive fixture {name} size", failures)
            require_equal(sha256(fixture_path), expected_sha256, f"archive fixture {name} SHA-256", failures)
        except OSError as exc:
            failures.append(f"archive fixture {name} is missing or unreadable: {exc}")

    require_equal(scenario.get("schema"), "gentle-ai.yasb-limitora.reusable-vm-run/v1", "generic scenario schema", failures)
    require_equal(scenario.get("scenario"), SCENARIO_NAME, "generic scenario id", failures)
    if scenario.get("dialogAnswers") != []:
        failures.append("generic scenario dialogAnswers must be exactly []")
    require_equal(steps.get("schema"), "gentle-ai.yasb-limitora.c5-silent-uninstall/v1", "C5 step schema", failures)
    require_equal(steps.get("scenario"), SCENARIO_NAME, "C5 step scenario id", failures)
    require_equal(steps.get("legacyScenarioSha256"), LEGACY_SCENARIO_SHA256, "legacy scenario SHA-256", failures)
    if steps.get("dialogAnswers") != []:
        failures.append("C5 step dialogAnswers must be exactly []")
    if steps.get("silentArguments") != SILENT_ARGUMENTS:
        failures.append("C5 step silent argument declaration mismatch")
    if steps.get("fixtureFiles") != [
        {"path": "config.json", "size": 32, "sha256": FIXTURE_SHA256},
        {"path": "quota-v2-cache.json", "size": 32, "sha256": FIXTURE_SHA256},
    ]:
        failures.append("C5 step fixture declaration mismatch")
    require_equal(result.get("schema"), "gentle-ai.yasb-limitora.c5-result/v1", "result schema", failures)
    require_equal(result.get("scenario"), SCENARIO_NAME, "result scenario", failures)
    require_equal(result.get("legacyScenarioSha256"), LEGACY_SCENARIO_SHA256, "result legacy scenario SHA-256", failures)
    verify_setup_binding(input_root, steps, result, failures)
    if result.get("silentArguments") != SILENT_ARGUMENTS:
        failures.append("result silent argument declaration mismatch")
    if result.get("fixtureFiles") != [
        {"path": "config.json", "size": 32, "sha256": FIXTURE_SHA256},
        {"path": "quota-v2-cache.json", "size": 32, "sha256": FIXTURE_SHA256},
    ]:
        failures.append("result fixture declaration mismatch")
    for field in ("statePreserved", "applicationRemoved", "uninstallKeyRemoved", "dialogAnswerAttempted"):
        exact_bool(result.get(field), f"result.{field}", failures)
    if not result.get("statePreserved"):
        failures.append("result does not prove state preservation")
    if not result.get("applicationRemoved"):
        failures.append("result does not prove application removal")
    if not result.get("uninstallKeyRemoved"):
        failures.append("result does not prove uninstall-key removal")
    if result.get("dialogAnswerAttempted"):
        failures.append("result records an unexpected dialog-answer attempt")
    if "dialogObserved" in result:
        failures.append("result must not claim dialog observation")
    if result.get("stateDeleted"):
        failures.append("state deletion is not an accepted C5 claim")
    verify_state_captures(evidence_root, failures)
    verify_process_records(evidence_root, failures)
    verify_generic_records(evidence_root, failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_root", type=pathlib.Path)
    args = parser.parse_args()
    if not args.archive_root.is_dir():
        failures = ["archive root does not exist"]
    else:
        failures = verify_c5(args.archive_root)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"C5 VERDICT: FAIL ({len(failures)} violation(s))")
        return 1
    print(f"C5 VERDICT: PASS scenario={SCENARIO_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
