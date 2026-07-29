"""A quiet native Windows fixture for the process-tree proof."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


_RATE_LIMITS = {
    "rateLimits": {
        "limitId": "codex",
        "planType": "plus",
        "primary": {"windowDurationMins": 300, "usedPercent": 20, "resetsAt": 4102444800},
        "secondary": {"windowDurationMins": 10080, "usedPercent": 30, "resetsAt": 4102444800},
    }
}


def _write(path: Path, values: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(values, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _descendant(marker: Path, sentinel: str) -> None:
    os.write(2, sentinel.encode("ascii") + b"\n")
    marker.write_text("descendant stderr attempted\n", encoding="utf-8")
    while True:
        time.sleep(1)


def _response(identifier: int, result: dict[str, object]) -> None:
    sys.stdout.write(json.dumps({"id": identifier, "result": result}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _run(mode: str, evidence: Path, sentinel: str, descendant_marker: Path) -> None:
    descendant = subprocess.Popen(
        [sys.executable, __file__, "--descendant", str(descendant_marker), sentinel],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    record = {
        "fixture_pid": os.getpid(),
        "helper_pid": os.getppid(),
        "descendant_pid": descendant.pid,
        "authorized": False,
        "fixture_stderr_attempted": False,
    }
    _write(evidence, record)
    if sentinel:
        os.write(2, sentinel.encode("ascii") + b"\n")
        record["fixture_stderr_attempted"] = True
        _write(evidence, record)
    if mode == "timeout":
        for line in sys.stdin:
            if line:
                record["authorized"] = True
                _write(evidence, record)
                break
        while True:
            time.sleep(1)

    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        record["authorized"] = True
        _write(evidence, record)
        if message["id"] == 1:
            _response(1, {"serverInfo": {"name": "fixture"}})
        elif message["id"] == 2:
            _response(2, _RATE_LIMITS)
            return


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--descendant":
        if len(sys.argv) != 4:
            raise SystemExit(2)
        _descendant(Path(sys.argv[2]), sys.argv[3])
        return
    if len(sys.argv) != 5:
        raise SystemExit(2)
    _run(sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))


if __name__ == "__main__":
    main()
