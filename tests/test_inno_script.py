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


def test_exec_is_reserved_for_rollback_uninstaller_and_registry_snapshot() -> None:
    code = code_section(script_text())
    assert code.count("Exec(") == 4
    assert code.count("ewWaitUntilTerminated, ResultCode") == 4
    exec_lines = " ".join(line for line in code.splitlines() if "Exec(" in line)
    assert "NewUninstallString" in exec_lines
    assert exec_lines.count("'reg.exe'") == 2
    # the single added Exec is the read-only running-probe redirect via {cmd}
    assert exec_lines.count("ExpandConstant('{cmd}')") == 1
    assert "tasklist /FO CSV /NH" in exec_lines
    assert "VERYSILENT" in code
    # every reg.exe Exec is fail-closed on both the launch flag and the exit code
    assert "(not SnapshotOk) or (ResultCode <> 0)" in code
    assert re.search(r"if Exec\('reg\.exe', 'import.*\n\s*and \(ResultCode = 0\)", code)


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
    # the three identity values are still read for the ownership gate
    for value in ("'DisplayVersion'", "'UninstallString'", "'InstallLocation'"):
        assert f"RegQueryStringValue(HKCU, G1UninstallKey, {value}" in code
    # the complete prior key is restored from the snapshot; string-typed
    # per-value rewrites (which lose original registry types) are gone
    assert "RegWriteStringValue" not in code
    assert "Exec('reg.exe', 'import \"' + PriorRegistrySnapshot" in code


def prepare_procedure(code: str) -> str:
    """Slice of [Code] covering only PrepareToInstall."""
    return code.split("function PrepareToInstall", 1)[1].split(
        "procedure RestoreEvacuatedPriorInstall", 1
    )[0]


def test_complete_prior_registry_snapshot_is_exported_before_evacuation() -> None:
    text = script_text()
    assert '#define G1RegistrySnapshotSuffix ".reg"' in text
    code = code_section(text)
    assert "PriorRegistrySnapshot: string;" in code
    prepare = prepare_procedure(code)
    export = prepare.index(
        "SnapshotOk := Exec('reg.exe', 'export \"HKCU\\' + G1UninstallKey"
    )
    rename = prepare.index("RenameFile(AppDir, OldDir)")
    assert export < rename
    assert "'{#G1RegistrySnapshotSuffix}'" in prepare
    # fail-closed: launch flag and exit code are checked, and the abort
    # happens before any canonical byte moves
    abort_branch = prepare[export:rename]
    assert "(not SnapshotOk) or (ResultCode <> 0)" in abort_branch
    assert "aborting with the prior install intact" in abort_branch
    assert "DeleteFile(SnapshotPath)" in abort_branch
    # the snapshot path is bound only after the evacuation rename succeeds
    assert prepare.index("PriorRegistrySnapshot := SnapshotPath") > rename


def test_registry_restore_is_verbatim_import_fail_closed_and_keeps_recovery_bytes() -> None:
    restore = restore_procedure(code_section(script_text()))
    imported = restore.index("Exec('reg.exe', 'import")
    assert "and (ResultCode = 0)" in restore[imported:]
    # the snapshot is deleted only after the checked successful import
    assert imported < restore.index("DeleteFile(PriorRegistrySnapshot)")
    # the failure path logs without advertising success and retains the snapshot
    failure_log = restore[restore.index("snapshot import failed") :]
    assert "prior registry not re-advertised" in failure_log
    assert "recovery bytes retained at" in failure_log
    assert "DeleteFile" not in failure_log


def test_old_payload_is_deleted_only_after_a_successful_install() -> None:
    code = code_section(script_text())
    assert "procedure CurStepChanged(CurStep: TSetupStep);" in code
    assert "CurStep = ssPostInstall" in code
    commit = code.split("procedure CurStepChanged", 1)[1].split(
        "procedure DeinitializeSetup", 1
    )[0]
    assert "DelTree(EvacuatedOldDir" in commit
    # the registry snapshot is cleaned only on the same successful commit
    assert "DeleteFile(PriorRegistrySnapshot)" in commit


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


