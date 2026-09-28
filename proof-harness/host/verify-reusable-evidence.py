#!/usr/bin/env python3
"""Fail-closed verifier for extracted reusable VM proof evidence.

The reusable branch verifies the generic bootstrap watcher identity marker, the
staged runner and complete input-tree hashes, declared artifact hashes, and the
controlled exit/shutdown records. It never claims legacy scenario steps, state,
dialog, or assistant evidence. A missing or incomplete evidence tree fails closed.
The legacy branch remains only for the pre-existing T2 verifier contract.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_WATCHER_HASH = re.compile(r"watcher script sha256=([0-9a-fA-F]{64})", re.IGNORECASE)
_BOOTSTRAP_HASH = re.compile(r"bootstrap(?: watcher|-watch\.ps1)\s+sha256=([0-9a-fA-F]{64})", re.IGNORECASE)
_RESERVED_VOLUME_ROOT_NAMES = frozenset({"system volume information", "$recycle.bin"})


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
        except (OSError, ValueError, json.JSONDecodeError) as exc:
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
        except (OSError, ValueError, json.JSONDecodeError) as exc:
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
                    except (OSError, ValueError, json.JSONDecodeError):
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


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object) -> pathlib.PurePosixPath:
    text = str(value or "").replace("\\", "/")
    candidate = pathlib.PurePosixPath(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise ValueError(f"unsafe artifact path: {text!r}")
    return candidate


def _input_tree_digest(root: pathlib.Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("input root is not a real directory")
    root = root.resolve()
    entries: list[str] = []
    pending: list[tuple[pathlib.Path, bool]] = [(root, True)]
    while pending:
        directory, is_root = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda entry: entry.name)
        except OSError as exc:
            raise ValueError(f"input directory is unreadable: {directory}: {exc}") from exc
        for entry in children:
            if is_root and entry.name.casefold() in _RESERVED_VOLUME_ROOT_NAMES:
                continue
            path = pathlib.Path(entry.path)
            try:
                if entry.is_symlink():
                    raise ValueError(f"input contains a symlink: {path}")
                if entry.is_dir(follow_symlinks=False):
                    pending.append((path, False))
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    entries.append(f"{path.relative_to(root).as_posix()}|{size}|{_sha256_file(path)}")
                else:
                    raise ValueError(f"input entry has unsupported identity: {path}")
            except OSError as exc:
                raise ValueError(f"input entry is unreadable: {path}: {exc}") from exc
    payload = ("\n".join(sorted(entries)) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_bootstrap_identity(evidence_root: pathlib.Path, expected: str, failures: list[str]) -> None:
    if not _SHA256.fullmatch(expected):
        failures.append("expected generic bootstrap watcher SHA-256 is missing or malformed")
        return
    log_path = evidence_root / "bootstrap.log"
    if not log_path.is_file() or log_path.is_symlink():
        failures.append("missing bootstrap.log for generic watcher identity")
        return
    log = log_path.read_text(encoding="utf-8", errors="replace")
    matches = _BOOTSTRAP_HASH.findall(log)
    if not matches:
        failures.append("bootstrap.log has no generic bootstrap watcher SHA-256 marker")
    elif any(value.lower() != expected.lower() for value in matches):
        failures.append("bootstrap.log generic bootstrap watcher SHA-256 does not match host expectation")


def _validate_host_provenance(
    provenance_path: pathlib.Path,
    expected_bootstrap: str,
    expected_runner: str,
    failures: list[str],
) -> None:
    if not provenance_path.is_file() or provenance_path.is_symlink():
        failures.append("missing host-provenance.json")
        return
    try:
        record = load(provenance_path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"invalid host provenance ({exc})")
        return
    if record.get("schema") != "gentle-ai.yasb-limitora.reusable-vm-host-provenance/v1":
        failures.append("host provenance schema mismatch")
    for field in ("runId", "vmName", "requestedCheckpointName", "requestedCheckpointId", "requestedCheckpointVmId", "requestedCheckpointCreationTimeUtc", "restoreObservedUtc", "bootstrapSha256", "runnerSha256", "inputVhdxSha256"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            failures.append(f"host provenance is missing {field}")
    before = record.get("checkpointBeforeRestore")
    after = record.get("checkpointAfterRestore")
    if not isinstance(before, dict) or not isinstance(after, dict):
        failures.append("host provenance has no before/after checkpoint identity")
    else:
        for field in ("Name", "Id", "VMId", "CreationTime"):
            if not isinstance(before.get(field), str) or not isinstance(after.get(field), str):
                failures.append(f"host provenance checkpoint identity is missing {field}")
            elif before[field] != after[field]:
                failures.append(f"host provenance checkpoint identity drift for {field}")
        expected_fields = {
            "requestedCheckpointName": "Name",
            "requestedCheckpointId": "Id",
            "requestedCheckpointVmId": "VMId",
            "requestedCheckpointCreationTimeUtc": "CreationTime",
        }
        for requested, identity in expected_fields.items():
            if record.get(requested) != before.get(identity):
                failures.append(f"host provenance {requested} does not match before-restore identity")
    if str(record.get("bootstrapSha256", "")).lower() != expected_bootstrap.lower():
        failures.append("host provenance bootstrap SHA-256 does not match host expectation")
    if str(record.get("runnerSha256", "")).lower() != expected_runner.lower():
        failures.append("host provenance runner SHA-256 does not match staged runner")
    if not _SHA256.fullmatch(str(record.get("inputVhdxSha256", ""))):
        failures.append("host provenance input VHDX SHA-256 is malformed")
    outcomes = record.get("outcomes")
    if not isinstance(outcomes, dict):
        failures.append("host provenance has no explicit outcomes")
    else:
        for outcome in ("checkpointRestore", "guestRun", "evidenceExtraction", "verification", "overall"):
            if outcomes.get(outcome) not in {"pending", "success", "failed"}:
                failures.append(f"host provenance outcome {outcome} is invalid")
        if outcomes.get("overall") == "success" and any(
            outcomes.get(outcome) != "success"
            for outcome in ("checkpointRestore", "guestRun", "evidenceExtraction", "verification")
        ):
            failures.append("host provenance reports overall success with an incomplete outcome")


def _validate_reusable_input(input_root: pathlib.Path, failures: list[str]) -> tuple[str, dict[str, tuple[int, str]] | None]:
    required = {"runner.ps1", "scenario.json", "expected-runner.sha256", "expected-artifacts.json"}
    if not input_root.is_dir():
        failures.append("input root is missing")
        return "", None
    for name in sorted(required):
        path = input_root / name
        if not path.is_file() or path.is_symlink():
            failures.append(f"input is missing or unsafe: {name}")
    runner_hash = ""
    manifest: dict[str, tuple[int, str]] | None = None
    try:
        scenario = load(input_root / "scenario.json")
        if scenario.get("schema") != "gentle-ai.yasb-limitora.reusable-vm-run/v1":
            failures.append("scenario.json schema mismatch")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(scenario.get("scenario", ""))):
            failures.append("scenario.json scenario is unsafe or missing")
        expected = (input_root / "expected-runner.sha256").read_text(encoding="utf-8").strip().lower()
        if not _SHA256.fullmatch(expected):
            failures.append("expected-runner.sha256 is not a digest")
        runner_hash = _sha256_file(input_root / "runner.ps1")
        if expected != runner_hash:
            failures.append(f"runner hash mismatch (expected={expected}, actual={runner_hash})")
        artifact_manifest = load(input_root / "expected-artifacts.json")
        if artifact_manifest.get("schema") != "gentle-ai.yasb-limitora.reusable-artifact-manifest/v1":
            failures.append("expected-artifacts.json schema mismatch")
        manifest = {}
        artifacts = artifact_manifest.get("artifacts")
        if not isinstance(artifacts, list):
            raise TypeError("artifact manifest has no artifacts list")
        for entry in artifacts:
            if not isinstance(entry, dict):
                raise TypeError("artifact manifest entry is not an object")
            relative = _safe_relative(entry.get("path"))
            size_value = entry.get("size")
            if not isinstance(size_value, int) or isinstance(size_value, bool):
                raise TypeError(f"malformed artifact size: {relative}")
            size = size_value
            digest = str(entry.get("sha256", "")).lower()
            if size < 0 or not _SHA256.fullmatch(digest):
                raise ValueError(f"malformed artifact manifest entry: {relative}")
            key = relative.as_posix()
            if key in manifest:
                raise ValueError(f"duplicate artifact manifest entry: {key}")
            manifest[key] = (size, digest)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        failures.append(f"invalid reusable input contract ({exc})")
    return runner_hash, manifest


def _validate_reusable_evidence(
    evidence_root: pathlib.Path,
    input_root: pathlib.Path,
    expected_bootstrap: str,
    host_provenance: pathlib.Path | None = None,
) -> int:
    failures: list[str] = []
    if not evidence_root.is_dir():
        failures.append("evidence root is missing")
    runner_hash, manifest = _validate_reusable_input(input_root, failures)
    _validate_bootstrap_identity(evidence_root, expected_bootstrap, failures)
    if host_provenance is not None:
        _validate_host_provenance(host_provenance, expected_bootstrap, runner_hash, failures)
    try:
        input_digest = _input_tree_digest(input_root)
    except (OSError, ValueError) as exc:
        input_digest = ""
        failures.append(f"cannot hash input tree ({exc})")

    done: dict[str, Any] = {}
    exit_record: dict[str, Any] = {}
    exit_hash = ""
    try:
        done = load(evidence_root / "done.json")
        exit_record = load(evidence_root / "exit.json")
        exit_hash = _sha256_file(evidence_root / "exit.json")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"missing or invalid reusable completion records ({exc})")

    if done.get("schema") != "gentle-ai.yasb-limitora.reusable-vm-done/v1":
        failures.append("done.json schema mismatch")
    if exit_record.get("schema") != "gentle-ai.yasb-limitora.reusable-vm-exit/v1":
        failures.append("exit.json schema mismatch")
    if done.get("result") != "success" or done.get("runnerExitCode") != 0:
        failures.append("guest completion is not a controlled success")
    if not isinstance(exit_record.get("success"), bool) or not exit_record.get("success") or exit_record.get("exitCode") != 0:
        failures.append("exit.json is not a successful zero exit")
    if not isinstance(done.get("shutdownRequested"), bool) or not done.get("shutdownRequested") or not isinstance(exit_record.get("shutdownRequested"), bool) or not exit_record.get("shutdownRequested"):
        failures.append("guest did not request clean shutdown")
    if runner_hash and str(done.get("runnerSha256", "")).lower() != runner_hash:
        failures.append("done.json runner hash does not match host input hash")
    if input_digest and str(done.get("inputTreeSha256", "")).lower() != input_digest:
        failures.append("done.json input tree hash does not match host recomputation")
    if not isinstance(done.get("inputUnchanged"), bool) or not done.get("inputUnchanged"):
        failures.append("guest did not attest that input stayed unchanged")
    if done.get("scenario") != exit_record.get("scenario"):
        failures.append("done.json and exit.json scenario identity mismatch")
    if done.get("runnerExitCode") != exit_record.get("runnerExitCode"):
        failures.append("done.json and exit.json runner exit mismatch")

    for output_name in ("runner.stdout.txt", "runner.stderr.txt", "bootstrap.log"):
        output_path = evidence_root / output_name
        if not output_path.is_file() or output_path.is_symlink():
            failures.append(f"missing reusable evidence file: {output_name}")

    observed: dict[str, tuple[int, str]] = {}
    if manifest is not None:
        for relative, (expected_size, expected_hash) in manifest.items():
            path = evidence_root.joinpath(*relative.split("/"))
            if not path.is_file() or path.is_symlink():
                failures.append(f"missing declared artifact: {relative}")
                continue
            actual = (path.stat().st_size, _sha256_file(path))
            observed[relative] = actual
            if actual != (expected_size, expected_hash):
                failures.append(f"artifact mismatch: {relative}")
        records = done.get("artifacts")
        if isinstance(records, list) and len(records) == 1 and isinstance(records[0], list):
            records = records[0]
        recorded: dict[str, tuple[int, str]] = {}
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict):
                    continue
                record_size = record.get("size")
                try:
                    normalized = _safe_relative(record.get("path")).as_posix()
                except ValueError:
                    failures.append("done.json contains an unsafe artifact path")
                    continue
                if isinstance(record_size, int) and not isinstance(record_size, bool):
                    recorded[normalized] = (record_size, str(record.get("sha256", "")).lower())
        if recorded != observed:
            failures.append("done.json artifact records do not match host artifact hashes")

    print(f"input_tree_sha256={input_digest} runner_sha256={runner_hash} exit_sha256={exit_hash} artifacts={len(observed)}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"VERDICT: FAIL ({len(failures)} violation(s))")
        return 1
    print("VERDICT: PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence_root")
    ap.add_argument("--expected-executable")
    ap.add_argument("--input-root", help="detached extraction of the staged input VHDX")
    ap.add_argument("--expected-bootstrap-sha256", default="", help="SHA-256 of the generic guest bootstrap watcher")
    ap.add_argument("--host-provenance", type=pathlib.Path, help="host-run provenance record bound to this archive")
    args = ap.parse_args()

    root = pathlib.Path(args.evidence_root)
    if args.input_root or (root / "done.json").is_file() and _looks_like_reusable_done(root / "done.json"):
        if not args.input_root:
            print("FAIL reusable evidence requires --input-root", file=sys.stderr)
            return 1
        return _validate_reusable_evidence(root, pathlib.Path(args.input_root), args.expected_bootstrap_sha256, args.host_provenance)

    if not args.expected_executable:
        print("FAIL --expected-executable is required for legacy evidence", file=sys.stderr)
        return 2
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


def _looks_like_reusable_done(path: pathlib.Path) -> bool:
    try:
        return load(path).get("schema") == "gentle-ai.yasb-limitora.reusable-vm-done/v1"
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


if __name__ == "__main__":
    sys.exit(main())
