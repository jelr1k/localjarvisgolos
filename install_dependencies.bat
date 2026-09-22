@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"

rem Support both the current root layout and the future start\ layout.
if exist "%SCRIPT_DIR%core\" (
    set "PROJECT_ROOT=%SCRIPT_DIR%"
) else (
    set "PROJECT_ROOT=%SCRIPT_DIR%..\"
)

set "LOG_DIR=%PROJECT_ROOT%logs"
set "LOG_FILE=%LOG_DIR%\startup.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "REQUIREMENTS_FILE=%PROJECT_ROOT%config\requirements.txt"
if not exist "%REQUIREMENTS_FILE%" set "REQUIREMENTS_FILE=%PROJECT_ROOT%requirements.txt"

echo.>>"%LOG_FILE%"
echo ==================================================>>"%LOG_FILE%"
echo [%date% %time%] Проверка и установка зависимостей Jarvis>>"%LOG_FILE%"

echo Проверка и установка зависимостей Jarvis...
python -m pip install -r "%REQUIREMENTS_FILE%" >>"%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo [%date% %time%] ОШИБКА: не удалось установить зависимости Jarvis.>>"%LOG_FILE%"
    echo.>>"%LOG_FILE%"
    echo.
    echo Не удалось установить зависимости Jarvis.
    echo Подробности сохранены в:
    echo %LOG_FILE%
    echo Проверьте, что Python и pip доступны через команду python.
    pause
    exit /b 1
)

echo [%date% %time%] Зависимости успешно проверены/установлены.>>"%LOG_FILE%"
exit /b 0