def test_rollback_waits_bounded_for_uninstaller_cleanup_before_quarantine() -> None:
    text = script_text()
    assert '#define G1UninstallCleanupBudgetMs 30000' in text
    assert '#define G1UninstallCleanupPollMs 250' in text
    restore = restore_procedure(code_section(text))
    uninstaller = restore.index("Exec(RemoveQuotes(NewUninstallString)")
    wait = restore.index("WaitedMs := 0")
    step2 = restore.index("{ Step 2:")
    quarantine = restore.index("RenameFile(AppDir, FailedDir)")
    assert uninstaller < wait < step2 < quarantine
    # the wait runs only when the checked uninstaller returned cleanly
    assert "if UninstallerRan and (ResultCode = 0) then" in restore[uninstaller:wait]
    wait_block = restore[wait:step2]
    assert "while DirExists(AppDir) and (WaitedMs < {#G1UninstallCleanupBudgetMs}) do" in wait_block
    assert "Sleep({#G1UninstallCleanupPollMs})" in wait_block
    assert "WaitedMs := WaitedMs + {#G1UninstallCleanupPollMs}" in wait_block
    # fail closed: exhausted budget aborts before any quarantine or restoration
    assert "did not complete within the bounded wait" in wait_block
    assert "prior payload recoverable at " in wait_block
    assert "prior registry not re-advertised" in wait_block
    assert "Exit;" in wait_block
    assert "RenameFile" not in wait_block and "DelTree" not in wait_block


def test_manual_close_gate_precedes_registry_capture_and_evacuation() -> None:
    prepare = prepare_procedure(code_section(script_text()))
    gate = prepare.index("if not ManualCloseGate(YasbDetectedRunning) then")
    assert gate < prepare.index("RegQueryStringValue(HKCU, G1UninstallKey, 'DisplayVersion'")
    assert gate < prepare.index("Exec('reg.exe', 'export")
    assert gate < prepare.index("RenameFile(AppDir, OldDir)")
    abort = prepare[gate:prepare.index("RegQueryStringValue")]
    assert "aborting with the prior install intact" in abort and "Exit;" in abort


def test_manual_close_gate_wires_uninstall_and_retry_reprobes() -> None:
    code = code_section(script_text())
    assert "function YasbDetectedRunning: Boolean; forward;" in code
    assert "function ManualCloseGate(DetectedRunning: Boolean): Boolean; forward;" in code
    uninstall = code.split("function InitializeUninstall: Boolean;", 1)[1].split("\nend;", 1)[0]
    gate = uninstall.index("if not ManualCloseGate(YasbDetectedRunning) then")
    consent = uninstall.index("CleanupConsent := ConfirmStateCleanup")
    assert gate < consent
    assert "Result := False" in uninstall[gate:consent] and "Exit;" in uninstall[gate:consent]
    body = code.rsplit("function ManualCloseGate(DetectedRunning: Boolean): Boolean;", 1)[1].split("\nend;", 1)[0]
    assert "while DetectedRunning do" in body
    assert "DetectedRunning := YasbDetectedRunning" in body
    assert "Result := False" in body


def test_running_probe_is_read_only_exact_name_and_fail_closed() -> None:
    code = code_section(script_text())
    probe = code.rsplit("function YasbDetectedRunning: Boolean;", 1)[1].split("\nend;", 1)[0]
    assert "tasklist /FO CSV /NH" in probe
    assert "'\"yasb.exe\"'" in probe and "'\"yasb-limitora.exe\"'" in probe
    assert "Lowercase(" in probe
    # fail closed: an inconclusive probe reports running so the gate asks the user
    assert probe.index("Result := True") < probe.index("Result := (Pos(")
    lowered = probe.lower()
    for forbidden in ("taskkill", "terminateprocess", "closemainwindow", "/kill"):
        assert forbidden not in lowered


def test_post_install_cleanup_is_checked_and_failure_preserves_recovery_state() -> None:
    code = code_section(script_text())
    commit = code.split("procedure CurStepChanged(CurStep: TSetupStep);", 1)[1].split("procedure DeinitializeSetup", 1)[0]
    deltree = commit.index("if not DelTree(EvacuatedOldDir, True, True, True) then")
    log = commit.index("Log('G1 commit:")
    snapshot_delete = commit.index("DeleteFile(PriorRegistrySnapshot)")
    clear = commit.index("EvacuatedOldDir := ''")
    assert deltree < log < snapshot_delete < clear
    failure = commit[deltree:snapshot_delete]
    # handler-only Exit cannot fail setup (verified sha256:b5e35a1b…); the fatal
    # RaiseException must precede any snapshot deletion or state clearing.
    assert "Exit;" not in failure and "preserved" in failure
    assert deltree + failure.index("RaiseException(") < snapshot_delete
    assert "PriorRegistrySnapshot := ''" not in failure
    assert "EvacuatedOldDir := ''" not in failure and "DeleteFile" not in failure


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
    registry_import = restore.index("Exec('reg.exe', 'import")
    # Coherent order: quarantine new payload -> restore prior payload -> prior registry.
    assert quarantine < payload_back < registry_import
    # Every filesystem failure path exits before any prior-registry advertisement.
    failure_exits = [m.start() for m in re.finditer(r"\bExit;", restore)]
    assert len(failure_exits) >= 2
    assert all(position < registry_import for position in failure_exits)
    # Failed quarantine must not leave .old renamed away from recovery.
    quarantine_failure = restore[quarantine:payload_back]
    assert "Exit;" in quarantine_failure and "Log(" in quarantine_failure
    assert "RenameFile(EvacuatedOldDir" not in quarantine_failure


