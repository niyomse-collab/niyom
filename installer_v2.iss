#define MyAppName "NiyomSilp Design v2.1"
#ifndef MyAppVersion
  #define MyAppVersion "2.1.0-beta.1"
#endif
#define MyAppPublisher "NiyomSilp Design"
#define MyAppExeName "NiyomsilAIEnhancer.exe"

[Setup]
AppId={{C0DC8AA4-8EC2-4AE2-A9B0-2047E57A0802}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomSilpDesignV2
UsePreviousAppDir=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=NiyomSilp-Design-v2-Setup
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

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
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
  TargetDir, InstalledV1: String;
begin
  Result := '';
  TargetDir := ExpandConstant('{app}');
  { Never allow even a custom /DIR installation to overwrite the V1 program. }
  if IsInFolder(TargetDir, ExpandConstant('{autopf}\NiyomSilpDesignV1')) then
  begin
    Result := 'NiyomSilp Design v2 cannot install inside the v1 folder.';
    Exit;
  end;
  { Guard a V1 custom installation location recorded by Inno Setup. }
  if RegQueryStringValue(
      HKLM64,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{D657F42C-17C9-43C9-88EA-41FCD2788931}_is1',
      'InstallLocation', InstalledV1) then
  begin
    if (InstalledV1 <> '') and IsInFolder(TargetDir, InstalledV1) then
      Result := 'V2 cannot overwrite the registered NiyomSilp Design v1 installation.';
  end;
end;
