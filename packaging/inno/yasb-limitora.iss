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
#define G1UninstallCleanupBudgetMs 30000
#define G1UninstallCleanupPollMs 250

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
#include "SetupAssistant.isi"

var
  AddToPathConsent: Boolean;
  EnvBlockConsent: Boolean;
  ConfigWizardConsent: Boolean;
  CleanupConsent: Boolean;
  CodexChoice: Integer;
  OpencodeChoice: Integer;
  CodexRunnerPath: String;
  ProviderPage: TInputFileWizardPage;
  CodexCombo: TNewComboBox;
  OpencodeCombo: TNewComboBox;
  RunnerInputIdx: Integer;

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
  FailedQuarantineOwned: Boolean;

{ R4-001: the manual-close gate and its read-only running probe are defined at
  the bottom of this section; forward declarations let the hooks above call them. }
function YasbDetectedRunning: Boolean; forward;
function ManualCloseGate(DetectedRunning: Boolean): Boolean; forward;

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

function HasOwnedNewUninstaller(AppDir, UninstallString: string): Boolean;
var
  Candidate: string;
begin
  Result := False;
  Candidate := RemoveQuotes(UninstallString);
  if Candidate = '' then
    Exit;
  if not SameText(RemoveBackslash(ExtractFilePath(Candidate)), RemoveBackslash(AppDir)) then
    Exit;
  Result := FileExists(Candidate);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppDir: string;
  OldDir: string;
  FailedDir: string;
  SnapshotPath: string;
  SnapshotOk: Boolean;
  ResultCode: Integer;
begin
  Result := '';
  NeedsRestart := False;
  AppDir := ExpandConstant('{app}');
  OldDir := AppDir + '{#G1PriorPayloadSuffix}';
  { R4-001: the manual-close gate runs before any registry capture or
    canonical-directory evacuation; the user alone closes processes and Cancel aborts. }
  if not ManualCloseGate(YasbDetectedRunning) then
  begin
    Result := 'Operator cancelled the YASB manual-close gate; aborting with the prior install intact.';
    Exit;
  end;
  RegQueryStringValue(HKCU, G1UninstallKey, 'DisplayVersion', PriorDisplayVersion);
  RegQueryStringValue(HKCU, G1UninstallKey, 'UninstallString', PriorUninstallString);
  RegQueryStringValue(HKCU, G1UninstallKey, 'InstallLocation', PriorInstallLocation);
  FailedDir := AppDir + '{#G1FailedPayloadSuffix}';
  if DirExists(FailedDir) then
  begin
    Result := 'Stale ' + FailedDir + ' from an interrupted recovery; aborting with the prior install intact.';
    Exit;
  end;
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
  WaitedMs: Integer;
