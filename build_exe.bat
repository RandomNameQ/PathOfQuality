@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "NAME_BASE=PathOfQuality"
set "MAIN=app.py"

REM Prefer 'py -3' if available; fallback to 'python'
where py >nul 2>&1 && (set "PYCMD=py -3") || (set "PYCMD=python")

echo [1/6] Determine application version
for /f "delims=" %%V in ('%PYCMD% -c "from src.version import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%V"
if not defined APP_VERSION (
  echo Failed to determine application version.
  goto :fail
)
set "NAME=%NAME_BASE%_%APP_VERSION%"
set "DIST_ROOT=dist"
set "OUTPUT_SUBDIR=poq_%APP_VERSION%"
set "OUTPUT_DIR=%DIST_ROOT%\%OUTPUT_SUBDIR%"
echo Version detected: %APP_VERSION%

echo [2/6] Install project requirements
call %PYCMD% -m pip install -r requirements.txt || goto :fail

echo [3/6] Install/upgrade PyInstaller
call %PYCMD% -m pip install --upgrade pyinstaller || goto :fail

echo [4/6] Clean previous build artifacts
if exist build rd /s /q build
if exist dist rd /s /q dist

echo [5/6] Build one-file, windowed executable
call %PYCMD% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%NAME%" ^
  --add-data "assets;assets" ^
  --add-data "settings.json;." ^
  "%MAIN%" || goto :fail

echo [6/6] Prepare output folder (external settings/assets for convenience)
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if exist "%DIST_ROOT%\%NAME%.exe" move /y "%DIST_ROOT%\%NAME%.exe" "%OUTPUT_DIR%\" >nul
if exist settings.json copy /y settings.json "%OUTPUT_DIR%\settings.json" >nul
if exist assets xcopy assets "%OUTPUT_DIR%\assets" /E /I /Y >nul
if exist "%NAME%.spec" del "%NAME%.spec"

echo.
echo Build complete: "%CD%\%OUTPUT_DIR%\%NAME%.exe"
exit /b 0

:fail
echo.
echo Build failed. See messages above.
exit /b 1
