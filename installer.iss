#define MyAppName "NiyomSilp AI Core - Portrait Gentle TEST"
#define MyAppVersion "2.1.3-test"
#define MyAppPublisher "Niyomsil Design"
#define MyAppExeName "NiyomsilAIEnhancer.exe"

[Setup]
AppId={{A8ECF5DD-5C21-4E44-91D0-20261010A111}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomSilpPortraitGentleTEST
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=NiyomSilp-Portrait-Gentle-TEST-Setup-v2.1.3
Compression=lzma2/normal
SolidCompression=yes
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
