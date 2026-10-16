"""Lifecycle contract: a supplied lifecycle must preserve the original exception.

Contract unit, not lifecycle ownership. The historical module stays an external manifest
input; the RED control is a minimal tracked oracle reproducing only the historical
exception-replacement behavior, and the GREEN control is a minimal conforming shape.
"""

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
CONTRACT = ROOT / "tests" / "powershell" / "test_exception_fidelity_lifecycle_contract.ps1"
FIXTURES = ROOT / "tests" / "fixtures"
BEFORE = FIXTURES / "exception-fidelity-lifecycle-before-fidelity.ps1"
PRESERVING = FIXTURES / "exception-fidelity-lifecycle-preserving.ps1"


def _run_contract(lifecycle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-File", str(CONTRACT), "-LifecyclePath", str(lifecycle)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_contract_rejects_lifecycle_that_replaces_the_original_exception() -> None:
    result = _run_contract(BEFORE)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "ASSERTION FAILED" in output, output
    # The RED control must fail on exception fidelity, not on a missing surface.
    assert "must preserve the original CLR type" in output or "must not substitute a fabricated RuntimeException" in output, output


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_contract_accepts_conforming_lifecycle() -> None:
    result = _run_contract(PRESERVING)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "PASS lifecycle contract exception fidelity assertions=" in result.stdout, output


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell 5.1")
def test_contract_requires_the_core_entry_point(tmp_path: Path) -> None:
    empty = tmp_path / "no-core.ps1"
    empty.write_text("Set-StrictMode -Version Latest\n", encoding="utf-8")
    result = _run_contract(empty)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "must define exactly one Invoke-OwnedCleanupLifecycleCore" in output, output
