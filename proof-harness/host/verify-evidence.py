#!/usr/bin/env python3
"""Fail-closed host gate for extracted reusable VM proof evidence.

The gate verifies the guest watcher identity, the declared scenario/step coverage,
process input identity, and only claims state, dialog, or assistant evidence when
the scenario declares that evidence. A missing or incomplete evidence tree is a
failure; an empty tree is never reported as PASS.
"""
import argparse
import json
import pathlib
import re
import sys
from typing import Any

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_WATCHER_HASH = re.compile(r"watcher script sha256=([0-9a-fA-F]{64})", re.IGNORECASE)


def load(path: pathlib.Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def step_key(step: dict[str, Any]) -> tuple[str, str]:
    return (str(step.get("kind", "")), str(step.get("phase", "")))


def declared_expect_failure(scenario: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        step_key(step)
        for step in scenario.get("steps", [])
        if isinstance(step, dict) and isinstance(step.get("expectFailure"), bool) and step.get("expectFailure")
    }


def _phase_root(evidence_dir: pathlib.Path, name: str, phase: str) -> pathlib.Path:
    return evidence_dir / name / phase


def _validate_watcher_stamp(evidence_dir: pathlib.Path, failures: list[str], name: str) -> None:
    stamp_path = evidence_dir / "expected-watcher.sha256"
    log_path = evidence_dir / "watcher.log"
    if not stamp_path.is_file():
        failures.append(f"{name}: missing expected-watcher.sha256 stamp")
        return
    try:
        expected = stamp_path.read_text(encoding="utf-8").strip().lower()
    except OSError as exc:
        failures.append(f"{name}: cannot read watcher stamp ({exc})")
        return
    if not _SHA256.fullmatch(expected):
        failures.append(f"{name}: watcher stamp is not a SHA-256 digest")
        return
    if not log_path.is_file():
        failures.append(f"{name}: missing watcher.log for stamped watcher identity")
        return
    log = log_path.read_text(encoding="utf-8", errors="replace")
    matches = _WATCHER_HASH.findall(log)
    if not matches:
        failures.append(f"{name}: watcher.log has no running watcher SHA-256")
    elif any(value.lower() != expected for value in matches):
        failures.append(f"{name}: watcher.log watcher SHA-256 does not match the stamp")


def _validate_state_captures(
    evidence_dir: pathlib.Path,
    name: str,
    scenario: dict[str, Any],
    failures: list[str],
) -> None:
    for declared in scenario.get("steps", []):
        if not isinstance(declared, dict) or declared.get("kind") != "capture":
            continue
        phase = str(declared.get("phase", ""))
        capture_path = _phase_root(evidence_dir, name, phase) / "state-capture.json"
        if not capture_path.is_file():
            failures.append(f"{name}: missing state capture for declared capture/{phase}")
            continue
        try:
            capture = load(capture_path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{name}: invalid state capture for capture/{phase} ({exc})")
            continue
        if capture.get("scenario") != name or capture.get("phase") != phase:
            failures.append(f"{name}: state capture identity mismatch for capture/{phase}")
        if not str(capture.get("schema", "")).startswith("gentle-ai.yasb-limitora.s11b-guest-state/"):
            failures.append(f"{name}: state capture for capture/{phase} has an unsupported schema")
        trees = capture.get("trees")
        if not isinstance(trees, dict) or not isinstance(trees.get("app"), dict) or not isinstance(trees.get("state"), dict):
            failures.append(f"{name}: state capture for capture/{phase} has no meaningful app/state trees")
        elif any(not isinstance(tree.get("present"), bool) or not isinstance(tree.get("files"), list) for tree in (trees["app"], trees["state"])):
            failures.append(f"{name}: state capture for capture/{phase} has incomplete tree state")


def _validate_claims(
    evidence_dir: pathlib.Path,
    name: str,
    scenario: dict[str, Any],
    done_steps: list[dict[str, Any]],
    failures: list[str],
) -> None:
    log_path = evidence_dir / "watcher.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    claim_text = [log]
    for path in evidence_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".log", ".txt", ".json"} and path.name not in {"scenario.json", "done.json"}:
            claim_text.append(path.read_text(encoding="utf-8", errors="replace"))
    claim_evidence = "\n".join(claim_text)

    answers = scenario.get("dialogAnswers") or []
    if answers:
        answered = [step for step in done_steps if isinstance(step.get("dialogAnswered"), bool) and step.get("dialogAnswered")]
        if not answered:
            failures.append(f"{name}: declared dialog answers have no answered-dialog evidence")
        answer_lines = log.lower().count("answering declared dialog")
        if answer_lines < len(answers):
            failures.append(f"{name}: declared dialog answers exceed watcher dialog evidence")
    elif any(isinstance(step.get("dialogAnswered"), bool) and step.get("dialogAnswered") for step in done_steps):
        failures.append(f"{name}: evidence claims a dialog was answered without a declared dialog")

    claims = scenario.get("claims")
    assist = scenario.get("assist")
    if assist is None and isinstance(claims, dict):
        assist = claims.get("assist")
    if assist:
        marker = assist.get("marker") if isinstance(assist, dict) else assist if isinstance(assist, str) else "assist"
        if not isinstance(marker, str) or not marker.strip() or marker.casefold() not in claim_evidence.casefold():
            failures.append(f"{name}: declared assist claim has no matching evidence marker")


def _validate_input_and_steps(
    evidence_dir: pathlib.Path,
    name: str,
    scenario: dict[str, Any],
    done: dict[str, Any],
    expected_executable: str,
    failures: list[str],
) -> None:
    declared = scenario.get("steps")
    observed = done.get("steps")
    if not isinstance(declared, list) or not declared:
        failures.append(f"{name}: scenario declares no steps")
        return
    if not isinstance(observed, list):
        failures.append(f"{name}: done.json has no step coverage")
        return

    declared_keys = [step_key(step) for step in declared if isinstance(step, dict)]
    observed_keys = [step_key(step) for step in observed if isinstance(step, dict)]
    if len(set(declared_keys)) != len(declared_keys):
        failures.append(f"{name}: scenario has duplicate declared steps")
    if observed_keys != declared_keys:
        failures.append(f"{name}: done.json step coverage does not match declared scenario order")

    expected_failures = declared_expect_failure(scenario)
    process_keys = {
        step_key(step)
        for step in declared
        if isinstance(step, dict) and step.get("kind") in {"setup", "uninstall"}
    }
    for step in observed:
        if not isinstance(step, dict):
            failures.append(f"{name}: done.json contains a non-object step")
            continue
        key = step_key(step)
        code = step.get("exitCode")
        if code is None and key in process_keys:
            failures.append(f"{name}: process step {key[0]}/{key[1]} has no exit code")
        elif code is not None:
            try:
                code = int(code)
            except (TypeError, ValueError):
                failures.append(f"{name}: step {key[0]}/{key[1]} has an invalid exit code")
                continue
            if code != 0 and key not in expected_failures:
                failures.append(f"{name}: step {key[0]}/{key[1]} exited {code} without expectFailure")

        if key[0] in {"setup", "uninstall"} and "dialogAnswered" in step and not isinstance(step["dialogAnswered"], bool):
            failures.append(f"{name}: step {key[0]}/{key[1]} has a non-boolean dialogAnswered claim")

    records: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record_path in sorted(evidence_dir.rglob("run-record.json")):
        try:
            record = load(record_path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{name}: invalid run record {record_path.name} ({exc})")
            continue
        key = step_key(record)
        records.setdefault(key, []).append(record)
        if key not in process_keys:
            failures.append(f"{name}: run record {key[0]}/{key[1]} is not a declared process step")

        executable = record.get("executable")
        if not isinstance(executable, dict):
            failures.append(f"{name}: run record {key[0]}/{key[1]} has no executable identity")
            continue
        record_name = pathlib.PureWindowsPath(str(executable.get("path", ""))).name.casefold()
        declared_step = next((step for step in declared if isinstance(step, dict) and step_key(step) == key), None)
        if declared_step and key[0] == "setup":
            if record_name != str(declared_step.get("executable", "")).casefold():
                failures.append(f"{name}: setup input identity does not match declared executable for {key[1]}")
            if str(executable.get("sha256", "")).lower() != expected_executable:
                failures.append(f"{name}: {record_path.parent.name} ran executable hash {executable.get('sha256')} instead of expected {expected_executable}")
        code = record.get("exitCode")
        if code is not None:
            try:
                record_code = int(code)
            except (TypeError, ValueError):
                failures.append(f"{name}: {record_path.parent.name} has an invalid exit code")
                continue
            if record_code != 0 and key not in expected_failures:
                failures.append(f"{name}: {record_path.parent.name} exit {code} without expectFailure")

    for key in process_keys:
        if key not in records:
            failures.append(f"{name}: missing run record for declared {key[0]}/{key[1]}")

    identity = scenario.get("inputIdentity")
    if identity is None and isinstance(scenario.get("input"), dict) and "sha256" in scenario["input"]:
        identity = scenario["input"]
    if identity:
        identity_evidence = done.get("inputIdentity")
        if identity_evidence is None:
            for candidate in (evidence_dir / "input-identity.json", evidence_dir / "input.json"):
                if candidate.is_file():
                    try:
                        identity_evidence = load(candidate)
                    except (OSError, TypeError, ValueError, json.JSONDecodeError):
                        identity_evidence = None
                    break
        if not isinstance(identity_evidence, dict):
            failures.append(f"{name}: declared input identity has no evidence")
        else:
            for field in ("path", "size", "sha256"):
                if field in identity and identity_evidence.get(field) != identity[field]:
                    failures.append(f"{name}: input identity field {field} does not match declaration")


def _evidence_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    direct = root / "done.json"
    if direct.is_file():
        return [root]
    return sorted(path.parent for path in root.glob("*/done.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence_root")
    ap.add_argument("--expected-executable", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.evidence_root)
    expected = args.expected_executable.lower()
    failures: list[str] = []
    if not _SHA256.fullmatch(expected):
        failures.append("expected executable must be a SHA-256 digest")
    evidence_dirs = _evidence_dirs(root) if root.is_dir() else []
    if not evidence_dirs:
        failures.append("no done.json evidence was found; PASS is unsupported")

    scenarios = 0
    runs = 0
    for evidence_dir in evidence_dirs:
        try:
            done = load(evidence_dir / "done.json")
            scenario_path = evidence_dir / "scenario.json"
            if not scenario_path.is_file() and root != evidence_dir:
                scenario_path = root / "scenario.json"
            scenario = load(scenario_path)
            name = str(done.get("scenario", ""))
            scenarios += 1
            if not name or scenario.get("scenario") != name:
                failures.append(f"{name or '<missing>'}: scenario identity mismatch")
            if done.get("result") != "success":
                failures.append(f"{name}: done.json result={done.get('result')!r} ({done.get('failureReason')})")
            if not isinstance(done.get("shutdownSkipped"), bool) or done.get("shutdownSkipped"):
                failures.append(f"{name}: guest did not shut down cleanly (shutdownSkipped={done.get('shutdownSkipped')})")
            _validate_watcher_stamp(evidence_dir, failures, name)
            _validate_input_and_steps(evidence_dir, name, scenario, done, expected, failures)
            raw_done_steps = done.get("steps")
            done_steps = [step for step in raw_done_steps if isinstance(step, dict)] if isinstance(raw_done_steps, list) else []
            _validate_state_captures(evidence_dir, name, scenario, failures)
            _validate_claims(evidence_dir, name, scenario, done_steps, failures)
            runs += sum(1 for _ in evidence_dir.rglob("run-record.json"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{evidence_dir.name}: malformed evidence ({exc})")

    print(f"scenarios={scenarios} run_records={runs} expected_executable={expected}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"VERDICT: FAIL ({len(failures)} violation(s))")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
