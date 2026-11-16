; Windows installer for yt down (Inno Setup 6). Built by .github/workflows/installers.yml:
;   iscc /DAppVersion=1.0.0 installer\ytdown.iss
; Expects the uv executable at installer\bin\uv.exe (downloaded by the workflow).
; Per-user install, no admin rights: the app keeps its .venv inside {app}, so it must be writable.
; Python and dependencies are prepared during installation (start-windows.bat --setup);
; the shortcuts start the app window directly with pythonw.exe, without a console.

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
Name: "{autoprograms}\yt down"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m ytdown"; WorkingDir: "{app}"; IconFilename: "{app}\ytdown.ico"
Name: "{autodesktop}\yt down"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m ytdown"; WorkingDir: "{app}"; IconFilename: "{app}\ytdown.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m ytdown"; WorkingDir: "{app}"; Description: "Avvia yt down"; Flags: nowait postinstall skipifsilent; Check: AppReady

[UninstallDelete]
; Created by start-windows.bat --setup, not by the installer.
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\src\ytdown.egg-info"

[Code]
procedure StopRunningApp();
var
  ResultCode: Integer;
  Script: String;
begin
  { Close yt down and its yt-dlp children, so their files can be replaced. Matched by command
    line: the venv's pythonw.exe starts the real interpreter from uv's Python folder. }
  Script := 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ''*-m ytdown*'' -or $_.CommandLine -like ''*-m yt_dlp*'' } | Invoke-CimMethod -MethodName Terminate | Out-Null';
  Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function AppReady(): Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\.venv\Scripts\pythonw.exe'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if DirExists(ExpandConstant('{app}')) then
    StopRunningApp();
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Preparo yt down: scarico Python e i componenti (qualche minuto, serve internet)...';
    WizardForm.ProgressGauge.Style := npbstMarquee;
    if not Exec(ExpandConstant('{cmd}'), '/C ""' + ExpandConstant('{app}\start-windows.bat') + '" --setup"',
                ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      SuppressibleMsgBox('Non sono riuscito a preparare yt down. Controlla la connessione a internet e riapri questo installer.',
                         mbError, MB_OK, IDOK);
    WizardForm.ProgressGauge.Style := npbstNormal;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningApp();
  Result := True;
end;
