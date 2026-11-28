#define MyAppName "NiyomSilp Design V2.1.1 EXPERIMENTAL"
#ifndef MyAppVersion
  #define MyAppVersion "2.1.0-beta.1"
#endif
#define MyAppPublisher "NiyomSilp Design"
#define MyAppExeName "NiyomsilAIEnhancer.exe"

[Setup]
AppId={{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomSilpDesignV211Experimental
UsePreviousAppDir=no
DisableDirPage=yes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=NiyomSilp-Design-v211-EXPERIMENTAL-Setup
Compression=lzma2/normal
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=1800000000
SlicesPerDisk=1
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\app_icon.ico

[Files]
Source: "dist\NiyomsilAIEnhancer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; Remember the exact profile-local cache root used by the installer task.
; The uninstaller asks before deleting anything and the Python cleanup validates this path.
Root: HKCU64; Subkey: "Software\NiyomSilp\V211Experimental"; ValueType: string; ValueName: "FourAIDataRoot"; ValueData: "{localappdata}\NiyomSilp\V211-FourAI-QA"; Flags: uninsdeletevalue

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "installfourai"; Description: "I agree: download and install all four AI engines now for automatic offline use (internet required; stored in this Windows user profile)"; GroupDescription: "V2.1.1 offline AI engines (one-time):"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetProvisionParameters}"; Description: "Download and verify the four AI engines for offline use"; StatusMsg: "Downloading and verifying the four AI engines..."; Flags: waituntilterminated runascurrentuser; Tasks: installfourai
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Check: ShouldLaunchEditor; Flags: nowait postinstall skipifsilent

[Code]
var
  FourAISetupExitCode: Integer;
  FourAISetupArmed: Boolean;
  FourAIDataRootPath: String;

function GetProvisionParameters(Param: String): String;
begin
  Result := '--provision-v211-four-ai';
  if WizardSilent then
    Result := Result + ' --silent';
end;

function FourAICompletionMarker: String;
begin
  Result := ExpandConstant('{localappdata}\NiyomSilp\V211-FourAI-QA\setup-complete.flag');
end;

function FourAIPendingMarker: String;
begin
  Result := ExpandConstant('{localappdata}\NiyomSilp\V211-FourAI-QA\setup-pending.flag');
end;

function ShouldLaunchEditor: Boolean;
begin
  Result := not WizardIsTaskSelected('installfourai');
  if WizardIsTaskSelected('installfourai') then
    Result := FourAISetupArmed and
              FileExists(FourAICompletionMarker()) and
              not FileExists(FourAIPendingMarker());
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) and WizardIsTaskSelected('installfourai') then
  begin
    { A fresh pending marker makes any stale success marker unusable. }
    FourAISetupExitCode := 1;
    { Create the per-user marker directory on a clean first install before writing. }
    FourAISetupArmed :=
      ForceDirectories(ExtractFileDir(FourAIPendingMarker())) and
      SaveStringToFile(FourAIPendingMarker(), 'pending', False);
    if not FourAISetupArmed then
      Log('V2.1.1: could not create the fresh four-engine setup pending marker');
  end;

  { ssDone is reached after the [Run] entries have completed. Checking at
    ssPostInstall would run too early, before the provisioning command writes
    its fresh completion marker (especially breaking silent installs). }
  if (CurStep = ssDone) and WizardIsTaskSelected('installfourai') then
  begin
    if FourAISetupArmed and
       FileExists(FourAICompletionMarker()) and
       not FileExists(FourAIPendingMarker()) then
      FourAISetupExitCode := 0
    else
      FourAISetupExitCode := 1;
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := FourAISetupExitCode;
end;

function IsInFolder(const Candidate, RootFolder: String): Boolean;
var
  C, R: String;
