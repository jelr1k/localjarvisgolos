@echo off
setlocal EnableExtensions

rem ============================================================
rem JARVIS - Architecture Test Runner
rem ============================================================

set "TESTS_DIR=%~dp0"
for %%I in ("%TESTS_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

if not exist "%PROJECT_ROOT%\core\" (
    echo ERROR: core folder not found: "%PROJECT_ROOT%\core"
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\tests\unit\" (
    echo ERROR: unit test folder not found: "%PROJECT_ROOT%\tests\unit"
    pause
    exit /b 1
)

cd /d "%PROJECT_ROOT%"

echo ========================================
echo JARVIS - Architecture Test Runner
echo ========================================
echo Project: %PROJECT_ROOT%
echo.

echo [1/4] Python
python --version
if errorlevel 1 goto :python_error

echo.
echo [2/4] Pytest
python -m pytest --version >nul 2>&1
if errorlevel 1 goto :pytest_error
python -m pytest --version

echo.
echo [3/4] Python syntax check
python -m compileall -q core chat llm services security tools voice presentation ui start
if errorlevel 1 goto :compile_error
echo Syntax check: OK

echo.
echo [4/4] Unit and architecture tests
echo ----------------------------------------
python -m pytest tests\unit -ra --tb=short
set "TEST_EXIT=%ERRORLEVEL%"
echo ----------------------------------------

echo.
echo ========================================
if "%TEST_EXIT%"=="0" (
    echo RESULT: ALL ARCHITECTURE TESTS PASSED
) else (
    echo RESULT: TESTS FAILED
    echo Exit code: %TEST_EXIT%
    echo.
    echo The failure is in the application/tests,
    echo not in the test runner itself.
)
echo ========================================
echo.

pause
exit /b %TEST_EXIT%

:python_error
echo.
echo ERROR: Python was not found in PATH.
pause
exit /b 1

:pytest_error
echo.
echo ERROR: pytest is not installed for this Python.
echo Run start.bat once to install project dependencies,
echo or install the dependencies from config\requirements.txt.
pause
exit /b 1

:compile_error
echo.
echo ERROR: Python syntax check failed.
echo See the compiler output above.
pause
exit /b 1
