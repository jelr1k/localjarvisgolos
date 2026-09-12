@echo off
chcp 65001 >nul

cd /d "%~dp0"

call "%~dp0install_dependencies.bat"
if errorlevel 1 exit /b 1

start "" pythonw main.py

exit