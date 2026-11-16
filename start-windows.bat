@echo off
setlocal
chcp 65001 >nul
title yt down
cd /d "%~dp0"

rem Usage: start-windows.bat            prepare (if needed) and open the app window
rem        start-windows.bat --setup    only prepare Python + dependencies (used by the installer)
set "SETUP_ONLY="
if /i "%~1"=="--setup" set "SETUP_ONLY=1"

rem The installer ships uv in bin\; the ZIP version installs it once if missing.
if exist "%~dp0bin\uv.exe" set "PATH=%~dp0bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    ) else (
        echo Installo uv ^(solo la prima volta^)...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    )
)
where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERRORE: installazione di uv non riuscita. Vedi README.md, sezione "Problemi".
    if not defined SETUP_ONLY pause
    exit /b 1
)
for /f "delims=" %%U in ('where uv') do if not defined YTDOWN_UV set "YTDOWN_UV=%%U"

echo Preparo yt down ^(la prima volta richiede qualche minuto^)...
uv sync --frozen --no-dev --quiet
if errorlevel 1 (
    if not exist ".venv\Scripts\pythonw.exe" (
        echo.
        echo ERRORE: installazione delle dipendenze non riuscita. Controlla la connessione e riprova.
        if not defined SETUP_ONLY pause
        exit /b 1
    )
)

rem A sync interrupted halfway (e.g. connection lost) can leave a venv without packages.
".venv\Scripts\python.exe" -c "import ytdown, webview, yt_dlp, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERRORE: yt down non e' completo. Controlla la connessione a internet e riprova.
    if not defined SETUP_ONLY pause
    exit /b 1
)

if defined SETUP_ONLY (
    rem Install the latest yt-dlp now, so the first start is ready to download.
    uv pip install --quiet --python ".venv\Scripts\python.exe" --upgrade "yt-dlp[default]"
    exit /b 0
)

rem The app window runs without a console; it updates yt-dlp itself at every start.
start "" ".venv\Scripts\pythonw.exe" -m ytdown %*
exit /b 0