begin
  C := Uppercase(RemoveBackslashUnlessRoot(Candidate));
  R := Uppercase(RemoveBackslashUnlessRoot(RootFolder));
  Result := (C = R) or (Copy(C, 1, Length(R) + 1) = R + '\');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  TargetDir, InstalledV1, InstalledV2: String;
begin
  Result := '';
  TargetDir := ExpandConstant('{app}');
  { Experimental v2.1.1 must NEVER overwrite either V1 or V2 Stable. }
  if IsInFolder(TargetDir, ExpandConstant('{autopf}\NiyomSilpDesignV1')) or
     IsInFolder(TargetDir, ExpandConstant('{autopf}\NiyomSilpDesignV2')) then
  begin
    Result := 'V2.1.1 experimental cannot install inside the V1/V2 Stable folder.';
    Exit;
  end;
  if RegQueryStringValue(
      HKLM64,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{D657F42C-17C9-43C9-88EA-41FCD2788931}_is1',
      'InstallLocation', InstalledV1) then
  begin
    if (InstalledV1 <> '') and IsInFolder(TargetDir, InstalledV1) then
    begin
      Result := 'V2.1.1 experimental cannot overwrite registered V1.';
      Exit;
    end;
  end;
  if RegQueryStringValue(
      HKLM64,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{C0DC8AA4-8EC2-4AE2-A9B0-2047E57A0802}_is1',
      'InstallLocation', InstalledV2) then
  begin
    if (InstalledV2 <> '') and IsInFolder(TargetDir, InstalledV2) then
      Result := 'V2.1.1 experimental cannot overwrite registered V2 Stable.';
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  FourAIDataRootPath := '';
  RegQueryStringValue(
    HKCU64,
    'Software\NiyomSilp\V211Experimental',
    'FourAIDataRoot',
    FourAIDataRootPath
  );
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ErrorCode: Integer;
  Parameters: String;
  CurrentUserFourAIDataRoot: String;
begin
  { usUninstall occurs after the user confirms uninstall and before app files
    are removed. Silent uninstall deliberately keeps all per-user model caches. }
  if (CurUninstallStep = usUninstall) and (not UninstallSilent) then
  begin
    CurrentUserFourAIDataRoot :=
      ExpandConstant('{localappdata}\NiyomSilp\V211-FourAI-QA');
    if DirExists(CurrentUserFourAIDataRoot) then
    begin
      if MsgBox(
        'Do you also want to remove the four downloaded AI engines and their manifest from this Windows account?' #13#13 +
        'Only the dedicated NiyomSilp V2.1.1 engine cache will be removed. ' +
        'Unknown files, customer artwork, V1 and V2 Stable files are not part of this cleanup.' #13#13 +
        'Choose No to keep the models for later offline use.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES then
      begin
        Parameters :=
          '--remove-v211-four-ai-assets --confirmed-by-user --data-root "' +
          CurrentUserFourAIDataRoot + '"';
        if not Exec(
          ExpandConstant('{app}\{#MyAppExeName}'),
          Parameters,
          ExpandConstant('{app}'),
          SW_HIDE,
          ewWaitUntilTerminated,
          ErrorCode
        ) then
          MsgBox(
            'The four-engine cache cleanup could not be started. The cache was left in place.',
            mbError,
            MB_OK
          )
        else if ErrorCode <> 0 then
          MsgBox(
            'The four-engine cache cleanup did not complete safely. Remaining files were left in place.',
            mbError,
            MB_OK
          );
      end;
    end;

    { The install-time profile may differ if Setup was elevated with another
      administrator account. Never delete that other profile's cache silently. }
    if (FourAIDataRootPath <> '') and
       (Uppercase(FourAIDataRootPath) <> Uppercase(CurrentUserFourAIDataRoot)) and
       DirExists(FourAIDataRootPath) then
      MsgBox(
        'A separate V2.1.1 model cache exists in another Windows user profile. ' +
        'It was left untouched for safety. Sign in to that account to remove its cache if desired.',
        mbInformation,
        MB_OK
      );
  end;
end;
