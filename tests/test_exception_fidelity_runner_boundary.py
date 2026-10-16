"""A2 focused proof: the runner writer receives the exception context its catch holds."""

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
RUNNER = ROOT / "proof-harness" / "guest" / "owned-cleanup" / "runner.ps1"
PROOF = ROOT / "tests" / "powershell" / "test_exception_fidelity_runner_boundary.ps1"


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_runner_writer_receives_caught_exception_context() -> None:
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-File", str(PROOF), "-RunnerPath", str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "PASS A2 runner boundary exception context assertions=" in result.stdout, output
