@echo off
chcp 65001 >nul

cd /d "%~dp0"

echo Проверка и установка зависимостей Jarvis...
python -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo Не удалось установить зависимости Jarvis.
    echo Проверьте, что Python и pip доступны через команду python.
    pause
    exit /b 1
)

exit /b 0
