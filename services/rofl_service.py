from __future__ import annotations

import logging
import random
import re
from pathlib import PurePath


logger = logging.getLogger("jarvis.rofl")


class RoflService:
    """Редкие шуточные ответы после успешных действий Jarvis."""

    DEFAULT_ROFL_CHANCE = 0.12
    DEFAULT_DEMON_CHANCE = 0.15

    NORMAL_LINES = (
        "Готово, {target} открыта.",
        "Объект успешно призван.",
        "Открытие завершено. Жертва довольна.",
        "Портал в указанное приложение стабилизирован.",
        "Приложение материализовано.",
        "Дверь открыта. Не спрашивай, куда она ведёт.",
        "Дверь успешно выебана, можно пользоваться.",
        "Porta interconnexa aperta est.",
        "Ritus invocationis perfectus est.",
        "Machina evocata est.",
        "Portal apertum est.",
        "Via inter mundos aperta est.",
    )

    DEMON_LINES = (
        "Ритуал завершён. Он уже здесь.",
        "Призыв завершён. Демон получил доступ к системе.",
        "Dæmon evocatus est.",
        "Ritus perfectus est. Porta aperta est.",
        "Invocatio daemonis completa est.",
        "Invocatio daemonis completa est. Quid fecisti?",
    )

    # Заготовки для будущих прямых команд. Пока не подключены к выдаче.
    FUTURE_LINES = {
        "ollama_start": (
            ("Оллама проснулась. Лучше бы не будить.", "Сервер поднят. Теперь есть кому пожирать RAM."),
            ("Ollama experrecta est. Melius dormire debuit.", "Servitium surrexit. Nunc RAM devorabit."),
        ),
        "ollama_stop": (
            ("Оллама остановлена. RAM снова может дышать.", "Сервер уснул. Тишина продлится недолго."),
            ("Ollama sopita est. RAM respirare potest.", "Servitium dormit. Silentium diu non manebit."),
        ),
        "model_unload": (
            ("Модель выгружена. Память освобождена от цифрового паразита.", "Квен изгнан из оперативной памяти."),
            ("Exemplum e memoria expulsum est. Parasitus digitalis abiit.", "Qwen e memoria RAM expulsus est."),
        ),
    }

    ROUTER_LINES = {
        "close": (
            (
                "Приложение закрыто. Надеюсь, оно не обиделось.",
                "Закрытие прошло успешно. Ещё один процесс изгнан из мира живых.",
                "Окно закрыто. Дверь в этот мир временно запечатана.",
                "Мама Кирилла одобряет закрытие. Наверное.",
                "Приложение устранено. Следов борьбы не обнаружено.",
                "Нейросеть сказала: иди нахуй, кожаный. Приложение тоже закрыто.",
            ),
            (
                "Applicatio clausa est. Ne irascatur.",
                "Processus e mundo vivorum expulsus est.",
                "Fenestra clausa est. Porta obsignata manet.",
                "Mater Kirilli clausuram approbat. Forsitan.",
                "Applicatio eliminata est. Nulla vestigia certaminis.",
                "Neuralis dixit: abi in infernum, homo cutaneus. Applicatio clausa est.",
            ),
        ),
        "search": (
            (
                "Поиск завершён. Где-то здесь оно действительно было.",
                "Объект найден. Ритуал поиска не потребовал жертв.",
                "Найдено. Даже странно, что с первого раза.",
                "След обнаружен. Мама Кирилла может спать спокойно.",
                "Поиск завершён. Архивы реальности вскрыты.",
                "Объект найден. Деревня пока цела.",
            ),
            (
                "Quaestio perfecta est. Obiectum inventum.",
                "Vestigium inventum est. Nullum sacrificium necessarium.",
                "Inventum est. Mirum, sed ita est.",
                "Vestigium repertum est. Mater Kirilli quiescere potest.",
                "Archivum realitatis apertum est.",
                "Obiectum inventum est. Vicus adhuc integer manet.",
            ),
        ),
        "read": (
            (
                "Файл прочитан. Тайны раскрыты, психика ещё держится.",
                "Содержимое извлечено из древних письмен.",
                "Файл прочитан. Ничего страшнее ожиданий не обнаружено.",
                "Я заглянул внутрь. Теперь мы оба это знаем.",
                "Текст успешно вызван из цифрового измерения.",
                "Файл прочитан. Дверь в его содержимое закрывается.",
            ),
            (
                "Tabula lecta est. Arcana revelata sunt.",
                "Scriptum antiquum e charta digitali extractum est.",
                "Tabula lecta est. Nihil terribilius inventum.",
                "Intravi. Nunc ambo hoc scimus.",
                "Textus e dimensione digitali evocatus est.",
                "Scriptum lectum est. Porta contenti clauditur.",
            ),
        ),
        "delete": (
            (
                "Удаление завершено. Его больше нет. Наверное.",
                "Объект стёрт с лица диска.",
                "Ритуал удаления завершён. Пепел не найден.",
                "Удалено. Мама Кирилла ничего не видела.",
                "Файл уничтожен. Следующая жертва уже ожидает.",
                "Объект отправлен в цифровой небытие.",
            ),
            (
                "Deletio perfecta est. Iam non est.",
                "Obiectum e facie orbis deletum est.",
                "Ritus deletionis perfectus est. Cinis non inventus.",
                "Deletum est. Mater Kirilli nihil vidit.",
                "Tabula destructa est. Proxima victima exspectat.",
                "Obiectum in nihilum digitale missum est.",
            ),
        ),
        "status": (
            (
                "Проверка завершена. Машина признана живой.",
                "Статус получен. Оно либо работает, либо очень убедительно делает вид.",
                "Диагностика завершена. Красные флаги пока молчат.",
                "Проверка окончена. Мама Кирилла информирована. Формально.",
                "Состояние объекта установлено без вскрытия черепа.",
                "Статус проверен. Ритуал диагностики не сломал систему.",
            ),
            (
                "Inspectio perfecta est. Machina viva declaratur.",
                "Status receptus est. Aut operatur, aut bene simulatur.",
                "Diagnostica perfecta est. Vexilla rubra tacent.",
                "Inspectio finita est. Mater Kirilli certior facta est.",
                "Status obiecti sine cranio aperto determinatus est.",
                "Ritus diagnosticae systema non fregit.",
            ),
        ),
        "minimize": (
            (
                "Окно свернуто. Теперь оно прячется от налоговой.",
                "Приложение успешно уменьшено до состояния карманной вселенной.",
                "Окно исчезло. Оно не умерло, оно просто ушло в трей.",
                "Свернул. Дверь закрыта, но не заперта.",
                "Приложение отправлено в угол. Как и заслуживало.",
                "Окно свернуто. Мама Кирилла даже не заметила.",
            ),
            (
                "Fenestra reducta est. Nunc a publicano latet.",
                "Applicatio ad universum parvum redacta est.",
                "Fenestra evanuit. Non mortua est, in systray abiit.",
                "Reducitur. Porta clausa est, sed non obsignata.",
                "Applicatio in angulum missa est.",
                "Fenestra reducta est. Mater Kirilli nihil animadvertit.",
            ),
        ),
        "create_file": (
            (
                "Файл создан. Ещё один свидетель цифровой цивилизации.",
                "Новый файл материализован из пустоты.",
                "Файл создан. Теперь ему предстоит познать содержимое.",
                "Рождение файла прошло успешно. Без осложнений.",
                "Файл появился. Мама Кирилла гордится.",
                "Создание завершено. Дверь для текста открыта.",
            ),
            (
                "Tabula creata est. Alius testis civilitatis digitalis.",
                "Nova tabula e nihilo materializata est.",
                "Tabula creata est. Nunc contentum cognoscet.",
                "Nativitas tabulae perfecta est. Sine complicationibus.",
                "Tabula apparuit. Mater Kirilli superba est.",
                "Creatio perfecta est. Porta textui aperta est.",
            ),
        ),
        "create_folder": (
            (
                "Папка создана. Теперь ей есть куда складывать проблемы.",
                "Новая директория материализована.",
                "Папка создана. Пустота обрела форму.",
                "Каталог возведён. Строители требуют отпуск.",
                "Новая дверь в файловой системе готова.",
                "Папка создана. Деревня пока не сожжена.",
            ),
            (
                "Capsa creata est. Nunc problemata habet ubi ponantur.",
                "Novum directorium materializatum est.",
                "Capsa creata est. Vacuum formam accepit.",
                "Directorium erectum est. Architecti vacationem petunt.",
                "Nova porta in systemate tabularum parata est.",
                "Capsa creata est. Vicus nondum combustus est.",
            ),
        ),
        "write_file": (
            (
                "Текст записан. Теперь файл знает слишком много.",
                "Запись завершена. Чернила цифрового мира высохли.",
                "Файл успешно переписан. Старые знания уничтожены.",
                "Данные записаны. Мама Кирилла предупреждена.",
                "Текст запечатан внутри файла.",
                "Запись завершена. Дверь закрыта изнутри.",
            ),
            (
                "Textus scriptus est. Nunc tabula nimium scit.",
                "Scriptura perfecta est. Atramentum digitale siccum est.",
                "Tabula rescripta est. Scientia vetus deleta est.",
                "Data scripta sunt. Mater Kirilli certior facta est.",
                "Textus intra tabulam obsignatus est.",
                "Scriptura perfecta est. Porta ab intus clausa est.",
            ),
        ),
        "rename_file": (
            (
                "Имя изменено. Файл пережил кризис личности.",
                "Переименование завершено. Новое имя принято.",
                "Файл получил новое имя и теперь делает вид, что всегда так назывался.",
                "Старое имя изгнано. Мама Кирилла довольна.",
                "Имя изменено без жертвоприношений.",
                "Ритуал переименования завершён. Дверь открыта для новой личности.",
            ),
            (
                "Nomen mutatum est. Crisis identitatis superata.",
                "Renominatio perfecta est. Novum nomen acceptum.",
                "Tabula nomen novum accepit et semper ita fuisse simulat.",
                "Nomen vetus expulsus est. Mater Kirilli laeta est.",
                "Nomen sine sacrificio mutatum est.",
                "Ritus renominationis perfectus est. Porta novae identitati aperta.",
            ),
        ),
        "copy_file": (
            (
                "Копия создана. Теперь у файла есть двойник.",
                "Файл скопирован. Реальность стала на один экземпляр сложнее.",
                "Дубликат материализован. Оригинал пока не в курсе.",
                "Копирование завершено. Мама Кирилла подозревает размножение.",
                "Файл успешно размножен.",
                "Копия создана. Дверь между двумя экземплярами открыта.",
            ),
            (
                "Copia creata est. Tabula nunc geminum habet.",
                "Tabula copiata est. Res magis implicata facta est.",
                "Duplicatum materializatum est. Originale nihil scit.",
                "Copia perfecta est. Mater Kirilli multiplicationem suspicatur.",
                "Tabula feliciter multiplicata est.",
                "Copia creata est. Porta inter exemplaria aperta est.",
            ),
        ),
        "move_file": (
            (
                "Файл перемещён. Он сменил место жительства.",
                "Перемещение завершено. Переезд прошёл без экзорцизма.",
                "Файл доставлен в новый дом.",
                "Объект переехал. Мама Кирилла отправила адрес.",
                "Файл перенесён. Дверь в старое жилище закрыта.",
                "Переезд завершён. Курьер выжил.",
            ),
            (
                "Tabula translata est. Domum mutavit.",
                "Translatio perfecta est. Exorcismus non necessarius.",
                "Tabula in novam domum deducta est.",
                "Obiectum migravit. Mater Kirilli inscriptionem misit.",
                "Tabula translata est. Porta veteris domus clausa.",
                "Migratio perfecta est. Nuntius superstes est.",
            ),
        ),
        "file_info": (
            (
                "Информация добыта. Файл больше не может скрываться.",
                "Сведения получены из глубин файловой системы.",
                "Досье объекта раскрыто.",
                "Файл допрошен. Он всё рассказал.",
                "Информация получена. Мама Кирилла теперь в курсе.",
                "Данные извлечены. Дверь в архив закрыта.",
            ),
            (
                "Notitia recepta est. Tabula latere non potest.",
                "Informationes ex profundo systematis extractae sunt.",
                "Dossier obiecti revelatum est.",
                "Tabula interrogata est. Omnia narravit.",
                "Notitia recepta est. Mater Kirilli nunc scit.",
                "Data extracta sunt. Porta archivi clausa est.",
            ),
        ),
        "find_application": (
            (
                "Приложение найдено. Оно всё это время было здесь.",
                "Поиск приложения завершён. Жертва обнаружена.",
                "Приложение обнаружено среди обломков Windows.",
                "След приложения найден. Можно начинать охоту.",
                "Объект найден. Мама Кирилла уже зовёт его по имени.",
                "Приложение обнаружено. Ритуал поиска завершён.",
            ),
            (
                "Applicatio inventa est. Toto tempore hic erat.",
                "Quaestio applicationis perfecta est. Victima reperta.",
                "Applicatio inter ruinas Windows inventa est.",
                "Vestigium applicationis repertum est. Venatio incipit.",
                "Obiectum inventum est. Mater Kirilli iam nomen eius clamat.",
                "Applicatio inventa est. Ritus quaestionis perfectus.",
            ),
        ),
        "open_url": (
            (
                "Ссылка открыта. Дверь в интернет распахнута.",
                "URL призван из цифрового пространства.",
                "Веб-портал открыт. Надеюсь, там нет попапов.",
                "Ссылка открыта. Мама Кирилла теперь тоже может зайти.",
                "Портал стабилизирован. Интернет снова совершил ошибку.",
                "Дверь в сеть открыта. Ритуал оказался успешным.",
            ),
            (
                "Pagina aperta est. Porta interretialis patefacta.",
                "URL e spatio digitali evocatum est.",
                "Porta interretialis aperta est. Spero sine fenestris molestis.",
                "Pagina aperta est. Mater Kirilli intrare potest.",
                "Portal stabilizatus est. Interrete iterum erravit.",
                "Porta ad retia aperta est. Ritus successit.",
            ),
        ),
    }

    def __init__(self, event_bus, config=None):
        self.events = event_bus
        rofl_config = config.get("rofl", {}) if config is not None else {}
        self.rofl_chance = self._clamp_chance(
            rofl_config.get("chance", self.DEFAULT_ROFL_CHANCE),
            self.DEFAULT_ROFL_CHANCE,
        )
        self.demon_chance = self._clamp_chance(
            rofl_config.get("demon_chance", self.DEFAULT_DEMON_CHANCE),
            self.DEFAULT_DEMON_CHANCE,
        )
        event_bus.subscribe("tool.executed", self._on_tool_executed)
        event_bus.subscribe("router.rofl_candidate", self._on_router_rofl_candidate)
        event_bus.subscribe("rofl.settings_changed", self._on_settings_changed)
        logger.debug(
            "rofl_service_created chance=%.2f demon_chance=%.2f",
            self.rofl_chance,
            self.demon_chance,
        )

    @staticmethod
    def _clamp_chance(value, default):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    def _on_settings_changed(self, settings: dict):
        self.rofl_chance = self._clamp_chance(
            settings.get("chance", self.DEFAULT_ROFL_CHANCE),
            self.DEFAULT_ROFL_CHANCE,
        )
        self.demon_chance = self._clamp_chance(
            settings.get("demon_chance", self.DEFAULT_DEMON_CHANCE),
            self.DEFAULT_DEMON_CHANCE,
        )
        logger.info(
            "rofl_settings_applied chance=%.2f demon_chance=%.2f",
            self.rofl_chance,
            self.demon_chance,
        )

    @staticmethod
    def _display_target(arguments: dict, result: dict) -> str:
        target = str(arguments.get("target") or result.get("path") or "объект").strip().strip("\"'")
        if not target:
            return "объект"
        if "/" in target or "\\" in target:
            name = PurePath(target.replace("\\", "/")).name
            if name:
                return name
        return target

    @staticmethod
    def _is_failed_response(response: str) -> bool:
        text = str(response).casefold()
        return (
            text.startswith("не выполнено:")
            or text.startswith("не удалось")
            or text.startswith("не найдено")
            or text.startswith("неоднозначный")
            or "отменено" in text
            or "требуется подтверждение" in text
        )

    @staticmethod
    def _router_action(command_text: str, router=None) -> str | None:
        text = " ".join(str(command_text).casefold().split())

        # Расширенные команды проверяем первыми: например, «найди приложение»
        # иначе общий алиас «найди» ошибочно классифицируется как поиск файла.
        extended = (
            ("create_file", r"^(?:создай|создать)\s+(?:новый\s+)?файл\s+"),
            ("create_folder", r"^(?:создай|создать)\s+(?:новую\s+)?папку\s+"),
            ("write_file", r"^(?:запиши|записать|перезапиши|перезаписать)\s+"),
            ("rename_file", r"^(?:переименуй|переименовать)\s+(?:файл\s+)?"),
            ("copy_file", r"^(?:скопируй|скопировать)\s+(?:файл\s+)?"),
            ("move_file", r"^(?:перемести|переместить)\s+(?:файл\s+)?"),
            ("file_info", r"^(?:информация|сведения|свойства)\s+"),
            ("find_application", r"^(?:найди|найти)\s+(?:приложение|приложения|программу|программа)\s+"),
            ("open_url", r"^(?:открой|открыть)\s+https?://"),
        )
        for action, pattern in extended:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return action

        if router is not None:
            action = router._resolve_action(command_text)
            if action:
                return action[0]

        if re.match(r"^(?:открой|открыть|запусти|запустить|включи|включить|стартуй|стартовать|запускай|вруби|врубить)\s+", text):
            return "launch"
        if re.match(r"^(?:закрой|закрыть|останови|остановить|выключи|выключить|заверши|завершить|выруби|вырубить)\s+", text):
            return "close"
        if re.match(r"^(?:найди|найти|поищи|поискать|отыщи|отыскать|разыщи|разыскать|покажи|показать)\s+", text):
            return "search"
        if re.match(r"^(?:прочитай|прочесть|прочитать|прочти|зачитай|зачитать|озвучь|озвучить)\s+", text):
            return "read"
        if re.match(r"^(?:удали|удалить|стереть|сотри|убери|убрать)\s+", text):
            return "delete"
        if re.match(r"^(?:проверь|проверить)\s+", text):
            return "status"
        if re.match(r"^(?:сверни|свернуть|сворачивай)\s+", text):
            return "minimize"
        return None

    def maybe_router_response(self, command_text: str, response: str, router=None, action: str | None = None):
        """Иногда добавляет рофл к успешному прямому ответу CommandRouter."""
        if not response or self._is_failed_response(response):
            return
        action = action or self._router_action(command_text, router)
        if not action or action == "launch" or action not in self.ROUTER_LINES:
            return
        if random.random() >= self.rofl_chance:
            return

        normal_lines, latin_lines = self.ROUTER_LINES[action]
        lines = latin_lines if random.random() < 0.5 else normal_lines
        text = random.choice(lines)
        logger.info("router_rofl_response action=%s text=%r command=%r", action, text, command_text)
        self.events.emit("chat.rofl_response", text)

    def maybe_tool_response(self, tool_name: str, response: str):
        """Заготовка для будущих рофлов отдельных инструментов."""
        if not response or self._is_failed_response(response):
            return
        # Пока намеренно пусто: LLM-инструменты не должны случайно получать
        # те же рофлы, что и прямой CommandRouter.
        return

    def _on_router_rofl_candidate(self, command_text: str, response: str, action: str | None = None):
        self.maybe_router_response(command_text, response, action=action)

    def _on_tool_executed(self, tool_name: str, arguments: dict, result: dict):
        if tool_name != "launch_application" or not result.get("success"):
            return
        if random.random() >= self.rofl_chance:
            return

        if random.random() < self.demon_chance:
            text = random.choice(self.DEMON_LINES)
            category = "demon"
        else:
            text = random.choice(self.NORMAL_LINES).format(
                target=self._display_target(arguments, result)
            )
            category = "normal"

        logger.info(
            "rofl_response category=%s text=%r target=%r",
            category,
            text,
            arguments.get("target"),
        )
        self.events.emit("chat.rofl_response", text)

    def close(self):
        self.events.unsubscribe("tool.executed", self._on_tool_executed)
        self.events.unsubscribe("router.rofl_candidate", self._on_router_rofl_candidate)
        self.events.unsubscribe("rofl.settings_changed", self._on_settings_changed)
