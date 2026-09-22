@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0"
set "START_DIR=%PROJECT_ROOT%start"

rem Support both the current layout and the future start\ layout.
if not exist "%START_DIR%\" set "START_DIR=%PROJECT_ROOT%"

call "%START_DIR%\install_dependencies.bat"
if errorlevel 1 exit /b 1

start "" pythonw "%START_DIR%\bootstrap.py"

exit /b 0
