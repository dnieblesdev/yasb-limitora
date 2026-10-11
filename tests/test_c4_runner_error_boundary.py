"""Run the actual C4 PowerShell runner boundary test on Windows."""

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
RUNNER = ROOT / "proof-harness" / "guest" / "owned-cleanup" / "runner.ps1"
BASELINE = ROOT / "tests" / "fixtures" / "c4-runner-before-observability.ps1"
BOUNDARY_TEST = ROOT / "tests" / "powershell" / "test_c4_runner_error_boundary.ps1"


def _run_boundary(runner: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(BOUNDARY_TEST),
            "-RunnerPath",
            str(runner),
            "-BaselinePath",
            str(BASELINE),
            "-FixtureParent",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_original_runner_has_expected_observability_red(tmp_path: Path) -> None:
    result = _run_boundary(BASELINE, tmp_path)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "RED original-runner actual-boundary mismatch" in result.stdout
    assert "ASSERTION FAILED" in output


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_c4_runner_error_boundary(tmp_path: Path) -> None:
    result = _run_boundary(RUNNER, tmp_path)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "PASS actual runner-file boundary assertions=204" in result.stdout