def test_stale_failed_payload_is_detected_and_preserved_before_transaction() -> None:
    prepare = prepare_procedure(code_section(script_text()))
    assert "FailedDir := AppDir + '{#G1FailedPayloadSuffix}'" in prepare
    stale_gate = prepare.index("if DirExists(FailedDir) then")
    export = prepare.index("Exec('reg.exe', 'export")
    rename = prepare.index("RenameFile(AppDir, OldDir)")
    # Fail-closed: the stale-.failed abort precedes any snapshot export or evacuation.
    assert stale_gate < export < rename
    abort = prepare[stale_gate:export]
    assert "interrupted recovery" in abort
    assert "aborting with the prior install intact" in abort
    assert "Exit;" in abort
    # Detect-and-preserve: preparation never deletes or renames a .failed sibling.
    assert "DelTree" not in prepare
    assert "DeleteFile(FailedDir" not in prepare
    assert "RenameFile(FailedDir" not in prepare


def test_rollback_failed_quarantine_is_owned_by_the_current_transaction() -> None:
    code = code_section(script_text())
    assert re.search(r"\bFailedQuarantineOwned\s*:\s*Boolean", code)
    restore = restore_procedure(code)
    # The single .failed deletion is guarded by current-transaction ownership.
    assert restore.count("DelTree(FailedDir") == 1
    deltree = restore.index("DelTree(FailedDir")
    deltree_guard = restore.rindex("if", 0, deltree)
    assert "FailedQuarantineOwned" in restore[deltree_guard:deltree]
    # Ownership is claimed only after this transaction's quarantine rename succeeds,
    # so the current-transaction rollback still quarantines the failed new tree.
    assert restore.index("FailedQuarantineOwned := True") > restore.index(
        "RenameFile(AppDir, FailedDir)"
    )
    # The step-3 rename-back of the quarantined payload uses the same ownership guard.
    back = restore.index("RenameFile(FailedDir, AppDir)")
    back_guard = restore.rindex("if", 0, back)
    assert "FailedQuarantineOwned" in restore[back_guard:back]


def test_s10_surface_keeps_forbidden_payloads_out_of_installer_script() -> None:
    text = script_text().lower()
    assert "targetpath" not in text
    assert "portable zip" not in text
    assert "yaml" not in text
    assert "css" not in text
    assert "secret" not in text


ASSISTANT_INCLUDE = ROOT / "packaging" / "inno" / "SetupAssistant.isi"


def setup_assistant_text() -> str:
    assert ASSISTANT_INCLUDE.is_file(), "S11 requires packaging/inno/SetupAssistant.isi"
    return ASSISTANT_INCLUDE.read_text(encoding="utf-8")


def test_s11_includes_setup_assistant_and_uses_nonce_only_transport() -> None:
    text = script_text()
    assistant = setup_assistant_text()
    assert re.search(r"(?mi)^\s*#include\s+[\"<]SetupAssistant\.isi[\">]", text)
    assert "_YASB_SETUP_ASSIST_NONCE" in assistant
    assert "--__yasb-limitora-setup-assist" in assistant
    assert "request.json" in assistant and "result.json" in assistant
    assert re.search(r"['\"]\{localappdata\}['\"]", assistant)
    assert "\\Temp\\yasb-limitora-setup-assist\\" in assistant
    assert "Length(Nonce) = 32" in assistant
    assert "C >= 'a'" in assistant and "C <= 'f'" in assistant
    assert "{localappdata}\\yasb-limitora" not in assistant


