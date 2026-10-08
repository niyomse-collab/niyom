#define MyAppName "Niyomsil Design AI Enhancer"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Niyomsil Design"
#define MyAppExeName "NiyomsilAIEnhancer.exe"

[Setup]
AppId={{B0DD9E45-BD74-48A0-8C7B-B87227371EB1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NiyomsilDesignAIEnhancer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=Niyomsil-Design-AI-Enhancer-Setup-v2.1.0
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
