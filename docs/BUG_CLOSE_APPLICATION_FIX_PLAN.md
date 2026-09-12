# План исправления `close_application`

## Цель

Исправить архитектуру управления приложениями так, чтобы Jarvis мог надёжно определить реальный процесс приложения по его пользовательскому имени, ярлыку или исполняемому файлу.

Текущая проблема на примере Prism Launcher: поиск приложения через `find_application()` работает, но `close_application()` повторно пытается найти процесс по строке `Prism Launcher`. Имя ярлыка приложения и имя реального процесса не обязаны совпадать.

## Целевая архитектура

```text
User command
    ↓
Command Router
    ↓
close_application("Prism Launcher")
    ↓
Application Resolver
    ↓
Application Identity
    ├── display name
    ├── shortcut path
    ├── target executable
    └── normalized identifiers
    ↓
Process Resolver
    ↓
Running process
    ↓
Graceful terminate
    ↓
Verification
    ↓
Tool result
```

## 1. Реализовать разрешение Windows `.lnk`

Добавить универсальный механизм, который по найденному `.lnk` определяет:

- target executable;
- рабочую директорию, если она нужна для идентификации;
- аргументы запуска, если они нужны;
- нормализованный путь к executable.

Не следует считать имя `.lnk` именем процесса.

## 2. Создать единый Application Resolver

Нужен общий внутренний resolver, который принимает пользовательское имя приложения и возвращает нормализованную информацию о нём.

Пример:

```text
"Prism Launcher"
        ↓
Prism Launcher.lnk
        ↓
<target executable>
        ↓
Application Identity
```

Resolver должен уметь работать как минимум с:

- `.lnk`;
- `.exe`;
- приложениями, найденными через PATH;
- уже известными путями из существующей логики `find_application()`.

## 3. Создать Process Resolver

На основании Application Identity нужно определять реально запущенный процесс.

Приоритет проверки должен быть примерно таким:

1. точное совпадение полного пути executable;
2. нормализованное совпадение executable;
3. дополнительные надёжные признаки, если они нужны конкретному типу приложения;
4. имя процесса как fallback, а не как единственный источник истины.

Нельзя считать отсутствие процесса с именем display name доказательством того, что приложение не запущено.

## 4. Переписать `close_application`

`close_application()` должен использовать общий Application Resolver + Process Resolver.

Целевая последовательность:

```text
resolve application
    ↓
resolve process
    ↓
if process absent:
    return already_closed
    ↓
terminate process
    ↓
wait/check
    ↓
verify process exited
    ↓
return success
```

## 5. Переписать `get_process_status`

`get_process_status()` должен использовать тот же resolver, чтобы статус приложения определялся тем же способом, что и закрытие.

Это предотвращает ситуацию, когда Jarvis говорит, что приложение не запущено, а `close_application()` при тех же условиях ведёт себя иначе.

## 6. Проверять результат завершения

После `terminate()` нельзя сразу считать операцию успешной.

Нужно:

- дождаться завершения процесса с разумным timeout;
- проверить, что процесс действительно исчез;
- отдельно обработать `AccessDenied`, `NoSuchProcess` и timeout;
- вернуть структурированный результат.

Пример результата:

```json
{
  "success": true,
  "running": false,
  "closed": [12345]
}
```

## 7. Идемпотентность

Если приложение уже не запущено, это не обязательно ошибка инструмента.

Рекомендуемое поведение:

```text
Prism Launcher уже закрыт.
```

Внутренний результат при этом может иметь `success=true`, `running=false` и отдельный признак `already_closed`.

## 8. Тесты

Добавить тестовые сценарии:

### Сценарий A: имя ярлыка совпадает с executable

Проверить обычный случай.

### Сценарий B: имя ярлыка отличается от executable

Например:

```text
Display name: Prism Launcher
Shortcut: Prism Launcher.lnk
Executable: другое_имя.exe
```

`close_application("Prism Launcher")` должен найти процесс.

### Сценарий C: приложение уже закрыто

Операция должна вернуть корректный статус `already_closed`, а не ложную ошибку поиска процесса.

### Сценарий D: процесс найден, но завершение не произошло

Проверить timeout/error path.

### Сценарий E: несколько процессов

Проверить, что resolver не завершает посторонние процессы только из-за похожего имени.

## 9. Проверка Prism Launcher

После реализации обязательно протестировать реальный сценарий на Windows:

```text
Запустить Prism Launcher
↓
Jarvis: "Закрой Prism Launcher"
↓
найти `.lnk`
↓
разрешить target
↓
найти реальный процесс
↓
закрыть
↓
проверить отсутствие процесса
```

## 10. Не делать частный hardcode первым решением

Не решать проблему только через таблицу:

```text
Prism Launcher → prismlauncher.exe
Discord → Discord.exe
```

Такой mapping может быть полезным fallback для редких случаев, но основным механизмом должен быть универсальный resolver.

## 11. Критерии готовности

Исправление считается завершённым, если:

- `find_application()` продолжает находить приложение;
- `.lnk` корректно разрешается в target;
- `close_application()` больше не предполагает, что display name = process name;
- `get_process_status()` использует ту же модель идентификации;
- результат `terminate()` проверяется;
- уже закрытое приложение обрабатывается корректно;
- добавлены автоматические тесты;
- Prism Launcher успешно закрывается реальным Jarvis-командным сценарием на Windows.
