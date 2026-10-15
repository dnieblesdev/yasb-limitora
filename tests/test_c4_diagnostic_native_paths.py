"""Exercise native diagnostic paths through the actual inert C4 runner file."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
HARNESS = ROOT / "tests/powershell/test_c4_diagnostic_native_paths.ps1"


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_c4_diagnostic_native_paths() -> None:
    result = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(HARNESS),
            "-RepositoryRoot",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS native diagnostic public boundary assertions=" in result.stdout
