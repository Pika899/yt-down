@echo off
setlocal
chcp 65001 >nul
title yt down
cd /d "%~dp0"

rem uv manages Python and every dependency; install it once if missing.
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
    pause
    exit /b 1
)

echo Preparo yt down ^(la prima volta richiede qualche minuto^)...
uv sync --frozen --no-dev --quiet
if errorlevel 1 (
    echo.
    echo ERRORE: installazione delle dipendenze non riuscita. Controlla la connessione e riprova.
    pause
    exit /b 1
)

rem YouTube changes often: keep yt-dlp current. Offline is fine, the installed version is used.
uv pip install --quiet --upgrade "yt-dlp[default]" 2>nul

uv run --no-sync python -m ytdown
if errorlevel 1 pause
