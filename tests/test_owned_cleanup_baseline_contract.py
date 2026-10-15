"""Exercise the pure baseline contract with Windows PowerShell 5.1."""

import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_owned_cleanup_baseline_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [
            str(powershell), "-NoProfile", "-NonInteractive", "-File",
            str(root / "tests/powershell/test_owned_cleanup_baseline_contract.ps1"),
            "-RepositoryRoot", str(root),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stderr == ""
    assert result.stdout == (
        "PASS owned-cleanup baseline contract cases=44 guards=12 assertions=977\n"
    )