def test_s11_run_invocation_has_no_request_or_target_path_argument() -> None:
    assistant = setup_assistant_text()
    run = assistant.split("function YasbSetupAssistRun", 1)[1].split(
        "procedure InvokePostCommitAssist", 1
    )[0]
    assert "YasbSetupAssistSwitch = '--__yasb-limitora-setup-assist'" in assistant
    assert "YasbSetupAssistNonceEnvironment = '_YASB_SETUP_ASSIST_NONCE'" in assistant
    nonce_set = run.index("SetEnvironmentVariableW(YasbSetupAssistNonceEnvironment, Nonce);")

    invocation = re.search(
        r"(?s)Exec\(\s*AssistantExe,\s*YasbSetupAssistSwitch,\s*''\s*,\s*"
        r"SW_HIDE,\s*ewWaitUntilTerminated,\s*ExitCode\s*\)",
        run,
    )
    assert invocation is not None
    assert nonce_set < invocation.start()
    invocation_text = invocation.group(0).lower()
    assert "request" not in invocation_text
    assert "target" not in invocation_text
    assert "path" not in invocation_text


def test_s11_request_is_schema_v1_and_operations_choices_only() -> None:
    assistant = setup_assistant_text()
    assert re.search(
        r"['\"]gentle-ai\.yasb-limitora\.setup-assist-request/v1['\"]",
        assistant,
    )
    assert re.search(
        r"['\"]gentle-ai\.yasb-limitora\.setup-assist-result/v1['\"]",
        assistant,
    )
    assert re.search(r"(?m)request.*schema", assistant, re.IGNORECASE)
    assert re.search(r"(?m)operations.*(?:choice|consent)", assistant, re.IGNORECASE)
    assert "target_path" not in assistant and "target-path" not in assistant
    assert "target" not in re.sub(r"(?i)target[a-z_-]*", "", assistant)


def test_s11_result_read_is_bounded_regular_schema_valid_before_exact_cleanup() -> None:
    assistant = setup_assistant_text()
    run = assistant.split("function YasbSetupAssistRun", 1)[1].split(
        "procedure InvokePostCommitAssist", 1
    )[0]
    assert "FileExists(ResultFile)" in run
    assert re.search(r"64\s*\*\s*1024|65536|MaxResultBytes", run)
    validator = assistant.split("function YasbSetupAssistValidateResult", 1)[1].split(
        "function YasbSetupAssistResultState", 1
    )[0]
    assert "YasbSetupAssistResultSchema" in validator
    validation = run[run.index("if not YasbSetupAssistValidateResult"):]
    assert "result.json did not satisfy schema v1" in validation
    assert run.index("YasbSetupAssistValidateResult") < run.index(
        "YasbSetupAssistCleanup(Root)"
    )

    cleanup = assistant.split("procedure YasbSetupAssistCleanup", 1)[1].split(
        "procedure YasbSetupAssistCleanupState", 1
    )[0]
    assert "if Root = ''" in cleanup
    assert "DeleteFile(YasbSetupAssistRequestFile(Root));" in cleanup
    assert "DeleteFile(YasbSetupAssistResultFile(Root));" in cleanup
    assert "RemoveDir(Root);" in cleanup


def test_s11_install_assist_runs_after_commit_and_is_nonfatal() -> None:
    code = code_section(script_text()) + "\n" + setup_assistant_text()
    commit = code.index("CurStep = ssPostInstall")
    assist = code.index("InvokePostCommitAssist", commit)
    assert commit < assist
    assistant = setup_assistant_text()
    assist_slice = assistant.split("function YasbSetupAssistRun", 1)[1].split(
        "procedure InvokeUninstallAssist", 1
    )[0]
    assert "Exec(" in assist_slice
    assert "Log(" in assist_slice
    assert "RaiseException" not in assist_slice


def test_s11_uninstall_dispatches_state_cleanup_only_for_literal_yes() -> None:
    code = code_section(script_text())
    assistant = setup_assistant_text()
    assert "InitializeUninstall" in code
    uninstall = assistant.split("procedure InvokeUninstallAssist", 1)[1]
    assert "'[\"state-cleanup\"]'" in uninstall
    assert "'[\"YES\"]'" in uninstall
    assert uninstall.count("YasbSetupAssistRun(") == 1
    assert re.search(
        r"(?is)if\s+CleanupConsent\s+then.*?YasbSetupAssistRun\(.*?"
        r"'\[\"state-cleanup\"\]',\s*'\[\"YES\"\]'",
        uninstall,
    )
