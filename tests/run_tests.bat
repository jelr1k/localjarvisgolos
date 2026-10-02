@echo off
setlocal EnableExtensions

rem ============================================================
rem JARVIS - Test Runner
rem Uses the current Python project layout.
rem ============================================================

set "TESTS_DIR=%~dp0"
for %%I in ("%TESTS_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

if not exist "%PROJECT_ROOT%\core\" (
    echo.
    echo ERROR: JARVIS project root was not found.
    echo Expected: "%PROJECT_ROOT%\core"
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\tests\" (
    echo.
    echo ERROR: Tests directory was not found.
    echo Expected: "%PROJECT_ROOT%\tests"
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

echo [1/3] Python
python --version
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Pytest
python -m pytest --version
if errorlevel 1 (
    echo.
    echo ERROR: pytest is not installed for this Python.
    echo Install the project dependencies first, then run this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo [3/3] Running JARVIS tests
echo ----------------------------------------
echo Import root: %PROJECT_ROOT%
echo Test folder: %PROJECT_ROOT%\tests
echo.
echo The runner will show failed test names and short tracebacks.
echo ----------------------------------------
echo.

python -m pytest tests -ra --tb=short
set "TEST_EXIT=%ERRORLEVEL%"

echo.
echo ========================================
if "%TEST_EXIT%"=="0" (
    echo RESULT: ALL TESTS PASSED
) else (
    echo RESULT: TESTS FAILED
    echo Exit code: %TEST_EXIT%
    echo.
    echo IMPORTANT:
    echo The runner itself completed normally.
    echo The failures above are failures in individual tests,
    echo not a failure of run_tests.bat.
)
echo ========================================
echo.

pause
exit /b %TEST_EXIT%
