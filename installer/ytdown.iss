; Windows installer for yt down (Inno Setup 6). Built by .github/workflows/windows-installer.yml:
;   iscc /DAppVersion=1.0.0 installer\ytdown.iss
; Expects the uv executable at installer\bin\uv.exe (downloaded by the workflow).
; Per-user install, no admin rights: the app keeps its .venv inside {app}, so it must be writable.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3C2A9E-4B1D-4E7A-9C55-2D8E1F0B7A31}
AppName=yt down
AppVersion={#AppVersion}
AppPublisher=yt down
DefaultDirName={autopf}\yt down
DefaultGroupName=yt down
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=yt-down-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=yt down
SetupIconFile=..\assets\ytdown.ico
UninstallDisplayIcon={app}\ytdown.ico

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul Desktop"; GroupDescription: "Icone:"

[Files]
Source: "..\src\*"; DestDir: "{app}\src"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\uv.lock"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\start-windows.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "bin\uv.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\assets\ytdown.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\yt down"; Filename: "{app}\start-windows.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ytdown.ico"
Name: "{autodesktop}\yt down"; Filename: "{app}\start-windows.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ytdown.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\start-windows.bat"; Description: "Avvia yt down"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallDelete]
; Created at first launch by uv sync, not by the installer.
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\src\ytdown.egg-info"
