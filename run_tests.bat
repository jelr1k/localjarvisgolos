@echo off
setlocal

cd /d "%~dp0"

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
python -m pip install -r requirements.txt
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
