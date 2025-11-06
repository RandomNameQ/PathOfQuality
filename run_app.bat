@echo off
setlocal
rem Используем UTF-8 для корректного вывода русских сообщений
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

rem Предпочитаем Python из локального виртуального окружения
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" app.py
) else (
    rem Фолбэк на системный Python
    python app.py
)

endlocal