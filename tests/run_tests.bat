@echo off
setlocal EnableExtensions

rem ============================================================
rem JARVIS - Test Runner
rem Current project layout:
rem   <project>\core
rem   <project>\tests
rem   <project>\start
rem ============================================================

set "TESTS_DIR=%~dp0"
set "PROJECT_ROOT=%TESTS_DIR%.."

rem Normalize the project path.
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"

if not exist "%PROJECT_ROOT%\core\" (
    echo.
    echo ERROR: Project root was not found.
    echo Expected folder: "%PROJECT_ROOT%\core"
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\tests\" (
    echo.
    echo ERROR: Tests folder was not found.
    echo Expected folder: "%PROJECT_ROOT%\tests"
    echo.
    pause
    exit /b 1
)

cd /d "%PROJECT_ROOT%"

echo ========================================
echo JARVIS - Test Runner
echo ========================================
echo Project: %PROJECT_ROOT%
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found in PATH.
    echo.
    pause
    exit /b 1
)

echo.
echo Checking pytest...
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo pytest is not installed.
    echo Installing pytest...
    python -m pip install "pytest>=8,<9"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install pytest.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Python path:
where python
echo.

rem Make the project root explicitly available for imports.
rem This prevents errors such as:
rem   ModuleNotFoundError: No module named 'core'
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

echo Running tests...
echo ----------------------------------------
python -m pytest tests -q
set "TEST_EXIT=%errorlevel%"
echo ----------------------------------------
echo.

if "%TEST_EXIT%"=="0" (
    echo ========================================
    echo ALL TESTS PASSED
    echo ========================================
) else (
    echo ========================================
    echo SOME TESTS FAILED
    echo ========================================
    echo Exit code: %TEST_EXIT%
    echo.
    echo The full pytest output above contains the
    echo information needed to diagnose the failure.
)

echo.
pause
exit /b %TEST_EXIT%
