"""Static contract tests for the bounded S10 Inno Setup surface."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "inno" / "yasb-limitora.iss"


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def setup_section(text: str) -> str:
    match = re.search(r"(?ms)^\[Setup\]\s*(.*?)(?=^\[|\Z)", text)
    assert match is not None
    return match.group(1)


def code_section(text: str) -> str:
    match = re.search(r"(?ms)^\[Code\]\s*(.*?)(?=^\[|\Z)", text)
    assert match is not None
    return match.group(1)


def test_script_fails_closed_when_build_defines_are_missing() -> None:
    text = script_text()
    assert "#ifndef AppVersion" in text
    assert "#ifndef SourceDir" in text
    assert "#ifndef OutputDir" in text
    assert text.count("#error") >= 3


def test_per_user_x64_identity_and_fixed_appid() -> None:
    setup = setup_section(script_text())
    assert re.search(r"(?m)^PrivilegesRequired\s*=\s*lowest\s*$", setup)
    assert re.search(r"(?m)^ArchitecturesAllowed\s*=\s*x64compatible\s*$", setup)
    assert re.search(r"(?m)^ArchitecturesInstallIn64BitMode\s*=\s*x64compatible\s*$", setup)
    assert "PrivilegesRequiredOverridesAllowed" not in setup
    assert "AppId={{55D372A6-1DA5-41BE-B7AB-65CAB362E620}" in setup
    assert re.search(r"(?m)^DefaultDirName\s*=\s*\{autopf\}\\yasb-limitora\s*$", setup)
    assert "HKLM" not in script_text()


def test_version_and_single_setup_filename_contract() -> None:
    setup = setup_section(script_text())
    assert "AppVersion={#AppVersion}" in setup
    assert "AppVerName=yasb-limitora {#AppVersion}" in setup
    assert "OutputBaseFilename=yasb-limitora-{#AppVersion}-setup" in setup
    assert len(re.findall(r"(?m)^OutputBaseFilename\s*=", setup)) == 1
    assert "NoRepair=1" not in setup
    assert "NoModify=1" not in setup


def test_no_modify_no_repair_are_hkcu_registry_values() -> None:
    text = script_text()
    registry = re.search(r"(?ms)^\[Registry\]\s*(.*?)(?=^\[|\Z)", text)
    assert registry is not None
    entries = registry.group(1)
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1"
    for name in ("NoModify", "NoRepair"):
        line = next((ln for ln in entries.splitlines() if f'ValueName: "{name}"' in ln), None)
        assert line is not None
        assert "Root: HKCU" in line
        assert subkey in line
        assert 'ValueType: dword' in line and 'ValueData: "1"' in line


def test_optional_user_path_task_is_unchecked_and_not_required_for_yasb() -> None:
    text = script_text()
    tasks = re.search(r"(?ms)^\[Tasks\]\s*(.*?)(?=^\[|\Z)", text)
    assert tasks is not None
    addtopath = re.search(r'(?m)^Name:\s*"addtopath";.*$', tasks.group(1))
    assert addtopath is not None
    assert re.search(r"Flags:\s*unchecked", addtopath.group(0), re.IGNORECASE)
    assert "not required for YASB" in addtopath.group(0)


def test_g1_selected_lifecycle_is_pre_install_evacuation_only() -> None:
    text = script_text()
    assert "pre-install evacuation" in text
    assert "canonical -> .old before native copy/register" in text
    assert "exact new native uninstaller" in text
    assert "prior registry" in text and "prior payload" in text
    assert ".new -> canonical" not in text
    assert '#define G1LifecycleMechanism "pre-install-evacuation"' in text


def test_consent_booleans_and_default_negative_cleanup() -> None:
    text = script_text()
    code = code_section(text)
    for name in ("AddToPathConsent", "EnvBlockConsent", "ConfigWizardConsent", "CleanupConsent"):
        assert re.search(rf"\b{name}\s*:\s*Boolean", code)
    assert "WizardIsTaskSelected('addtopath')" in code
    assert "WizardIsTaskSelected('envassist')" in code
    assert "WizardIsTaskSelected('configassist')" in code
    assert "ExpandConstant('{localappdata}\\yasb-limitora')" in code
    assert "MB_YESNO or MB_DEFBUTTON2" in code
    assert "= IDYES" in code
    assert "InitializeUninstall" in code


def test_manual_close_retry_cancel_has_no_process_control() -> None:
    text = script_text()
    code = code_section(text)
    assert "YASB is currently running" in code
    assert "MB_RETRYCANCEL" in code
    assert "= IDRETRY" in code
    assert "= IDCANCEL" in code
    for forbidden in ("TerminateProcess", "CloseMainWindow", "CreateProcess", "ShellExecute", "taskkill"):
        assert forbidden not in code


def test_exec_is_reserved_for_the_native_uninstaller_rollback() -> None:
    code = code_section(script_text())
    assert code.count("Exec(") == 1
    call = next(line for line in code.splitlines() if "Exec(" in line)
    assert "NewUninstallString" in call
    assert "VERYSILENT" in code


def test_pre_install_evacuation_is_executable_before_copy() -> None:
    code = code_section(script_text())
    assert "function PrepareToInstall(var NeedsRestart: Boolean): String;" in code
    assert "RenameFile(AppDir, OldDir)" in code
    assert "'{#G1PriorPayloadSuffix}'" in code
    assert code.count("prior install intact") >= 2


def test_failed_upgrade_restores_prior_registry_and_payload() -> None:
    code = code_section(script_text())
    assert "procedure DeinitializeSetup;" in code
    assert "RestoreEvacuatedPriorInstall" in code
    assert "'{#G1FailedPayloadSuffix}'" in code
    for value in ("'DisplayVersion'", "'UninstallString'", "'InstallLocation'"):
        assert f"RegQueryStringValue(HKCU, G1UninstallKey, {value}" in code
        assert f"RegWriteStringValue(HKCU, G1UninstallKey, {value}" in code


def test_old_payload_is_deleted_only_after_a_successful_install() -> None:
    code = code_section(script_text())
    assert "procedure CurStepChanged(CurStep: TSetupStep);" in code
    assert "CurStep = ssPostInstall" in code
    assert "DelTree(EvacuatedOldDir" in code


def restore_procedure(code: str) -> str:
    """Slice of [Code] covering only RestoreEvacuatedPriorInstall."""
    return code.split("procedure RestoreEvacuatedPriorInstall", 1)[1].split("procedure CurStepChanged", 1)[0]


def test_foreign_install_root_is_never_evacuated_without_ownership_evidence() -> None:
    code = code_section(script_text())
    prepare = code.split("procedure RestoreEvacuatedPriorInstall", 1)[0]
    assert "HasCoherentPriorInstallOwnership" in prepare
    # The ownership gate must run strictly before any evacuation rename.
    gate = prepare.index("not HasCoherentPriorInstallOwnership(AppDir)")
    rename = prepare.index("RenameFile(AppDir, OldDir)")
    assert gate < rename
    # Incoherent ownership aborts without touching the existing directory.
    abort_message = prepare[gate:rename]
    assert "untouched" in abort_message
    # Ownership evidence requires registry + filesystem agreement on the same root.
    gate_body = prepare.split("function HasCoherentPriorInstallOwnership", 1)[1]
    assert "SameText(" in gate_body
    assert "RemoveBackslash(" in gate_body
    assert "FileExists(" in gate_body
    assert "PriorInstallLocation" in gate_body and "PriorUninstallString" in gate_body


def test_rollback_does_not_ignore_new_uninstaller_result() -> None:
    restore = restore_procedure(code_section(script_text()))
    exec_line = next(line for line in restore.splitlines() if "Exec(" in line)
    # The Exec result is captured, and the exit code is checked and reported.
    assert re.search(r"\w+\s*:=\s*Exec\(", exec_line)
    assert re.search(r"ResultCode\s*<>\s*0", restore)
    assert "Log(" in restore


def test_rollback_restores_payload_before_registry_and_never_mixes_identities() -> None:
    restore = restore_procedure(code_section(script_text()))
    quarantine = restore.index("RenameFile(AppDir, FailedDir)")
    payload_back = restore.index("RenameFile(EvacuatedOldDir, AppDir)")
    first_registry_write = restore.index("RegWriteStringValue")
    # Coherent order: quarantine new payload -> restore prior payload -> prior registry.
    assert quarantine < payload_back < first_registry_write
    # Every filesystem failure path exits before any prior-registry advertisement.
    failure_exits = [m.start() for m in re.finditer(r"\bExit;", restore)]
    assert len(failure_exits) >= 2
    assert all(position < first_registry_write for position in failure_exits)
    # Failed quarantine must not leave .old renamed away from recovery.
    quarantine_failure = restore[quarantine:payload_back]
    assert "Exit;" in quarantine_failure and "Log(" in quarantine_failure
    assert "RenameFile(EvacuatedOldDir" not in quarantine_failure


def test_s10_does_not_add_assistance_transport_or_forbidden_payloads() -> None:
    text = script_text().lower()
    assert "request.json" not in text
    assert "targetpath" not in text
    assert "parameters=" not in text
    assert "portable zip" not in text
    assert "yaml" not in text
    assert "css" not in text
    assert "secret" not in text


def test_static_slice_does_not_invoke_assistance() -> None:
    code = code_section(script_text())
    assert "assistance" not in code.lower()
    assert "setup-assist" not in code.lower()
    assert "[run]" not in script_text().lower()
    assert "Filename:" not in script_text()
