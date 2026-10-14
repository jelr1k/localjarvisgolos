import type { SettingGroup, SettingKey } from "./types";

export interface SettingOption {
  value: string;
  label: string;
}

export interface SettingDefinition {
  key: SettingKey;
  group: SettingGroup;
  label: string;
  description: string;
  kind: "text" | "toggle" | "select" | "number";
  options?: SettingOption[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
}

export const SETTING_GROUPS: Array<{ id: SettingGroup; label: string; description: string }> = [
  { id: "appearance", label: "Вид интерфейса", description: "Как выглядит приложение и как устроено рабочее пространство." },
  { id: "application", label: "Приложение", description: "Названия и режим работы оболочки." },
  { id: "voice", label: "Голос", description: "Параметры будущего голосового контура." },
  { id: "workspace", label: "Рабочая область", description: "Ограничения и путь к рабочим файлам." },
  { id: "ai", label: "Искусственный интеллект", description: "Выбор модели и параметры генерации." },
  { id: "system", label: "Система", description: "Язык и общие параметры отображения." }
];

export const THEME_OPTIONS: SettingOption[] = [
  { value: "dark", label: "Тёмная" },
  { value: "light", label: "Светлая" },
  { value: "gradient-amber", label: "Янтарная" },
  { value: "gradient-blue", label: "Синяя" },
  { value: "gradient-purple", label: "Фиолетовая" },
  { value: "gradient-cyan", label: "Циан" },
  { value: "gradient-green", label: "Изумрудная" },
  { value: "gradient-red", label: "Красная" },
  { value: "gradient-sunset", label: "Закат" },
  { value: "mono-slate", label: "Сланец" },
  { value: "mono-graphite", label: "Графит" },
  { value: "mono-silver", label: "Серебро" },
  { value: "mono-cream", label: "Кремовая" }
];

export const SETTING_DEFINITIONS: SettingDefinition[] = [
  {
    key: "interfaceMode", group: "appearance", label: "Оболочка",
    description: "Обычная навигация или карта настроек в стиле Obsidian.",
    kind: "select",
    options: [{ value: "classic", label: "Классический" }, { value: "nexus", label: "NEXUS" }]
  },
  {
    key: "theme", group: "appearance", label: "Цветовая тема",
    description: "Меняет цвета, не меняя расположение элементов.",
    kind: "select", options: THEME_OPTIONS
  },
  {
    key: "corners", group: "appearance", label: "Углы и рамки",
    description: "Форма карточек и полей.",
    kind: "select",
    options: [{ value: "sharp", label: "Острые" }, { value: "soft", label: "Мягкие" }, { value: "round", label: "Округлые" }]
  },
  {
    key: "motion", group: "appearance", label: "Анимация",
    description: "Обычная: заметная пульсация ядра главного экрана примерно раз в 3,2 секунды и короткие переходы. Уменьшенная: мягкая пульсация примерно раз в 8 секунд. Выключена: CSS-анимации и переходы отключены.",
    kind: "select",
    options: [{ value: "full", label: "Обычная" }, { value: "reduced", label: "Уменьшенная" }, { value: "off", label: "Выключена" }]
  },
  {
    key: "appName", group: "application", label: "Название приложения",
    description: "Название в заголовке и внутри интерфейса.",
    kind: "text"
  },
  {
    key: "assistantName", group: "application", label: "Имя ассистента",
    description: "Имя, которое отображается в сообщениях.",
    kind: "text"
  },
  {
    key: "testingMode", group: "application", label: "Режим тестирования",
    description: "В реальном приложении будет переключать режим Command Router.",
    kind: "toggle"
  },
  {
    key: "wakeWord", group: "voice", label: "Слово активации",
    description: "Фраза, после которой ассистент начинает принимать команду.",
    kind: "text"
  },
  {
    key: "microphone", group: "voice", label: "Микрофон",
    description: "Выбор устройства станет доступен после подключения голосового сервиса.",
    kind: "select",
    options: [{ value: "system", label: "Системное устройство" }, { value: "default", label: "Устройство по умолчанию" }]
  },
  {
    key: "silenceSeconds", group: "voice", label: "Тишина до отправки",
    description: "Сколько секунд тишины ждать после речи.",
    kind: "number", min: 0.3, max: 5, step: 0.1, unit: "с"
  },
  {
    key: "workspaceRoot", group: "workspace", label: "Папка Workspace",
    description: "Путь-плейсхолдер. Реальная файловая система пока не подключена.",
    kind: "text"
  },
  {
    key: "workspaceScope", group: "workspace", label: "Область доступа",
    description: "Какие каталоги будут разрешены для файловых команд.",
    kind: "select",
    options: [{ value: "workspace-only", label: "Только Workspace" }, { value: "allow-listed", label: "Разрешённые каталоги" }]
  },
  {
    key: "aiModel", group: "ai", label: "Локальная модель",
    description: "Выбранная модель для будущего подключения к Ollama.",
    kind: "select",
    options: [{ value: "qwen3:1.7b", label: "Qwen3 1.7B" }, { value: "qwen3-1.7b-no-think:latest", label: "Qwen3 1.7B без размышлений" }, { value: "qwen3:8b", label: "Qwen3 8B" }]
  },
  {
    key: "aiThinking", group: "ai", label: "Режим размышлений",
    description: "Сохраняет предпочтение в интерфейсе, но не управляет моделью на этом этапе.",
    kind: "toggle"
  },
  {
    key: "contextTokens", group: "ai", label: "Размер контекста",
    description: "Максимальный контекст модели в токенах.",
    kind: "number", min: 512, max: 40960, step: 512, unit: "токенов"
  },
  {
    key: "temperature", group: "ai", label: "Температура",
    description: "Условная настройка генерации, пока не передаётся модели.",
    kind: "number", min: 0, max: 2, step: 0.1
  },
  {
    key: "language", group: "system", label: "Язык интерфейса",
    description: "Сейчас подписи подготовлены на русском; переключение языка будет отдельным этапом.",
    kind: "select",
    options: [{ value: "ru", label: "Русский" }, { value: "en", label: "English (позже)" }]
  }
];

export function getSettingDefinition(key: SettingKey): SettingDefinition {
  const definition = SETTING_DEFINITIONS.find((item) => item.key === key);
  if (!definition) throw new Error("Неизвестная настройка: " + key);
  return definition;
}