begin
  AppDir := ExpandConstant('{app}');
  FailedDir := AppDir + '{#G1FailedPayloadSuffix}';
  { Step 1: run the exact new native uninstaller; its result is checked, not ignored.
    Ownership is path-bound to this transaction's canonical app directory, not to
    textual inequality with the prior string (same-path upgrades are valid). }
  if RegQueryStringValue(HKCU, G1UninstallKey, 'UninstallString', NewUninstallString)
     and HasOwnedNewUninstaller(AppDir, NewUninstallString) then
  begin
    UninstallerRan := Exec(RemoveQuotes(NewUninstallString), '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
      ExtractFilePath(RemoveQuotes(NewUninstallString)), SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if (not UninstallerRan) or (ResultCode <> 0) then
      Log('G1 rollback: new native uninstaller did not run cleanly (code ' + IntToStr(ResultCode) + '); continuing filesystem rollback.');
  end;
  { Step 1b (R3): the checked launcher can return while its second-phase copy is
    still deleting the canonical tree; wait bounded for cleanup/unlock, then fail closed. }
  if UninstallerRan and (ResultCode = 0) then
  begin
    WaitedMs := 0;
    while DirExists(AppDir) and (WaitedMs < {#G1UninstallCleanupBudgetMs}) do
    begin
      Sleep({#G1UninstallCleanupPollMs});
      WaitedMs := WaitedMs + {#G1UninstallCleanupPollMs};
    end;
    if DirExists(AppDir) then
    begin
      Log('G1 rollback: uninstaller cleanup did not complete within the bounded wait; aborting rollback; prior payload recoverable at ' + EvacuatedOldDir + '; prior registry not re-advertised.');
      Exit;
    end;
  end;
  { Step 2: quarantine any residual new payload before touching prior payload or
    prior registry. A stale .failed aborts in PrepareToInstall, so a .failed seen
    here was established by this transaction and is only deleted or renamed back
    under that ownership. A .failed owned by this transaction blocks the quarantine
    rename (a directory rename cannot overwrite an existing directory), so the
    owned quarantine is cleared, checked, before the rename and never after the
    prior payload is touched. }
  if FailedQuarantineOwned and DirExists(FailedDir) then
  begin
    if not DelTree(FailedDir, True, True, True) then
    begin
      Log('G1 rollback: owned failed quarantine could not be removed before re-quarantining the new payload; prior payload recoverable at ' + EvacuatedOldDir + '; prior registry not re-advertised.');
      Exit;
    end;
    FailedQuarantineOwned := False;
  end;
  if DirExists(AppDir) then
  begin
    if not RenameFile(AppDir, FailedDir) then
    begin
      Log('G1 rollback: quarantine of the new payload failed; registry left matching the canonical new payload; prior payload recoverable at ' + EvacuatedOldDir + '.');
      Exit;
    end;
    FailedQuarantineOwned := True;
  end;
  { Step 3: restore the prior payload; the prior registry may follow only a proven restoration. }
  if not RenameFile(EvacuatedOldDir, AppDir) then
  begin
    if FailedQuarantineOwned and DirExists(FailedDir) then
      RenameFile(FailedDir, AppDir);
    Log('G1 rollback: prior payload restoration failed; prior payload remains at ' + EvacuatedOldDir + '; prior registry not re-advertised.');
    Exit;
  end;
  if FailedQuarantineOwned and DirExists(FailedDir) and
     (not DelTree(FailedDir, True, True, True)) then
  begin
    Log('G1 rollback: owned failed quarantine could not be removed after prior payload restoration; prior registry not re-advertised; recovery evidence retained at ' + FailedDir + '.');
    Exit;
  end;
  FailedQuarantineOwned := False;
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
    { R4-002: checked cleanup; the snapshot is deleted and ownership cleared only
      after deletion is proven; a cleanup failure is fatal (RaiseException, since
      handler-only Exit cannot fail setup) and preserves the recovery state. }
    if not DelTree(EvacuatedOldDir, True, True, True) then
    begin
      Log('G1 commit: cleanup of the evacuated prior payload at ' + EvacuatedOldDir + ' failed; registry snapshot and recovery state preserved.');
      RaiseException('G1 commit: cleanup of the evacuated prior payload at ' + EvacuatedOldDir + ' failed; setup cannot continue; registry snapshot and recovery state preserved.');
    end;
    if PriorRegistrySnapshot <> '' then
    begin
      DeleteFile(PriorRegistrySnapshot);
      PriorRegistrySnapshot := '';
    end;
    EvacuatedOldDir := '';
  end;
  if CurStep = ssPostInstall then
    InvokePostCommitAssist(AddToPathConsent, EnvBlockConsent, ConfigWizardConsent, CodexChoice, OpencodeChoice, CodexRunnerPath);
end;

procedure DeinitializeSetup;
begin
  if EvacuatedOldDir <> '' then
    RestoreEvacuatedPriorInstall;
end;

function IsAbsolutePath(const S: String): Boolean;
var
  I: Integer;
  HasServer, HasShare: Boolean;
begin
  Result := False;
  if Length(S) < 3 then Exit;

  // Check for drive-rooted: C:\
  if (S[2] = ':') and ((S[3] = '\') or (S[3] = '/')) then
  begin
    Result := True;
    Exit;
  end;

  // Check for UNC: \\server\share
  if (Length(S) >= 5) and (S[1] = '\') and (S[2] = '\') then
  begin
    HasServer := False;
    HasShare := False;

    // Scan for server name (non-empty, no backslash)
    I := 3;
    while (I <= Length(S)) and (S[I] <> '\') do
    begin
      HasServer := True;
      Inc(I);
    end;

    if not HasServer or (I > Length(S)) then Exit; // no server or no separator

    // Skip the backslash after server
    Inc(I);

    // Scan for share name (non-empty)
    while (I <= Length(S)) and (S[I] <> '\') do
    begin
      HasShare := True;
      Inc(I);
    end;

    Result := HasShare;
  end;
end;
procedure OnCodexComboChange(Sender: TObject);
begin
  ProviderPage.Edits[RunnerInputIdx].Enabled := (CodexCombo.ItemIndex = 1);
  ProviderPage.Buttons[RunnerInputIdx].Enabled := (CodexCombo.ItemIndex = 1);
end;
procedure CreateProviderPage;
var Y: Integer;
begin
  ProviderPage := CreateInputFilePage(wpSelectTasks, 'Provider Configuration',
    'Choose provider states for the optional configuration wizard.', '');
  RunnerInputIdx := ProviderPage.Add('Codex runner path (absolute; required when enabling):',
    'Executable Files|*.exe|All Files|*.*', 'exe');
  ProviderPage.Edits[RunnerInputIdx].Enabled := False;
  ProviderPage.Buttons[RunnerInputIdx].Enabled := False;
  Y := ProviderPage.Edits[RunnerInputIdx].Top + ProviderPage.Edits[RunnerInputIdx].Height + ScaleY(12);
  with TNewStaticText.Create(ProviderPage) do begin
    Caption := 'Codex:'; Top := Y; AutoSize := True; Parent := ProviderPage.Surface;
  end;
  Y := Y + ScaleY(20);
  { VCL rule: a control's window handle is created when Parent is assigned,
    so handle-dependent properties (Style, Items, ItemIndex) must come after Parent. }
  CodexCombo := TNewComboBox.Create(ProviderPage);
  CodexCombo.Parent := ProviderPage.Surface;
  CodexCombo.Style := csDropDownList;
  CodexCombo.Items.Add('Unchanged'); CodexCombo.Items.Add('Enabled'); CodexCombo.Items.Add('Disabled');
  CodexCombo.ItemIndex := 0; CodexCombo.Top := Y; CodexCombo.Width := ScaleX(200);
  CodexCombo.OnChange := @OnCodexComboChange;
  Y := Y + ScaleY(28);
  with TNewStaticText.Create(ProviderPage) do begin
    Caption := 'OpenCode Go:'; Top := Y; AutoSize := True; Parent := ProviderPage.Surface;
  end;
  Y := Y + ScaleY(20);
  OpencodeCombo := TNewComboBox.Create(ProviderPage);
  OpencodeCombo.Parent := ProviderPage.Surface;
  OpencodeCombo.Style := csDropDownList;
  OpencodeCombo.Items.Add('Unchanged'); OpencodeCombo.Items.Add('Enabled'); OpencodeCombo.Items.Add('Disabled');
  OpencodeCombo.ItemIndex := 0; OpencodeCombo.Top := Y; OpencodeCombo.Width := ScaleX(200);
end;
function CaptureProviderChoices: Boolean;
begin
  CodexChoice := CodexCombo.ItemIndex;
  OpencodeChoice := OpencodeCombo.ItemIndex;
  CodexRunnerPath := Trim(ProviderPage.Values[RunnerInputIdx]);
  if (CodexChoice = 1) and not IsAbsolutePath(CodexRunnerPath) then begin
    MsgBox('Codex runner path must be an absolute path when enabling Codex.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;
procedure InitializeWizard;
begin
  AddToPathConsent := False;
  EnvBlockConsent := False;
  ConfigWizardConsent := False;
  CleanupConsent := False;
  CodexChoice := 0;
  OpencodeChoice := 0;
  CodexRunnerPath := '';
  CreateProviderPage;
end;

function CaptureInstallConsent: Boolean;
begin
  AddToPathConsent := WizardIsTaskSelected('addtopath');
  EnvBlockConsent := WizardIsTaskSelected('envassist');
  ConfigWizardConsent := WizardIsTaskSelected('configassist');
  Result := True;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (ProviderPage <> nil) and (PageID = ProviderPage.ID) and not ConfigWizardConsent then
    Result := True;
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectTasks then
    Result := CaptureInstallConsent;
  if (CurPageID = ProviderPage.ID) and Result then
    Result := CaptureProviderChoices;
end;

function ConfirmStateCleanup: Boolean;
var
  Choice: Integer;
begin
  { B1: a suppressed message box must never block the G1 rollback, which runs this
    uninstaller with /VERYSILENT /SUPPRESSMSGBOXES /NORESTART. Suppression returns the
    explicit fail-safe default, which matches the dialog default button: the state root
    is kept unless a person answers Yes. }
  Choice := SuppressibleMsgBox(
    'Remove the mutable configuration, cache, and backups in ' +
      ExpandConstant('{localappdata}\yasb-limitora') + '?',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO);
  Result := Choice = IDYES;
end;

function InitializeUninstall: Boolean;
begin
  { R4-001: the manual-close gate runs before consent, cleanup, or deletion; Cancel aborts. }
  if not ManualCloseGate(YasbDetectedRunning) then
  begin
    Result := False;
    Exit;
  end;
  CleanupConsent := ConfirmStateCleanup;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    InvokeUninstallAssist(CleanupConsent);
end;

function PromptManualClose: Boolean;
var
  Choice: Integer;
begin
  { B1: under /SUPPRESSMSGBOXES this returns Cancel, so ManualCloseGate fails closed and
    the uninstaller aborts instead of waiting for a person who is not there. }
  Choice := SuppressibleMsgBox(
    'YASB is currently running. Close YASB manually, then choose Retry. ' +
      'yasb-limitora will never close, restart, or manage YASB for you.',
    mbConfirmation, MB_RETRYCANCEL, IDCANCEL);
  Result := Choice = IDRETRY;
  if Choice = IDCANCEL then
    Result := False;
end;

function ManualCloseGate(DetectedRunning: Boolean): Boolean;
begin
  { R4-001: the user alone closes processes; Retry re-probes, Cancel aborts. }
  Result := True;
  while DetectedRunning do
  begin
    if not PromptManualClose then
    begin
      Result := False;
      Exit;
    end;
    DetectedRunning := YasbDetectedRunning;
  end;
end;

function YasbDetectedRunning: Boolean;
var
  ProbePath: string;
  ProbeOutput: AnsiString;
  ProbeList: string;
  ResultCode: Integer;
begin
  { Read-only tasklist enumeration; an inconclusive probe fails closed as running. }
  Result := True;
  ProbePath := ExpandConstant('{tmp}\yasb-running-probe.csv');
  if Exec(ExpandConstant('{cmd}'), '/C tasklist /FO CSV /NH > "' + ProbePath + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0)
     and LoadStringFromFile(ProbePath, ProbeOutput) then
  begin
    ProbeList := Lowercase(String(ProbeOutput));
    Result := (Pos('"yasb.exe"', ProbeList) > 0) or (Pos('"yasb-limitora.exe"', ProbeList) > 0);
  end;
  DeleteFile(ProbePath);
end;
