@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "NAME_BASE=Path Of Quality"
set "MAIN=app.py"
set "BUILD_VENV=.build-venv"
set "CLEAN_VENV=0"
set "BUILD_MODE=onefile"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="clean" set "CLEAN_VENV=1"
if /i "%~1"=="--clean" set "CLEAN_VENV=1"
if /i "%~1"=="safe" set "BUILD_MODE=onedir"
if /i "%~1"=="--safe" set "BUILD_MODE=onedir"
if /i "%~1"=="onedir" set "BUILD_MODE=onedir"
if /i "%~1"=="--onedir" set "BUILD_MODE=onedir"
shift
goto :parse_args

:args_done

if /i "%BUILD_MODE%"=="onedir" (
  set "PYI_MODE_FLAG=--onedir"
) else (
  set "PYI_MODE_FLAG=--onefile"
)

REM Prefer 'py -3' if available; fallback to 'python'
where py >nul 2>&1 && (set "PYCMD=py -3") || (set "PYCMD=python")

echo [1/8] Determine application version
for /f "delims=" %%V in ('%PYCMD% -c "from src.version import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%V"
if not defined APP_VERSION (
  echo Failed to determine application version.
  goto :fail
)
set "NAME=%NAME_BASE%"
set "DIST_ROOT=dist"
set "OUTPUT_SUBDIR=poq-version-%APP_VERSION%"
set "OUTPUT_DIR=%DIST_ROOT%\%OUTPUT_SUBDIR%"
echo Version detected: %APP_VERSION%

echo [2/8] Optionally clean isolated build virtual environment
if "%CLEAN_VENV%"=="1" (
  if exist "%BUILD_VENV%" rd /s /q "%BUILD_VENV%"
)

echo [3/8] Prepare isolated build virtual environment
if not exist "%BUILD_VENV%\Scripts\python.exe" (
  call %PYCMD% -m venv "%BUILD_VENV%" || goto :fail
)
set "VPY=%BUILD_VENV%\Scripts\python.exe"

echo [4/8] Install project requirements
call "%VPY%" -m pip install -r requirements.txt || goto :fail

echo [5/8] Install/upgrade PyInstaller
call "%VPY%" -m pip install --upgrade pyinstaller || goto :fail

echo [6/8] Clean previous build artifacts
if exist build rd /s /q build
if exist dist rd /s /q dist

echo [7/8] Build %BUILD_MODE%, windowed executable (UPX disabled)
call "%VPY%" -m PyInstaller --noconfirm --clean !PYI_MODE_FLAG! --windowed --noupx ^
  --name "%NAME%" ^
  --icon "poq_icon.png" ^
  --add-data "assets;assets" ^
  --add-data "poq_icon.png;." ^
  --add-data "map-data.json;." ^
  --add-data "settings.json;." ^
  "%MAIN%" || goto :fail

echo [8/8] Prepare output folder (external settings/assets for convenience)
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if /i "%BUILD_MODE%"=="onedir" (
  if exist "%DIST_ROOT%\%NAME%" xcopy "%DIST_ROOT%\%NAME%" "%OUTPUT_DIR%\%NAME%" /E /I /Y >nul
) else (
  if exist "%DIST_ROOT%\%NAME%.exe" move /y "%DIST_ROOT%\%NAME%.exe" "%OUTPUT_DIR%\" >nul
)
if exist settings.json copy /y settings.json "%OUTPUT_DIR%\settings.json" >nul
if exist map-data.json copy /y map-data.json "%OUTPUT_DIR%\map-data.json" >nul
if exist assets xcopy assets "%OUTPUT_DIR%\assets" /E /I /Y >nul
if exist "%NAME%.spec" del "%NAME%.spec"

if "%CLEAN_VENV%"=="1" call :cleanup_venv

echo.
if /i "%BUILD_MODE%"=="onedir" (
  echo Build complete: "%CD%\%OUTPUT_DIR%\%NAME%\%NAME%.exe"
) else (
  echo Build complete: "%CD%\%OUTPUT_DIR%\%NAME%.exe"
)
exit /b 0

:fail
if "%CLEAN_VENV%"=="1" call :cleanup_venv
echo.
echo Build failed. See messages above.
exit /b 1

:cleanup_venv
if exist "%BUILD_VENV%" rd /s /q "%BUILD_VENV%"
goto :eof
