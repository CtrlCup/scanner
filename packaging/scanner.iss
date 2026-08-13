; Inno Setup Skript für den Scanner-Windows-Installer.
; Wird in CI mit ISCC.exe /DMyAppVersion=X.Y.Z packaging\scanner.iss aufgerufen.
; Erwartet die fertig gebaute dist\Scanner.exe (PyInstaller-Onefile-Build).

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Scanner"
#define MyAppPublisher "Alex Klauser"
#define MyAppURL "https://github.com/CtrlCup/scanner"
#define MyAppExeName "Scanner.exe"

[Setup]
AppId={{4F3E9C2E-2E4B-4E36-9A8C-2B6C6E8E9C10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist\installer
OutputBaseFilename=Scanner-{#MyAppVersion}-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\src\scanner_app\resources\icon.ico
DisableProgramGroupPage=yes
; RestartApplications ist zwar bereits Inno-Setup-Default, wird hier aber explizit gesetzt
; und dokumentiert: die App nutzt dies für ihr automatisches Update (windows_updater.py) —
; ein still gestarteter Installer (/CLOSEAPPLICATIONS /RESTARTAPPLICATIONS) lässt den
; Windows-Restart-Manager die laufende Scanner.exe erkennen, schließen und danach neu starten.
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Scanner.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Scanner}"; Flags: nowait postinstall skipifsilent
