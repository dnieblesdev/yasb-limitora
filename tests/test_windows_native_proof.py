"""Executable native Windows proof for the contained production chain."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import importlib
from importlib import metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import pytest

from yasb_limitora.codex_helper import CodexHelperExecutor
from yasb_limitora.cli import main
from yasb_limitora.isolation.windows_job import (
    WAIT_OBJECT_0,
    JobError,
    JobErrorCode,
    WindowsJobBoundary,
)
from yasb_limitora.model import ProviderOutcome, ProviderState, PublicProviderState, SafeErrorCode, SnapshotFreshness
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError, V2Guard
from yasb_limitora.v2_path import V2FileError, canonicalize_v2_path, read_v2_config
from yasb_limitora.v2_worker import cleanup_complete


pytestmark = [
    pytest.mark.windows_native,
]

_R10_YASB_COMMIT = "7e84e011156844bec5b3565cf73f543bc23160e9"
_R10_YASB_ARCHIVE_SHA256 = "6aa3d74689f7cd7d7a9e3493d2a709c56db4451749413b4e561a199928096f79"
_R10_YASB_MODULE_SHA256 = "5e9f5060cd16901bcf21aa7b070c2f4949d19752dcda18634a7c8c9fc5f70ba1"
_R10_WHEELS = (
    ("pyqt6-6.10.2-cp39-abi3-win_amd64.whl", "bd328cb70bc382c48861cd5f0a11b2b8ae6f5692d5a2d6679ba52785dced327b"),
    ("pyqt6_qt6-6.10.2-py3-none-win_amd64.whl", "c4b7f7d66cc58bddf1bc1ca28dfcf7a45f58cfcb11d81d13a0510409dd4957ac"),
    ("pyqt6_sip-13.10.2-cp314-cp314-win_amd64.whl", "3213bb6e102d3842a3bb7e59d5f6e55f176c80880ff0b39d0dac0cfe58313fb3"),
    ("pydantic-2.13.4-py3-none-any.whl", "45a282cde31d808236fd7ea9d919b128653c8b38b393d1c4ab335c62924d9aba"),
    ("pydantic_core-2.46.4-cp314-cp314-win_amd64.whl", "811ff8e9c313ab425368bcbb36e5c4ebd7108c2bbf4e4089cfbb0b01eff63fac"),
    ("annotated_types-0.7.0-py3-none-any.whl", "1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53"),
    ("typing_extensions-4.15.0-py3-none-any.whl", "f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548"),
    ("typing_inspection-0.4.2-py3-none-any.whl", "4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7"),
    ("pywin32-312-cp314-cp314-win_amd64.whl", "a4dd3a848290ef724347b19f301045831d8e802fa4464f491b98b1e0a081432e"),
    ("pyyaml-6.0.3-cp314-cp314-win_amd64.whl", "4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac"),
    ("winrt_runtime-3.2.1-cp314-cp314-win_amd64.whl", "e36e587ab5fd681ee472cd9a5995743f75107a1a84d749c64f7e490bc86bc814"),
    ("winrt_windows_data_xml_dom-3.2.1-cp314-cp314-win_amd64.whl", "1cf1b6f31fff4e4c0ae30f1643b169da72b3b053a2996010f2c3a1e26b5d4970"),
    ("winrt_windows_ui_notifications-3.2.1-cp314-cp314-win_amd64.whl", "943599c727abf710ae94644b1d521e11857bd568e080e894a8be11aa717e383a"),
    ("winrt_windows_management_deployment-3.2.1-cp314-cp314-win_amd64.whl", "fbf20fa4becf20edb9980bfb9e4f45dfd323d57e4819c49c40a65fde82a1bb24"),
    ("pytest-8.4.1-py3-none-any.whl", "539c70ba6fcead8e78eebbf1115e8b589e7565830d7d006a8723f19ac8a0afb7"),
    ("iniconfig-2.1.0-py3-none-any.whl", "9deba5723312380e77435581c6bf4935c94cbfab9b1ed33ef8d238ea168eb760"),
    ("packaging-25.0-py3-none-any.whl", "29572ef2b1f17581046b3a2227d5c611fb25ec70ca1ba8554b24b0e69331a484"),
    ("pluggy-1.6.0-py3-none-any.whl", "e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746"),
    ("pygments-2.19.2-py3-none-any.whl", "86540386c03d588bb81d44bc3928634ff26449851e99741617ecb9037ee5ec0b"),
    ("colorama-0.4.6-py2.py3-none-any.whl", "4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6"),
    ("limitora-0.1.0-py3-none-any.whl", "84440f0b4c32c52559e91526c7c70d41532248fff817106e1775b4281d7b5c09"),
    ("setuptools-80.9.0-py3-none-any.whl", "062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922"),
)
_R10_WINRT_IMPORTS = (
    "winrt.system",
    "winrt.windows.data.xml.dom",
    "winrt.windows.ui.notifications",
    "winrt.windows.management.deployment",
)
_R10_RUNTIME_IMPORTS = ("PyQt6.QtCore", "pydantic", "pydantic_core", "yaml", "_yaml", "win32api", "pywintypes", *_R10_WINRT_IMPORTS)


def _require_r10_workflow_contract(text: str) -> None:
    required = (_R10_YASB_COMMIT, _R10_YASB_ARCHIVE_SHA256, _R10_YASB_MODULE_SHA256, "v2.0.6", "3.14", "x64", "--no-build-isolation", "wheelPaths.Count -ne 22")
    if any(value not in text for value in required):
        raise AssertionError("R10 frozen source identity drifted")
    if text.count(_R10_YASB_COMMIT) < 2 or f"tar.gz/{_R10_YASB_COMMIT}" not in text:
        raise AssertionError("R10 source commit/archive identity drifted")
    for filename, digest in _R10_WHEELS:
        if text.count(filename) < 2 or digest not in text or "--no-index" not in text or "--no-deps" not in text:
            raise AssertionError("R10 fixed wheel closure drifted")
    binary_wheels = (filename for filename, _ in _R10_WHEELS if filename.startswith(("pyqt6_sip", "pydantic_core", "pywin32", "pyyaml", "winrt_")))
    if len(_R10_WHEELS) != 22 or any("cp314" not in filename or "win_amd64" not in filename for filename in binary_wheels):
        raise AssertionError("R10 closure is not CPython 3.14 x64")
    if any(module not in text for module in _R10_RUNTIME_IMPORTS):
        raise AssertionError("R10 WinRT import smoke is incomplete")


def _assert_pe(path: Path) -> None:
    data = path.read_bytes()
    if data[:2] != b"MZ" or len(data) < 0x40:
        raise AssertionError("fixture is not a Windows PE")
    pe_offset = int.from_bytes(data[0x3C:0x40], "little")
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise AssertionError("fixture is not a Windows PE")


def _resolve_no_space_launcher(candidates: list[Path]) -> Path:
    if len(candidates) != 1 or " " in str(candidates[0]) or candidates[0].suffix.lower() != ".exe":
        raise AssertionError("launcher identity is ambiguous or unsafe")
    return candidates[0]


def test_r10_admission_contract_rejects_identity_and_closure_drift() -> None:
    workflow = (Path(__file__).parents[1] / ".github/workflows/windows-proof.yml").read_text(encoding="utf-8")
    wrapper = (Path(__file__).parents[1] / ".github/workflows/windows-proof-functions.ps1").read_text(encoding="utf-8")
    contract = workflow + wrapper
    _require_r10_workflow_contract(contract)
    assert re.search(r"native-proof:\s+needs: r10-admission\s+if: always\(\).*?steps:\s+- name: Enforce R10 admission delivery gate\s+if: always\(\).*?needs\.r10-admission\.result.*?-ne \"success\".*?throw", workflow, re.S) and re.search(r"r10-admission:.*?R10_YASB_SOURCE_ROOT=.*?Out-File \$env:GITHUB_ENV.*?R10_LAUNCHER_PATH=.*?Out-File \$env:GITHUB_ENV.*?R10_LAUNCHER_SHA256=.*?Out-File \$env:GITHUB_ENV.*?R10_FIXTURE_EXE=.*?Out-File \$env:GITHUB_ENV.*?- name: Run mandatory R10 admission before widget construction", workflow, re.S) and not re.search(r"- name: Run mandatory R10 admission before widget construction.*?R10_(?:YASB_SOURCE_ROOT|LAUNCHER_PATH|LAUNCHER_SHA256|FIXTURE_EXE)", workflow, re.S)
    assert re.search(r'\$fixtureSource = \[IO\.Path\]::GetFullPath\(\(Join-Path \$env:GITHUB_WORKSPACE "tests\\fixtures\\r10_yasb_fixture\.cs"\)\).*?& \$csc /nologo /target:exe "/out:\$fixture" "\$fixtureSource" \*> \(Join-Path \$root "csc\.log"\).*?R10 fixture compiler:.*?Math\]::Min\(240.*?throw "R10 fixture compilation failed"', workflow, re.S) and not re.search(r"(?s)- name: Validate artifacts before publication\s+if: always\(\)", workflow)
    for original, replacement in (
        (_R10_YASB_COMMIT, "0" * 40),
        (_R10_YASB_ARCHIVE_SHA256, "0" * 64),
        (_R10_YASB_MODULE_SHA256, "0" * 64),
        ("v2.0.6", "v2.0.5"),
        ("cp314", "cp313"),
        ("win_amd64", "win32"),
        (_R10_WHEELS[-1][0], "wrong.whl"),
    ):
        with pytest.raises(AssertionError):
            _require_r10_workflow_contract(contract.replace(original, replacement, 1))


def test_r10_admission_contract_rejects_failed_imports_and_unsafe_fixture(tmp_path: Path) -> None:
    workflow = (Path(__file__).parents[1] / ".github/workflows/windows-proof.yml").read_text(encoding="utf-8")
    wrapper = (Path(__file__).parents[1] / ".github/workflows/windows-proof-functions.ps1").read_text(encoding="utf-8")
    contract = workflow + wrapper
    for module in _R10_RUNTIME_IMPORTS:
        with pytest.raises(AssertionError):
            _require_r10_workflow_contract(contract.replace(module, "missing.module", 1))
    for payload in (b"malformed", b"print('not a PE')"):
        path = tmp_path / "r10-provider.exe"
        path.write_bytes(payload)
        with pytest.raises(AssertionError):
            _assert_pe(path)


def test_r10_admission_contract_rejects_launcher_ambiguity_spaces_path_drift_and_timeout_tree_cleanup(tmp_path: Path) -> None:
    launcher = tmp_path / "yasb-limitora.exe"
    launcher.write_bytes(b"MZ")
    assert _resolve_no_space_launcher([launcher]) == launcher
    with pytest.raises(AssertionError):
        _resolve_no_space_launcher([launcher, launcher])
    with pytest.raises(AssertionError):
        _resolve_no_space_launcher([tmp_path / "space dir" / "yasb-limitora.exe"])
    wrapper = (Path(__file__).parents[1] / ".github/workflows/windows-proof-functions.ps1").read_text(encoding="utf-8")
    timeout = wrapper[wrapper.index("if (-not $process.WaitForExit"):wrapper.index("if ($process.ExitCode")]
    assert all(token in timeout for token in ("taskkill.exe", "/PID", "/T", "/F", "$process.Id", "$LASTEXITCODE", "WaitForExit(5000)", "Get-CimInstance", "Win32_Process", "ParentProcessId", "ProcessId", "$pids", "4096", "metadata unavailable", "metadata ambiguous", "verification ambiguous"))
    assert timeout.count("Get-CimInstance") >= 2 and "foreach ($candidatePid in @($process.Id) + @($pids))" in timeout
    assert "$process.Kill()" not in timeout and "Get-Process -Id $process.Id" not in timeout
    assert 'ConvertTo-R10ProcessArgument $_ }) -join " "' in wrapper
    assert re.search(r"(?i)timeout", wrapper)
    assert re.search(r"(?i)nonzero|exit", wrapper)
    assert re.search(r"(?i)skipped", wrapper)
    assert "$env:Path" in wrapper and "finally" in wrapper.lower()


def test_r10_native_experience_contract_is_declared() -> None:
    root = Path(__file__).parents[1]; source = Path(__file__).read_text(encoding="utf-8"); workflow = (root / ".github/workflows/windows-proof.yml").read_text(encoding="utf-8"); wrapper = (root / ".github/workflows/windows-proof-functions.ps1").read_text(encoding="utf-8")
    required_source = ("test_native_yasb_customwidget_lifecycle_and_recovery", "QApplication", "CustomWidget", "QTimer", "CSSProcessor", "valid_to_malformed_to_valid", "tooltip_text", "r10-yasb-experience.json")
    assert all(marker in source for marker in required_source)
    assert "from core.utils.css_processor import CSSProcessor" in source and "from PyQt6.QtGui import QGuiApplication" in source and ("from PyQt6.QtCore import " + "QEvent, QGuiApplication") not in source
    assert "app." + "setStyleSheet(css_text)" not in source and "QT_QPA_PLATFORM: offscreen" not in workflow and "r10-yasb-experience.xml" in workflow
    assert "Assert-R10ExperienceEvidence" in wrapper and wrapper.count("not native_yasb_customwidget_lifecycle_and_recovery") >= 2
    assert re.search(r'\$Mode -eq "selected".*?else.*?"-k", "not native_yasb_customwidget_lifecycle_and_recovery"', wrapper, re.S)
    assert all(marker in wrapper for marker in ("primary_label", "alternate_label", "malformed_tooltip", "launcher_paths", "final_real_qtimer_refresh", "worker_threads_terminated", "subprocesses_terminated", "timer_inactive", "worker_deleted", "Get-R10JUnitDiagnostic", "--junitxml=", "diagnostics withheld", "R10_JUNIT_DIAGNOSTIC_STAGE", 'stage = "args"', 'stage = "xml"', 'stage = "candidate"', 'stage = "node"', 'stage = "match"', 'stage = "sanitize"', 'stage = "assemble"', "password", "240"))
    start = source.rfind("    def cleanup_widget"); cleanup = source[start:source.index("    real_before =", start)]; assert all(token in cleanup for token in ("process.terminate()", "process.kill()", "subprocess.TimeoutExpired")) and cleanup.index("process.terminate()") < cleanup.index("thread.join(timeout=5)") ; assert source.index("cleanup_observed = cleanup_widget()") < source.index('"lifecycle": [')

@pytest.mark.skipif(not any(shutil.which(name) for name in ("pwsh", "powershell")), reason="PowerShell unavailable")
def test_r10_junit_diagnostic_integration_contract(tmp_path: Path) -> None:
    shell = next(shutil.which(name) for name in ("pwsh", "powershell") if shutil.which(name)); wrapper = Path(__file__).parents[1] / ".github/workflows/windows-proof-functions.ps1"; cases = (("r10-admission.xml", "windows", r'File "C:\Users\Jane Doe\repo\test.py", line 12, in test_name password=SECRET; token=SECOND', 'R10 diagnostic: test=windows; line=12; message=File "[PATH]", line 12, in test_name [REDACTED]; [REDACTED]', None), ("r10-admission.xml", "posix", r"File '/home/Jane Doe/repo/test.py', line 7, in test_name api_key='VALUE'", "R10 diagnostic: test=posix; line=7; message=File '[PATH]', line 7, in test_name [REDACTED]", None), ("r10-admission.xml", "relative", r"tests/test_parser.py:23: message credential=VALUE", "R10 diagnostic: test=relative; line=23; message=tests/test_parser.py:23: message [REDACTED]", None), ("r10-admission.xml", "cap", "tests/test_parser.py:99: " + "x" * 300, ("R10 diagnostic: test=cap; line=99; message=tests/test_parser.py:99: " + "x" * 300)[:240], None), ("r10-admission.xml", "malformed", "MALFORMED", "diagnostics withheld", "xml"), ("r10-yasb-experience.xml", "missing", None, "diagnostics withheld", "args"))
    for name, testcase, message, normal, stage in cases:
        (tmp_path / name).unlink(missing_ok=True) if message is None else (tmp_path / name).write_text("<testsuite><testcase name=\"" + testcase + "\"><failure message=\"" + ("<testsuite>" if message == "MALFORMED" else message.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&apos;")) + "\"/></testcase></testsuite>", encoding="utf-8")
        for trace in ((False, None), (True, stage)):
            environment = os.environ.copy(); environment.pop("R10_JUNIT_DIAGNOSTIC_STAGE", None); environment.update({"R10_JUNIT_DIAGNOSTIC_STAGE": "1"} if trace else {}); expected = normal if stage is None or not trace else f"{normal}; stage={stage}"
            result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", f". '{wrapper}'; Get-R10JUnitDiagnostic @('--junitxml={name}')"], cwd=tmp_path, env=environment, capture_output=True, text=True); assert result.returncode == 0 and result.stdout.strip() == expected
@pytest.mark.skipif(os.name != "nt", reason="R10 native admission requires Windows")
def test_r10_native_admission_identity_imports_and_fixture() -> None:
    source_root_value = os.environ.get("R10_YASB_SOURCE_ROOT")
    if source_root_value is None:
        assert all(name not in os.environ for name in ("R10_LAUNCHER_PATH", "R10_LAUNCHER_SHA256", "R10_FIXTURE_EXE"))
        return
    if sys.version_info[:2] != (3, 14) or os.environ.get("PROCESSOR_ARCHITECTURE") != "AMD64":
        pytest.fail("R10 admission requires Python 3.14 AMD64")
    source_root = Path(source_root_value)
    settings = source_root / "settings.py"
    module = source_root / "core/widgets/yasb/custom.py"
    assert 'BUILD_VERSION = "2.0.6"' in settings.read_text(encoding="utf-8")
    assert hashlib.sha256(module.read_bytes()).hexdigest() == _R10_YASB_MODULE_SHA256
    expected_versions = {
        "PyQt6": "6.10.2",
        "PyQt6-Qt6": "6.10.2",
        "PyQt6-sip": "13.10.2",
        "pydantic": "2.13.4",
        "pydantic-core": "2.46.4",
        "annotated-types": "0.7.0",
        "typing-extensions": "4.15.0",
        "typing-inspection": "0.4.2",
        "pywin32": "312",
        "PyYAML": "6.0.3",
        "winrt-runtime": "3.2.1",
        "winrt-windows-data-xml-dom": "3.2.1",
        "winrt-windows-ui-notifications": "3.2.1",
        "winrt-windows-management-deployment": "3.2.1",
        "pytest": "8.4.1",
        "iniconfig": "2.1.0",
        "packaging": "25.0",
        "pluggy": "1.6.0",
        "Pygments": "2.19.2",
        "colorama": "0.4.6",
        "limitora": "0.1.0",
        "setuptools": "80.9.0",
    }
    for distribution, version in expected_versions.items():
        assert metadata.version(distribution) == version
    for name in _R10_RUNTIME_IMPORTS:
        imported = importlib.import_module(name)
        assert imported.__file__ and Path(imported.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    fixture = Path(os.environ["R10_FIXTURE_EXE"])
    _assert_pe(fixture)
    launcher = _resolve_no_space_launcher([Path(os.environ["R10_LAUNCHER_PATH"])])
    assert hashlib.sha256(launcher.read_bytes()).hexdigest() == os.environ["R10_LAUNCHER_SHA256"]
@pytest.mark.skipif(os.name != "nt", reason="R10 native YASB experience requires Windows")
def test_native_yasb_customwidget_lifecycle_and_recovery(tmp_path: Path) -> None:
    """Exercise the pinned YASB CustomWidget without replacing native Qt."""
    if os.environ.get("QT_QPA_PLATFORM"):
        pytest.fail("R10 native YASB proof must not use a substituted Qt platform")
    source_root = Path(os.environ["R10_YASB_SOURCE_ROOT"])
    assert 'BUILD_VERSION = "2.0.6"' in (source_root / "settings.py").read_text(encoding="utf-8")
    assert hashlib.sha256((source_root / "core/widgets/yasb/custom.py").read_bytes()).hexdigest() == _R10_YASB_MODULE_SHA256

    from PyQt6 import sip
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication
    from core.utils.css_processor import CSSProcessor
    from yaml import safe_load

    from core.validation.widgets.yasb.custom import CustomConfig
    from core.widgets.yasb.custom import CustomWidget
    app = QApplication.instance() or QApplication([])
    assert QGuiApplication.platformName().lower() == "windows"
    root = Path(__file__).parents[1]
    yaml_text = (root / "examples/customwidget/customwidget.yaml").read_text(encoding="utf-8")
    css_text = (root / "examples/customwidget/styles.css").read_text(encoding="utf-8")
    document = safe_load(yaml_text)
    options = document["widgets"]["limitora_r9"]["options"]
    assert options == {
        "class_name": "limitora-r9",
        "label": "{data[providers][0][compact_text]}",
        "label_alt": "{data[providers][0][alternate_text]}",
        "tooltip": True,
        "tooltip_label": "{data[providers][0][tooltip_text]}",
        "exec_options": {
            "run_cmd": "yasb-limitora --output-version 2",
            "run_once": False,
            "run_interval": 120000,
            "return_format": "json",
            "hide_empty": True,
            "use_shell": False,
        },
    }
    assert all(selector in css_text for selector in (".custom-widget.limitora-r9", ".label", ".label.alt", ".icon"))
    processed_css = CSSProcessor(str(root / "examples/customwidget/styles.css")).process()
    assert processed_css
    app.setStyleSheet(processed_css)
    assert app.styleSheet() == processed_css
    expected_primary = "Quota 80% remaining; state=available; freshness=fresh"
    expected_alternate = "Quota account / day: 80% remaining; state=available; freshness=fresh"
    expected_tooltip = "State: available\nFreshness: fresh\nQuota: 80% remaining"
    expected_malformed_primary = "{data[providers][0][compact_text]}"
    expected_malformed_alternate = "{data[providers][0][alternate_text]}"

    state_path = tmp_path / "r10-fixture.state"
    state_path.write_text("valid", encoding="ascii")
    config_path = tmp_path / "r10-config.json"
    config_path.write_text(
        json.dumps({"codex": {"enabled": False}, "opencode_go": {"enabled": False}}),
        encoding="utf-8",
    )
    fixture = Path(os.environ["R10_FIXTURE_EXE"])
    _assert_pe(fixture)
    scripts = Path(sys.prefix) / "Scripts"
    saved_path = os.environ["PATH"]
    real_launcher = _resolve_no_space_launcher(list(scripts.glob("yasb-limitora*.exe")))
    assert real_launcher.resolve() == Path(os.environ["R10_LAUNCHER_PATH"]).resolve()
    real_hash_before = hashlib.sha256(real_launcher.read_bytes()).hexdigest()
    assert real_hash_before == os.environ["R10_LAUNCHER_SHA256"]
    shadow_dir = Path(tempfile.gettempdir()) / "r10-yasb-shadow"
    if " " in str(shadow_dir):
        pytest.fail("R10 shadow launcher path contains spaces")
    shadow_dir.mkdir(parents=True, exist_ok=True)
    shadow_launcher = shadow_dir / "yasb-limitora.exe"
    shutil.copy2(fixture, shadow_launcher)
    shadow_hash = hashlib.sha256(shadow_launcher.read_bytes()).hexdigest()

    base_env = os.environ.copy()
    base_env.update({"YASB_LIMITORA_CONFIG": str(config_path), "YASB_R10_FIXTURE_STATE": str(state_path)})
    def run_launcher(path: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [str(path), "--output-version", "2"],
            env=environment,
            capture_output=True,
            timeout=5,
            check=False,
        )

    def wait_for(predicate, description: str) -> None:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError(f"native YASB lifecycle timeout: {description}")

    def current_tooltip(widget: object) -> str:
        return widget._widget_container._tooltip_filter.tooltip_text

    def stream_record(role: str, path: Path, result: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
        combined = result.stdout + result.stderr
        assert not re.search(rb"password|api[_-]?key|authorization|cookie|native-redaction-sentinel", combined, re.I)
        return {
            "role": role,
            "launcher_name": path.name,
            "launcher_path": "<sys.prefix>/Scripts/yasb-limitora.exe" if path.resolve() == real_launcher.resolve() else "<temp>/r10-yasb-shadow/yasb-limitora.exe",
            "exit_code": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "stderr_empty": result.stderr == b"",
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        }

    custom_module = importlib.import_module("core.widgets.yasb.custom")
    original_worker_run, original_popen = custom_module.CustomWorker.run, custom_module.subprocess.Popen
    worker_threads: list[threading.Thread] = []; widget_processes: list[subprocess.Popen[bytes]] = []

    def tracking_worker_run(worker: object) -> None:
        worker_threads.append(threading.current_thread()); original_worker_run(worker)

    def tracking_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process = original_popen(*args, **kwargs)
        if "creationflags" in kwargs:
            widget_processes.append(process)
        return process

    def cleanup_widget() -> dict[str, object]:
        widget.timer.stop(); worker = widget._worker; worker_deleted_before_cleanup = worker is None or sip.isdeleted(worker)
        if worker is not None and not worker_deleted_before_cleanup: worker.stop()
        for process in widget_processes:
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            if process.poll() is None: raise AssertionError("native widget subprocess survived cleanup")
        for thread in worker_threads: thread.join(timeout=5)
        observed = {"timer_inactive": not widget.timer.isActive(), "worker_stopped": worker_deleted_before_cleanup or not worker._is_running, "worker_threads_terminated": all(not thread.is_alive() for thread in worker_threads), "subprocesses_terminated": all(process.poll() is not None for process in widget_processes)}
        widget.close(); observed["widget_closed"] = not widget.isVisible()
        if worker is not None and not worker_deleted_before_cleanup: worker.deleteLater()
        widget._worker = None; observed["worker_released"] = widget._worker is None; widget.deleteLater()
        for _ in range(50):
            app.processEvents(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if sip.isdeleted(widget):
                break
            time.sleep(0.02)
        observed.update({"worker_deleted": worker is None or sip.isdeleted(worker), "widget_deleted": sip.isdeleted(widget)})
        if not all(observed.values()): raise AssertionError(f"native YASB cleanup incomplete: {observed}")
        return observed

    real_before = run_launcher(real_launcher, {**os.environ, "YASB_LIMITORA_CONFIG": str(config_path)})
    assert real_before.returncode == 0 and real_before.stderr == b""
    assert json.loads(real_before.stdout)["version"] == 2

    os.environ.update(base_env)
    os.environ["PATH"] = str(shadow_dir) + os.pathsep + saved_path
    widget = None
    refreshes: list[float] = []
    try:
        custom_module.CustomWorker.run = tracking_worker_run
        custom_module.subprocess.Popen = tracking_popen
        valid_probe = run_launcher(shadow_launcher, os.environ.copy())
        assert valid_probe.returncode == 0 and json.loads(valid_probe.stdout)["version"] == 2
        widget = CustomWidget(CustomConfig.model_validate(options))
        widget.show()
        wait_for(
            lambda: isinstance(widget._exec_data, dict) and widget._widgets[0].text().startswith("Quota 80%"),
            "initial valid render",
        )
        assert widget.isVisible()
        assert widget._widgets[0].text() == expected_primary
        assert current_tooltip(widget) == expected_tooltip
        assert widget._widgets[0].isVisible() and not widget._widgets_alt[0].isVisible()
        assert widget._widget_frame.property("class") == "widget custom-widget limitora-r9"
        assert widget._widgets[0].property("class") == "label"
        assert widget._widgets_alt[0].property("class") == "label alt"
        valid_observed = {"primary_label": widget._widgets[0].text(), "alternate_label": widget._widgets_alt[0].text(), "tooltip": current_tooltip(widget), "visible": widget.isVisible(), "toggle": {"primary_visible": widget._widgets[0].isVisible(), "alternate_visible": widget._widgets_alt[0].isVisible()}}

        widget._toggle_label()
        assert widget._widgets_alt[0].isVisible() and not widget._widgets[0].isVisible()
        assert widget._widgets_alt[0].text() == expected_alternate
        assert widget.isVisible() and current_tooltip(widget) == expected_tooltip
        alternate_observed = {"primary_label": widget._widgets[0].text(), "alternate_label": widget._widgets_alt[0].text(), "tooltip": current_tooltip(widget), "visible": widget.isVisible(), "toggle": {"primary_visible": widget._widgets[0].isVisible(), "alternate_visible": widget._widgets_alt[0].isVisible()}}
        widget._toggle_label()
        widget.timer.stop()
        widget.timer.setInterval(50)
        widget.timer.timeout.connect(lambda: refreshes.append(time.monotonic()))
        widget.timer.start()

        state_path.write_text("malformed", encoding="ascii")
        malformed_probe = run_launcher(shadow_launcher, os.environ.copy())
        assert malformed_probe.returncode == 0 and malformed_probe.stdout == b"{" and malformed_probe.stderr == b""
        refresh_count = len(refreshes)
        wait_for(
            lambda: len(refreshes) > refresh_count
            and widget._widgets[0].text() == expected_malformed_primary
            and widget._widgets_alt[0].text() == expected_malformed_alternate
            and current_tooltip(widget) == "None"
            and not widget.isVisible()
            and not widget._widgets[0].isVisible()
            and not widget._widgets_alt[0].isVisible(),
            "malformed fallback",
        )
        malformed_observed = {"primary_label": widget._widgets[0].text(), "alternate_label": widget._widgets_alt[0].text(), "tooltip": current_tooltip(widget), "visible": widget.isVisible(), "fallback": "raw_template_labels_and_literal_None", "toggle": {"primary_visible": widget._widgets[0].isVisible(), "alternate_visible": widget._widgets_alt[0].isVisible()}}

        state_path.write_text("valid", encoding="ascii")
        widget.timer.stop()
        os.environ["PATH"] = saved_path
        assert os.environ["PATH"] == saved_path
        restored_launcher = _resolve_no_space_launcher(list(scripts.glob("yasb-limitora*.exe")))
        assert restored_launcher.resolve() == real_launcher.resolve()
        real_hash_after = hashlib.sha256(restored_launcher.read_bytes()).hexdigest()
        assert real_hash_after == real_hash_before
        real_after = run_launcher(restored_launcher, {**base_env, "PATH": saved_path})
        assert real_after.returncode == 0 and real_after.stderr == b""
        assert json.loads(real_after.stdout)["version"] == 2
        refresh_count = len(refreshes)
        widget.timer.start()
        wait_for(
            lambda: len(refreshes) > refresh_count
            and widget.isVisible()
            and widget._widgets[0].text() == expected_primary
            and widget._widgets_alt[0].text() == expected_alternate
            and widget._widgets[0].isVisible()
            and not widget._widgets_alt[0].isVisible()
            and current_tooltip(widget) == expected_tooltip,
            "final valid restoration under restored launcher",
        )
        final_observed = {"primary_label": widget._widgets[0].text(), "alternate_label": widget._widgets_alt[0].text(), "tooltip": current_tooltip(widget), "visible": widget.isVisible(), "toggle": {"primary_visible": widget._widgets[0].isVisible(), "alternate_visible": widget._widgets_alt[0].isVisible()}, "path_restored": os.environ["PATH"] == saved_path, "final_real_qtimer_refresh": True}
        css_observed = {"processor": "core.utils.css_processor.CSSProcessor", "processed": True, "stylesheet_applied": app.styleSheet() == processed_css, "classes": {"widget": widget._widget_frame.property("class"), "primary": widget._widgets[0].property("class"), "alternate": widget._widgets_alt[0].property("class")}}
        cleanup_observed = cleanup_widget()

        evidence = {
            "native": True,
            "lifecycle": ["constructed", "valid", "alternate", "malformed", "restored_valid", "cleaned"],
            "identity": {
                "yasb_version": "2.0.6",
                "yasb_commit": _R10_YASB_COMMIT,
                "custom_module_sha256": _R10_YASB_MODULE_SHA256,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "architecture": os.environ.get("PROCESSOR_ARCHITECTURE"),
                "qt_platform": QGuiApplication.platformName(),
                "launcher_name": real_launcher.name,
                "launcher_sha256_before": real_hash_before,
                "launcher_sha256_after": real_hash_after,
                "shadow_launcher_sha256": shadow_hash,
            },
            "expected": {
                "primary_label": expected_primary,
                "alternate_label": expected_alternate,
                "tooltip": expected_tooltip,
                "alternate_tooltip": expected_tooltip,
                "malformed_label": expected_malformed_primary,
                "malformed_alternate_label": expected_malformed_alternate,
                "malformed_tooltip": "None",
                "malformed_visible": False,
                "valid_toggle": {"primary_visible": True, "alternate_visible": False},
                "alternate_toggle": {"primary_visible": False, "alternate_visible": True},
                "malformed_toggle": {"primary_visible": False, "alternate_visible": False},
                "final_toggle": {"primary_visible": True, "alternate_visible": False},
                "css_class": "widget custom-widget limitora-r9",
                "configured_refresh_ms": 120000,
            },
            "observed": {
                "valid": valid_observed,
                "alternate": alternate_observed,
                "malformed": malformed_observed,
                "final": final_observed,
                "css": css_observed,
                "cleanup": cleanup_observed,
                "qt_platform": QGuiApplication.platformName(),
                "timer_interval_test_ms": 50,
                "timer_refresh_count": len(refreshes),
                "valid_to_malformed_to_valid": True,
            },
            "launcher_streams": [
                stream_record("installed_before", real_launcher, real_before),
                stream_record("shadow_valid", shadow_launcher, valid_probe),
                stream_record("shadow_malformed", shadow_launcher, malformed_probe),
                stream_record("installed_after", restored_launcher, real_after),
            ],
            "launcher_paths": {"installed": "<sys.prefix>/Scripts/yasb-limitora.exe", "shadow": "<temp>/r10-yasb-shadow/yasb-limitora.exe", "path_restored": os.environ["PATH"] == saved_path},
            "sanitization": {
                "secret_like_output": False,
                "raw_streams_persisted": False,
                "paths_redacted": True,
                "status": "pass",
            },
            "r11_handoff": {
                "status": "excluded_from_r10",
                "next": "R11",
                "excluded": ["live providers", "credentials", "network smoke", "MSI/release coverage"],
            },
        }
        serialized = json.dumps(evidence, sort_keys=True)
        assert not re.search(r"password|api[_-]?key|authorization|cookie|native-redaction-sentinel", serialized, re.I)
        evidence_path = os.environ.get("YASB_NATIVE_EXPERIENCE_EVIDENCE_PATH")
        if not evidence_path:
            pytest.fail("R10 native YASB evidence path is unavailable")
        Path(evidence_path).write_text(serialized + "\n", encoding="utf-8")
    finally:
        custom_module.CustomWorker.run = original_worker_run
        custom_module.subprocess.Popen = original_popen
        if widget is not None and not sip.isdeleted(widget):
            cleanup_widget()
        os.environ["PATH"] = saved_path
        state_path.unlink(missing_ok=True)

_FIXTURE = Path(__file__).with_name("fixtures") / "windows_descendant.py"
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_DESCENDANT_ATTEMPT = "descendant stderr attempted\n"
_CHECKPOINT_ENV = "YASB_NATIVE_CHECKPOINT_PATH"
(
    _CHECKPOINT_START,
    _CHECKPOINT_SUCCESS_EXECUTOR_RETURNED,
    _CHECKPOINT_SUCCESS_VALIDATED,
    _CHECKPOINT_SUCCESS_TREE_GONE,
    _CHECKPOINT_TIMEOUT_TREE_OBSERVED,
    _CHECKPOINT_TIMEOUT_VALIDATED,
    _CHECKPOINT_TIMEOUT_STATE_VALIDATED,
    _CHECKPOINT_TIMEOUT_TREE_GONE,
    _CHECKPOINT_FINAL_SCAN_COMPLETE,
) = range(1, 10)
_CHECKPOINT_PAYLOADS = {f"{stage}\n".encode("ascii"): str(stage) for stage in range(1, 10)}

class _OsStreamCapture:
    def __init__(self, root: Path, label: str) -> None:
        self.stdout_path = root / f"{label}-stdout.log"
        self.stderr_path = root / f"{label}-stderr.log"
        self._saved: dict[int, int] = {}
        self.stdout_bytes = b""
        self.stderr_bytes = b""

    def __enter__(self) -> "_OsStreamCapture":
        try:
            for fd, path in ((1, self.stdout_path), (2, self.stderr_path)):
                self._saved[fd] = os.dup(fd)
                sink = os.open(
                    os.fspath(path),
                    os.O_BINARY | os.O_CREAT | os.O_TRUNC | os.O_WRONLY
                    if hasattr(os, "O_BINARY")
                    else os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                    0o600,
                )
                os.dup2(sink, fd)
                os.close(sink)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        for fd, saved in self._saved.items():
            os.dup2(saved, fd)
            os.close(saved)
        self.stdout_bytes = self.stdout_path.read_bytes()
        self.stderr_bytes = self.stderr_path.read_bytes()

def _assert_streams_clean(capture: _OsStreamCapture) -> None:
    if capture.stdout_bytes or capture.stderr_bytes:
        raise AssertionError("native proof stream isolation failed")

def _assert_descendant_output_attempted(marker: Path) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not marker.exists():
        time.sleep(0.05)
    if not marker.exists() or marker.read_text(encoding="utf-8") != _DESCENDANT_ATTEMPT:
        raise AssertionError("native descendant output attempt was not observed")

def _write_checkpoint(stage: int) -> None:
    if f"{stage}\n".encode("ascii") not in _CHECKPOINT_PAYLOADS:
        raise AssertionError("native proof checkpoint unavailable")
    checkpoint_path = os.environ.get(_CHECKPOINT_ENV)
    if not checkpoint_path:
        return
    target = Path(checkpoint_path)
    temporary = target.with_name(f"{target.name}.tmp")
    try:
        with temporary.open("w", encoding="ascii", newline="\n") as stream:
            stream.write(f"{stage}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception as error:  # noqa: BLE001 - checkpoint failures stay redacted
        temporary.unlink(missing_ok=True)
        raise AssertionError("native proof checkpoint unavailable") from error

def _classify_checkpoint(path: Path) -> str:
    try:
        return _CHECKPOINT_PAYLOADS.get(path.read_bytes(), "unknown")
    except FileNotFoundError:
        return "unknown"

def _process_is_running(pid: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE,
        False,
        pid,
    )
    if not handle:
        return False
    code = wintypes.DWORD()
    try:
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)

def _read_evidence(path: Path, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.05)
            continue
        if value.get("authorized"):
            return value
        time.sleep(0.05)
    pytest.fail("native fixture did not reach the post-READY protocol boundary")

def _assert_gone(pids: list[int]) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and any(_process_is_running(pid) for pid in pids):
        time.sleep(0.05)
    assert all(not _process_is_running(pid) for pid in pids)

def _runner(mode: str, evidence: Path, sentinel: str, descendant_marker: Path) -> tuple[str, ...]:
    return (sys.executable, str(_FIXTURE), mode, str(evidence), sentinel, str(descendant_marker))


def _assert_artifacts_are_sentinel_free(paths: tuple[Path, ...], sentinel: str) -> None:
    marker = sentinel.encode("ascii")
    for path in paths:
        if marker in path.read_bytes():
            raise AssertionError("native proof artifact scan failed")


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_helper_adapter_ipc_and_complete_job_tree_cleanup(tmp_path: Path) -> None:
    sentinel = "native-" + "redaction-sentinel"
    _write_checkpoint(_CHECKPOINT_START)
    success_evidence = tmp_path / "success.json"
    success_marker = tmp_path / "success-descendant.attempted"
    with _OsStreamCapture(tmp_path, "success") as success_streams:
        success = CodexHelperExecutor(timeout_seconds=5.0).run(
            _runner("success", success_evidence, sentinel, success_marker)
        )
    _write_checkpoint(_CHECKPOINT_SUCCESS_EXECUTOR_RETURNED)
    assert success.state is ProviderState.SUCCESS
    assert success.outcome is ProviderOutcome.SNAPSHOT
    assert success.snapshot is not None
    assert success.snapshot.public_state is PublicProviderState.AVAILABLE
    assert success.snapshot.freshness is SnapshotFreshness.FRESH
    assert success.snapshot.source_id == "codex-app-server-v2"
    assert len(success.snapshot.windows) == 2
    assert success.snapshot.windows[0].limit is not None
    assert success.snapshot.windows[0].remaining is not None
    _assert_streams_clean(success_streams)
    success_record = _read_evidence(success_evidence)
    assert success_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(success_marker)
    _write_checkpoint(_CHECKPOINT_SUCCESS_VALIDATED)
    success_pids = [int(success_record[key]) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
    _assert_gone(success_pids)
    _write_checkpoint(_CHECKPOINT_SUCCESS_TREE_GONE)

    timeout_evidence = tmp_path / "timeout.json"
    timeout_marker = tmp_path / "timeout-descendant.attempted"
    result: dict[str, object] = {}
    with _OsStreamCapture(tmp_path, "timeout") as timeout_streams:
        worker = threading.Thread(
            target=lambda: result.setdefault(
                "view",
                CodexHelperExecutor(timeout_seconds=5.0).run(
                    _runner("timeout", timeout_evidence, sentinel, timeout_marker)
                ),
            ),
            daemon=True,
        )
        worker.start()
        timeout_record = _read_evidence(timeout_evidence)
        timeout_pids = [int(timeout_record[key]) for key in ("helper_pid", "fixture_pid", "descendant_pid")]
        assert all(_process_is_running(pid) for pid in timeout_pids)
        _write_checkpoint(_CHECKPOINT_TIMEOUT_TREE_OBSERVED)
        worker.join(10.0)
        assert not worker.is_alive()
        timeout_view = result["view"]
    _assert_streams_clean(timeout_streams)
    assert timeout_record["fixture_stderr_attempted"] is True
    _assert_descendant_output_attempted(timeout_marker)
    _write_checkpoint(_CHECKPOINT_TIMEOUT_VALIDATED)
    assert timeout_view.state is ProviderState.SAFE_ERROR
    assert timeout_view.error.code is SafeErrorCode.TIMEOUT
    assert timeout_view.outcome is ProviderOutcome.EXECUTION_ERROR
    assert timeout_view.snapshot is None
    _write_checkpoint(_CHECKPOINT_TIMEOUT_STATE_VALIDATED)
    _assert_gone(timeout_pids)
    _write_checkpoint(_CHECKPOINT_TIMEOUT_TREE_GONE)

    v2_executor = CodexHelperExecutor(timeout_seconds=5.0)
    v2_result = v2_executor.run_with_deadline(
        _runner("success", tmp_path / "v2-codex.json", "v2-proof", tmp_path / "v2-codex-descendant.attempted"),
        DeadlineContext.from_seconds(10.0),
    )
    assert v2_result.state is ProviderState.SUCCESS, f"v2 provider error: {v2_result.error.code.value if v2_result.error else 'none'}"
    assert v2_result.outcome is ProviderOutcome.SNAPSHOT
    assert v2_result.snapshot is not None
    assert v2_executor._pending_supervisor is None
    assert cleanup_complete([], helpers=(v2_executor,))

    artifact_path = os.environ.get("YASB_NATIVE_EVIDENCE_PATH")
    if artifact_path:
        artifact = {
            "native": True,
            "ready_authorized": bool(success_record["authorized"] and timeout_record["authorized"]),
            "tree_terminated": True,
            "bounded_timeout_error": timeout_view.error.code.value,
            "streams_clean": not (
                success_streams.stdout_bytes
                or success_streams.stderr_bytes
                or timeout_streams.stdout_bytes
                or timeout_streams.stderr_bytes
            ),
        }
        Path(artifact_path).write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    _assert_artifacts_are_sentinel_free(tuple(tmp_path.iterdir()), sentinel)
    _write_checkpoint(_CHECKPOINT_FINAL_SCAN_COMPLETE)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_v2_default_configuration_reads_localappdata() -> None:
    real_localappdata = os.environ.get("LOCALAPPDATA")
    if not real_localappdata:
        pytest.fail("Windows native proof requires LOCALAPPDATA")
    temp_localappdata = Path(tempfile.mkdtemp(prefix="yasb-limitora-r7-", dir=real_localappdata))
    config_path = temp_localappdata / "yasb-limitora" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"codex": {"enabled": False}, "opencode_go": {"enabled": False}}),
        encoding="utf-8",
    )
    stdout, stderr = io.BytesIO(), io.StringIO()
    try:
        assert main(
            ["--output-version", "2"],
            environment={"LOCALAPPDATA": str(temp_localappdata)},
            stdout=stdout,
            stderr=stderr,
        ) == 0
        assert json.loads(stdout.getvalue())["version"] == 2
        assert stderr.getvalue() == ""
        assert str(config_path) not in stdout.getvalue().decode() + stderr.getvalue()
    finally:
        shutil.rmtree(temp_localappdata, ignore_errors=True)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_global_guard_privilege_competition_and_provider_barrier(tmp_path: Path) -> None:
    # The real Global\ mutex acquisition is the runner privilege proof.
    script = """import sys, time
