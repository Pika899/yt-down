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
Source: "..\.python-version"; DestDir: "{app}"; Flags: ignoreversion
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
Type: filesandordirs; Name: "{app}\src"

[Code]
{ The app writes its process id to {app}\.venv\ytdown.pid. Only that process (and its
  yt-dlp/ffmpeg children) is closed, after checking it really is yt down. }

function RunPowerShell(Script: String): Integer;
var
  ResultCode: Integer;
begin
  if not Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"',
              '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ResultCode := -1;
  Result := ResultCode;
end;

function AppPid(): Integer;
var
  Text: AnsiString;
begin
  Result := 0;
  if LoadStringFromFile(ExpandConstant('{app}\.venv\ytdown.pid'), Text) then
    Result := StrToIntDef(Trim(String(Text)), 0);
end;

function AppRunning(Pid: Integer): Boolean;
begin
  Result := (Pid > 0) and (RunPowerShell(
    'if (Get-CimInstance Win32_Process -Filter ''ProcessId=' + IntToStr(Pid) + ''' | ' +
    'Where-Object { $_.CommandLine -like ''*-m ytdown*'' }) { exit 1 } else { exit 0 }') = 1);
end;

function CloseAppIfRunning(): Boolean;
var
  Pid, ResultCode: Integer;
begin
  Result := True;
  Pid := AppPid();
  if not AppRunning(Pid) then
    exit;
  if SuppressibleMsgBox('yt down è aperto e verrà chiuso: i download in corso si interrompono. Continuare?',
                        mbConfirmation, MB_YESNO, IDYES) = IDNO then
  begin
    Result := False;
    exit;
  end;
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/PID ' + IntToStr(Pid) + ' /T /F', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  RunPowerShell('Wait-Process -Id ' + IntToStr(Pid) + ' -Timeout 20 -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1');
end;

function AppReady(): Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\.venv\Scripts\pythonw.exe'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if DirExists(ExpandConstant('{app}')) and not CloseAppIfRunning() then
    Result := 'Installazione annullata: chiudi yt down e riprova.';
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
  Result := CloseAppIfRunning();
end;
