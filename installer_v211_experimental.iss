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
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\app_icon.ico

[Files]
Source: "dist\NiyomsilAIEnhancer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "installfourai"; Description: "Install all four AI engines for offline use (requires internet)"; GroupDescription: "V2.1.1 AI setup:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetProvisionParameters}"; Description: "Download and verify the four AI engines for offline use"; StatusMsg: "Downloading and verifying the four AI engines..."; Flags: waituntilterminated runascurrentuser; Tasks: installfourai
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Check: ShouldLaunchEditor; Flags: nowait postinstall skipifsilent

[Code]
var
  FourAISetupExitCode: Integer;
  FourAISetupArmed: Boolean;

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
    FourAISetupArmed := SaveStringToFile(FourAIPendingMarker(), 'pending', False);
  end;

  if (CurStep = ssPostInstall) and WizardIsTaskSelected('installfourai') then
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
