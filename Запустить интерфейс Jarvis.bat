@echo off
setlocal EnableExtensions
chcp 65001 >nul
title JARVIS UI - проверка

echo.
echo  ==========================================
echo   JARVIS UI ^| режим проверки интерфейса
echo  ==========================================
echo.

where node >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Node.js не найден.
    echo Установи Node.js LTS с https://nodejs.org/ и запусти этот файл снова.
    goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] npm не найден. Переустанови Node.js LTS.
    goto :fail
)

cd /d "%~dp0electron"
if errorlevel 1 (
    echo [ОШИБКА] Папка electron не найдена рядом с этим батником.
    goto :fail
)

if not exist "package.json" (
    echo [ОШИБКА] Не найден electron\package.json.
    goto :fail
)

if not exist "node_modules" (
    echo [ИНФО] Первый запуск: устанавливаю зависимости...
    call npm install
    if errorlevel 1 (
        echo [ОШИБКА] Не получилось установить зависимости.
        goto :fail
    )
)

echo [ИНФО] Запускаю интерфейс Jarvis...
echo [ИНФО] Для остановки закрой окно этого батника.
echo.
call npm run dev
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ОШИБКА] Интерфейс завершился с кодом %EXIT_CODE%.
    goto :fail
)

echo.
echo Интерфейс завершил работу.
goto :end

:fail
echo.
echo Проверь сообщения выше. Если нужна помощь, приложи скрин этого окна.
echo.
pause
exit /b 1

:end
pause
exit /b 0
