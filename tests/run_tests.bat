@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

rem Support both the current root layout and the future tests\ layout.
if exist "%SCRIPT_DIR%core\" (
    set "PROJECT_ROOT=%SCRIPT_DIR%"
) else (
    set "PROJECT_ROOT=%SCRIPT_DIR%..\"
)

set "REQUIREMENTS_FILE=%PROJECT_ROOT%config\requirements.txt"
if not exist "%REQUIREMENTS_FILE%" set "REQUIREMENTS_FILE=%PROJECT_ROOT%requirements.txt"

cd /d "%PROJECT_ROOT%"

echo ========================================
echo JARVIS - Test Runner
echo ========================================
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found in PATH.
    echo Install Python or add it to PATH.
    pause
    exit /b 1
)

echo.
echo Installing/updating test dependencies...
python -m pip install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Running tests...
echo.
python -m pytest -q
set "TEST_EXIT=%errorlevel%"

echo.
echo ========================================
if "%TEST_EXIT%"=="0" (
    echo ALL TESTS PASSED
) else (
    echo SOME TESTS FAILED
)
echo ========================================
echo.

pause
exit /b %TEST_EXIT%
