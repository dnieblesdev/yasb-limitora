; S10 static installer contract. Build tooling must provide every input explicitly.
#ifndef AppVersion
#error AppVersion must be supplied with /DAppVersion
#endif
#ifndef SourceDir
#error SourceDir must be supplied with /DSourceDir
#endif
#ifndef OutputDir
#error OutputDir must be supplied with /DOutputDir
#endif

#define G1LifecycleMechanism "pre-install-evacuation"
#define G1PriorPayloadSuffix ".old"
#define G1FailedPayloadSuffix ".failed"
#define G1RegistrySnapshotSuffix ".reg"

[Setup]
AppId={{55D372A6-1DA5-41BE-B7AB-65CAB362E620}
AppName=yasb-limitora
AppVersion={#AppVersion}
AppVerName=yasb-limitora {#AppVersion}
AppPublisher=Gentle AI
AppPublisherURL=https://github.com/dnieb/yasb-limitora
AppSupportURL=https://github.com/dnieb/yasb-limitora/issues
DefaultDirName={autopf}\yasb-limitora
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=yasb-limitora-{#AppVersion}-setup
Uninstallable=yes
UninstallDisplayName=yasb-limitora
UninstallDisplayIcon={app}\yasb-limitora.exe
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "addtopath"; Description: "Add yasb-limitora to the user PATH (optional; not required for YASB)"; Flags: unchecked
Name: "envassist"; Description: "Allow the optional commented YASB environment assistance"; Flags: unchecked
Name: "configassist"; Description: "Allow the optional provider configuration wizard"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1"; ValueType: dword; ValueName: "NoModify"; ValueData: "1"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1"; ValueType: dword; ValueName: "NoRepair"; ValueData: "1"; Flags: uninsdeletevalue

[Code]
var
  AddToPathConsent: Boolean;
  EnvBlockConsent: Boolean;
  ConfigWizardConsent: Boolean;
  CleanupConsent: Boolean;

{ G1 contract: pre-install evacuation only.
  canonical -> .old before native copy/register.
  Evacuation is gated: an existing canonical directory is treated as the
  expected prior install only when the HKCU uninstall registry identity and
  the prior uninstaller on disk coherently point at that directory; otherwise
  setup aborts without touching the directory.
  On a post-bookkeeping failure, the exact new native uninstaller is the
  rollback correction; the complete prior registry key, snapshotted with its
  original value types by a bounded reg.exe export before evacuation, is
  re-advertised verbatim by reg.exe import only after the prior payload
  restoration is proven, so no failure path mixes identities.
  The rejected post-install rename is deliberately absent. }

{ Executable G1 hooks: PrepareToInstall gates, evacuates, and captures the
  prior bookkeeping; ssPostInstall commits by deleting .old; DeinitializeSetup
  restores an uncommitted evacuation with the exact new native uninstaller. }

const
  G1UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{55D372A6-1DA5-41BE-B7AB-65CAB362E620}_is1';

var
  EvacuatedOldDir: string;
  PriorRegistrySnapshot: string;
  PriorDisplayVersion: string;
  PriorUninstallString: string;
  PriorInstallLocation: string;

function HasCoherentPriorInstallOwnership(AppDir: string): Boolean;
var
  PriorUninstaller: string;
begin
  Result := False;
  if (PriorUninstallString = '') or (PriorInstallLocation = '') then
    Exit;
  if not SameText(RemoveBackslash(PriorInstallLocation), RemoveBackslash(AppDir)) then
    Exit;
  PriorUninstaller := RemoveQuotes(PriorUninstallString);
  if not SameText(RemoveBackslash(ExtractFilePath(PriorUninstaller)), RemoveBackslash(AppDir)) then
    Exit;
  Result := FileExists(PriorUninstaller);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppDir: string;
  OldDir: string;
  SnapshotPath: string;
  SnapshotOk: Boolean;
  ResultCode: Integer;
begin
  Result := '';
  NeedsRestart := False;
  AppDir := ExpandConstant('{app}');
  OldDir := AppDir + '{#G1PriorPayloadSuffix}';
  RegQueryStringValue(HKCU, G1UninstallKey, 'DisplayVersion', PriorDisplayVersion);
  RegQueryStringValue(HKCU, G1UninstallKey, 'UninstallString', PriorUninstallString);
  RegQueryStringValue(HKCU, G1UninstallKey, 'InstallLocation', PriorInstallLocation);
  if not DirExists(AppDir) then
    Exit;
  if DirExists(OldDir) then
  begin
    Result := 'Stale ' + OldDir + ' from an interrupted run; aborting with the prior install intact.';
    Exit;
  end;
  if not HasCoherentPriorInstallOwnership(AppDir) then
  begin
    Result := 'Existing ' + AppDir + ' lacks coherent prior-install ownership evidence; aborting with the directory untouched.';
    Exit;
  end;
  { Snapshot the complete prior HKCU registration, with original value types,
    before any canonical byte moves; export failure is fail-closed. }
  SnapshotPath := OldDir + '{#G1RegistrySnapshotSuffix}';
  SnapshotOk := Exec('reg.exe', 'export "HKCU\' + G1UninstallKey + '" "' + SnapshotPath + '" /y',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if (not SnapshotOk) or (ResultCode <> 0) then
  begin
    if FileExists(SnapshotPath) then
      DeleteFile(SnapshotPath);
    Result := 'Prior-registry snapshot export failed (code ' + IntToStr(ResultCode) + '); aborting with the prior install intact.';
    Exit;
  end;
  if RenameFile(AppDir, OldDir) then
  begin
    EvacuatedOldDir := OldDir;
    PriorRegistrySnapshot := SnapshotPath;
  end
  else
  begin
    DeleteFile(SnapshotPath);
    Result := 'Pre-install evacuation of ' + AppDir + ' failed; aborting with the prior install intact.';
  end;
end;

procedure RestoreEvacuatedPriorInstall;
var
  AppDir: string;
  FailedDir: string;
  NewUninstallString: string;
  ResultCode: Integer;
  UninstallerRan: Boolean;
begin
  AppDir := ExpandConstant('{app}');
  FailedDir := AppDir + '{#G1FailedPayloadSuffix}';
  { Step 1: run the exact new native uninstaller; its result is checked, not ignored. }
  if RegQueryStringValue(HKCU, G1UninstallKey, 'UninstallString', NewUninstallString)
     and (NewUninstallString <> '') and (NewUninstallString <> PriorUninstallString) then
  begin
    UninstallerRan := Exec(RemoveQuotes(NewUninstallString), '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
      ExtractFilePath(RemoveQuotes(NewUninstallString)), SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if (not UninstallerRan) or (ResultCode <> 0) then
      Log('G1 rollback: new native uninstaller did not run cleanly (code ' + IntToStr(ResultCode) + '); continuing filesystem rollback.');
  end;
  { Step 2: quarantine any residual new payload before touching prior payload or prior registry. }
  if DirExists(FailedDir) then
    DelTree(FailedDir, True, True, True);
  if DirExists(AppDir) and not RenameFile(AppDir, FailedDir) then
  begin
    Log('G1 rollback: quarantine of the new payload failed; registry left matching the canonical new payload; prior payload recoverable at ' + EvacuatedOldDir + '.');
    Exit;
  end;
  { Step 3: restore the prior payload; the prior registry may follow only a proven restoration. }
  if not RenameFile(EvacuatedOldDir, AppDir) then
  begin
    if DirExists(FailedDir) then
      RenameFile(FailedDir, AppDir);
    Log('G1 rollback: prior payload restoration failed; prior payload remains at ' + EvacuatedOldDir + '; prior registry not re-advertised.');
    Exit;
  end;
  EvacuatedOldDir := '';
  { Step 4: the prior payload is canonical again, so re-advertise the complete
    prior registration verbatim (all values, original types) by importing the
    pre-evacuation snapshot; import failure never advertises success and keeps
    the recovery bytes for manual restoration. }
  if (PriorUninstallString <> '') and (PriorRegistrySnapshot <> '') then
  begin
    if Exec('reg.exe', 'import "' + PriorRegistrySnapshot + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
       and (ResultCode = 0) then
    begin
      DeleteFile(PriorRegistrySnapshot);
      PriorRegistrySnapshot := '';
      Log('G1 rollback: complete prior registry key re-advertised from the snapshot import.');
    end
    else
      Log('G1 rollback: snapshot import failed (code ' + IntToStr(ResultCode) + '); prior registry not re-advertised; recovery bytes retained at ' + PriorRegistrySnapshot + '.');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (EvacuatedOldDir <> '') then
  begin
    DelTree(EvacuatedOldDir, True, True, True);
    if PriorRegistrySnapshot <> '' then
    begin
      DeleteFile(PriorRegistrySnapshot);
      PriorRegistrySnapshot := '';
    end;
    EvacuatedOldDir := '';
  end;
end;

procedure DeinitializeSetup;
begin
  if EvacuatedOldDir <> '' then
    RestoreEvacuatedPriorInstall;
end;

procedure InitializeWizard;
begin
  AddToPathConsent := False;
  EnvBlockConsent := False;
  ConfigWizardConsent := False;
  CleanupConsent := False;
end;

function CaptureInstallConsent: Boolean;
begin
  AddToPathConsent := WizardIsTaskSelected('addtopath');
  EnvBlockConsent := WizardIsTaskSelected('envassist');
  ConfigWizardConsent := WizardIsTaskSelected('configassist');
  Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectTasks then
    Result := CaptureInstallConsent;
end;

function ConfirmStateCleanup: Boolean;
var
  Choice: Integer;
begin
  Choice := MsgBox(
    'Remove the mutable configuration, cache, and backups in ' +
      ExpandConstant('{localappdata}\yasb-limitora') + '?',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
  Result := Choice = IDYES;
end;

function InitializeUninstall: Boolean;
begin
  CleanupConsent := ConfirmStateCleanup;
  Result := True;
end;

function PromptManualClose: Boolean;
var
  Choice: Integer;
begin
  Choice := MsgBox(
    'YASB is currently running. Close YASB manually, then choose Retry. ' +
      'yasb-limitora will never close, restart, or manage YASB for you.',
    mbConfirmation, MB_RETRYCANCEL);
  Result := Choice = IDRETRY;
  if Choice = IDCANCEL then
    Result := False;
end;

function ManualCloseGate(DetectedRunning: Boolean): Boolean;
begin
  Result := True;
  if DetectedRunning then
    Result := PromptManualClose;
end;
