#define MyAppName "NiyomSilp Independent Core TEST"
#define MyAppVersion "0.1.0-test"
#define MyAppPublisher "NiyomSilp Design"
#define MyAppExeName "NiyomSilpCoreTEST.exe"

[Setup]
; Distinct identity and folder: stable V2.1 app remains untouched.
AppId={{7F2AC880-44A0-4FF0-9E19-4111FA57D902}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomSilpIndependentCoreTEST
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release-independent
OutputBaseFilename=NiyomSilp-Independent-Core-TEST-Setup-v0.1.0
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\app_icon.ico

[Files]
Source: "dist\NiyomSilpCoreTEST\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create separate TEST shortcut"; GroupDescription: "Optional:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TEST"; Flags: nowait postinstall skipifsilent