from pathlib import Path
from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_guard import GuardError, V2Guard
path = sys.argv[1]
sentinel = Path(sys.argv[3])
def provider():
    sentinel.write_text("PROVIDER_STARTED\\n", encoding="ascii")
try:
    lease = V2Guard().acquire(path, DeadlineContext.from_seconds(float(sys.argv[2])))
    print("owned", flush=True)
    provider()
    if len(sys.argv) > 4: time.sleep(30)
except GuardError as error:
    print(error.code, flush=True)
"""
    path = str(tmp_path / "guard.json")
    owner_sentinel = str(tmp_path / "owner-provider.sentinel")
    blocked_sentinel = str(tmp_path / "blocked-provider.sentinel")
    first = subprocess.Popen([sys.executable, "-c", script, path, "5", owner_sentinel, "hold"], stdout=subprocess.PIPE, text=True)
    try:
        assert first.stdout is not None and first.stdout.readline().strip() == "owned"
        provider_deadline = time.monotonic() + 5
        while not Path(owner_sentinel).exists() and time.monotonic() < provider_deadline:
            time.sleep(0.01)
        assert Path(owner_sentinel).read_text(encoding="ascii") == "PROVIDER_STARTED\n"
        blocked = subprocess.run([sys.executable, "-c", script, path, "1", blocked_sentinel], capture_output=True, text=True, timeout=5)
        assert blocked.stdout.strip() == "guard_wait_timeout"
        assert not Path(blocked_sentinel).exists()
        first.terminate()
        first.wait(timeout=5)
        abandoned_sentinel = str(tmp_path / "abandoned-provider.sentinel")
        abandoned = subprocess.run([sys.executable, "-c", script, path, "5", abandoned_sentinel], capture_output=True, text=True, timeout=5)
        assert abandoned.stdout.strip() == "owned"
        assert Path(abandoned_sentinel).read_text(encoding="ascii") == "PROVIDER_STARTED\n"
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_path_and_file_limits_reject_before_provider_open(tmp_path: Path) -> None:
    context = DeadlineContext.from_seconds(5)
    with pytest.raises(ValueError):
        canonicalize_v2_path(r"\\server\share\config.json")
    with pytest.raises(ValueError):
        canonicalize_v2_path(r"\\?\C:\config.json")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 16_385)
    with pytest.raises(V2FileError):
        read_v2_config(oversized, context)


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_native_release_fault_is_deterministic_and_sanitized() -> None:
    class Api:
        def CreateMutexW(self, *_): return 1
        def WaitForSingleObject(self, *_): return 0
        def ReleaseMutex(self, _): return False
        def CloseHandle(self, _): return True

    lease = V2Guard(api=Api(), sid_provider=lambda: b"native-test-sid").acquire(r"C:\native.json", DeadlineContext.from_seconds(1))
    assert lease.release() is False


def test_sentinel_scan_failure_diagnostics_are_redacted(tmp_path: Path) -> None:
    sentinel = "native-redaction-sentinel"
    unsafe = tmp_path / "unsafe-proof.txt"
    unsafe.write_bytes(sentinel.encode("ascii"))
    with pytest.raises(AssertionError) as error:
        _assert_artifacts_are_sentinel_free((unsafe,), sentinel)
    if sentinel in str(error.value):
        pytest.fail("sentinel escaped artifact-scan diagnostics")


def test_checkpoint_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "native-proof.checkpoint"
    for content, expected in ((b"1\n", "1"), (None, "unknown"), (b"arbitrary", "unknown")):
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)
        assert _classify_checkpoint(path) == expected
    monkeypatch.setenv(_CHECKPOINT_ENV, str(path))
    _write_checkpoint(_CHECKPOINT_START)
    _write_checkpoint(_CHECKPOINT_FINAL_SCAN_COMPLETE)
    assert path.read_bytes() == b"9\n"
    assert not path.with_name(f"{path.name}.tmp").exists()

    def fail_replace(source: str, target: str) -> None:
        raise OSError

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(AssertionError, match="native proof checkpoint unavailable"):
        _write_checkpoint(_CHECKPOINT_START)
    assert path.read_bytes() == b"9\n"
    assert not path.with_name(f"{path.name}.tmp").exists()


class _NestedJobApi:
    def create_job(self):
        return "job"

    def make_non_inheritable(self, handle):
        return True

    def enable_kill_on_close(self, handle):
        return True

    def open_process(self, pid, access):
        return "process"

    def is_process_in_job(self, process, job):
        return job is None

    def assign(self, job, process):
        raise AssertionError("nested containment must not authorize assignment")

    def query_active(self, job):
        return 0

    def terminate(self, job):
        return True

    def terminate_process(self, process):
        return True

    def wait(self, handle, timeout_ms):
        return WAIT_OBJECT_0

    def close(self, handle):
        return True


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_nested_job_is_explicit_safe_failure_without_authorization() -> None:
    boundary = WindowsJobBoundary(api=_NestedJobApi())
    with pytest.raises(JobError) as error:
        boundary.assign_process(1234)
    assert error.value.code is JobErrorCode.NESTED_JOB
    with pytest.raises(JobError):
        boundary.authorize()


@pytest.mark.skipif(os.name != "nt", reason="native Windows proof requires Windows")
def test_supervisor_setup_failure_is_safe_and_does_not_run_runner() -> None:
    calls: list[str] = []

    def fail_before_authorization(**kwargs):
        calls.append("setup")
        raise JobError(JobErrorCode.ASSIGNMENT_FAILED)

    view = CodexHelperExecutor(fail_before_authorization).run((sys.executable, str(_FIXTURE), "success", "unused"))
    assert calls == ["setup"]
    assert view.state is ProviderState.SAFE_ERROR
    assert view.error.code is SafeErrorCode.PROVIDER_ERROR


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or sys.argv[1] != "--classify-checkpoint":
            raise ValueError
        print(_classify_checkpoint(Path(sys.argv[2])))
    except Exception:
        raise SystemExit(1) from None
