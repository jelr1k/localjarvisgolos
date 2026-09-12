@echo off
chcp 65001 >nul

cd /d "%~dp0"

set "LOG_DIR=%~dp0logs"
set "LOG_FILE=%LOG_DIR%\startup.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.>>"%LOG_FILE%"
echo ==================================================>>"%LOG_FILE%"
echo [%date% %time%] Проверка и установка зависимостей Jarvis>>"%LOG_FILE%"

echo Проверка и установка зависимостей Jarvis...
python -m pip install -r "%~dp0requirements.txt" >>"%LOG_FILE%" 2>&1

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
