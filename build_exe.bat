@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "NAME=PathOfQuality"
set "MAIN=app.py"

REM Prefer 'py -3' if available; fallback to 'python'
where py >nul 2>&1 && (set "PYCMD=py -3") || (set "PYCMD=python")

echo [1/5] Install project requirements
call %PYCMD% -m pip install -r requirements.txt || goto :fail

echo [2/5] Install/upgrade PyInstaller
call %PYCMD% -m pip install --upgrade pyinstaller || goto :fail

echo [3/5] Clean previous build artifacts
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist "%NAME%.spec" del "%NAME%.spec"

echo [4/5] Build one-file, windowed executable
call %PYCMD% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%NAME%" ^
  --add-data "assets;assets" ^
  --add-data "settings.json;." ^
  "%MAIN%" || goto :fail

echo [5/5] Prepare output folder (external settings/assets for convenience)
if not exist dist mkdir dist
if exist settings.json copy /y settings.json "dist\settings.json" >nul
if exist assets xcopy assets "dist\assets" /E /I /Y >nul

echo.
echo Build complete: "%CD%\dist\%NAME%.exe"
exit /b 0

:fail
echo.
echo Build failed. See messages above.
exit /b 1
