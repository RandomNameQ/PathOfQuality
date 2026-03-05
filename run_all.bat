@echo off
setlocal
cd /d "%~dp0"

call "%~dp0run_app.bat"
set "APP_EXIT_CODE=%ERRORLEVEL%"

endlocal & set "APP_EXIT_CODE=%APP_EXIT_CODE%"
exit %APP_EXIT_CODE%
