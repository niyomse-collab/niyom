#define MyAppName "NiyomSilp Design v1"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "NiyomSilp Design"
#define MyAppExeName "NiyomsilAIEnhancer.exe"

[Setup]
AppId={{D657F42C-17C9-43C9-88EA-41FCD2788931}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomSilpDesignV1
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=NiyomSilp-Design-v1-Setup
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\app_icon.ico

[InstallDelete]
; Clean up Thai-named shortcuts from the earlier v1 installer on upgrade.
Type: files; Name: "{autoprograms}\นิยมศิลป์ดีไซน์ v1.lnk"
Type: files; Name: "{autodesktop}\นิยมศิลป์ดีไซน์ v1.lnk"

[Files]
Source: "dist\NiyomsilAIEnhancer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
