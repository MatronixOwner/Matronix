#define AppName "Matronix"
#define AppVersion "0.2.0"
[Setup]
AppId={{7AE2F2C3-74B1-4C0A-8D4C-9BB65A71DF62}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Matronix
DefaultDirName={localappdata}\Programs\Matronix
DefaultGroupName=Matronix
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=MatronixSetup
SetupIconFile=..\matronix\icon.ico
UninstallDisplayIcon={app}\Matronix.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
SetupLogging=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Matronix.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Matronix"; Filename: "{app}\Matronix.exe"
Name: "{userdesktop}\Matronix"; Filename: "{app}\Matronix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Matronix.exe"; Description: "{cm:LaunchProgram,Matronix}"; Flags: nowait postinstall skipifsilent
