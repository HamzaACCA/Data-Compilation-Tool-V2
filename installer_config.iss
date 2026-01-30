; Data Analytical and Compilation Tool - Professional Installer Script
; This creates a single .exe installer with desktop icon

[Setup]
AppName=Data Analytical and Compilation Tool
AppVersion=2.0
AppPublisher=Hamza Yahya - Internal Audit
AppPublisherURL=https://yourwebsite.com
; Install to user's local app data (writable without admin)
DefaultDirName={localappdata}\DataCompilationTool
DefaultGroupName=Data Analytical and Compilation Tool
OutputDir=installer_output
OutputBaseFilename=DataCompilationTool_V3_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DataCompilationTool.exe
; No admin required since we install to user folder
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a &Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Dirs]
; Create Data folder structure with full permissions
Name: "{app}\Data"; Permissions: users-full
Name: "{app}\Data\Projects"; Permissions: users-full

[Files]
; Main executable
Source: "dist\DataCompilationTool.exe"; DestDir: "{app}"; Flags: ignoreversion
; Templates folder
Source: "templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
; Documentation
Source: "USER_GUIDE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Desktop icon
Name: "{autodesktop}\Data Analytical and Compilation Tool"; Filename: "{app}\DataCompilationTool.exe"; Tasks: desktopicon
; Start Menu icon
Name: "{group}\Data Analytical and Compilation Tool"; Filename: "{app}\DataCompilationTool.exe"
Name: "{group}\Open Data Folder"; Filename: "{app}\Data"
Name: "{group}\User Guide"; Filename: "{app}\USER_GUIDE.txt"
Name: "{group}\Uninstall Data Analytical and Compilation Tool"; Filename: "{uninstallexe}"

[Run]
; Option to run the app after installation
Filename: "{app}\DataCompilationTool.exe"; Description: "Launch Data Analytical and Compilation Tool"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up data folders on uninstall
Type: filesandordirs; Name: "{app}\Data"
