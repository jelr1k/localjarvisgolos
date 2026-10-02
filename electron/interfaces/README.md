# Интерфейсы Jarvis

Интерфейсы делятся на два режима.

- **shared** использует существующие страницы и общий CSS. Такой интерфейс можно менять без перезапуска.
- **custom** может иметь собственные CSS/JS и отдельную структуру страниц. Для таких интерфейсов ставится requiresRestart: true.

## Добавление сложного интерфейса

В electron/interface-manager.js добавляется запись:

    myinterface: {
      mode: "custom",
      requiresRestart: true,
      css: "interfaces/myinterface/interface.css",
      js: "interfaces/myinterface/interface.js"
    }

Структура:

    electron/interfaces/myinterface/
    ├── interface.css
    ├── interface.js
    └── pages/
        ├── home.html
        ├── chat.html
        ├── commands.html
        ├── workspace.html
        ├── ai.html
        └── settings.html

Общий функциональный слой Jarvis при этом не нужно копировать. Новый интерфейс может использовать те же данные, события и IPC, меняя только представление.

## Применение

1. Пользователь выбирает интерфейс.
2. Выбор остаётся в состоянии pending.
3. «Сохранить всё» применяет shared-интерфейс сразу.
4. Для requiresRestart: true появляется подтверждение.
5. После подтверждения настройка сохраняется, Electron перезапускается, и интерфейс загружается заново.
