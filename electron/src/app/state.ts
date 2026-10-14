import { THEME_OPTIONS } from "./settingsCatalog";
import type { AppAction, AppSettings, AppState, InterfaceMode, InterfacePreferences, SettingKey, SettingValue, ThemeName } from "./types";

export const STORAGE_KEY = "jarvis-ui-preferences-v2";

export const DEFAULT_INTERFACE_PREFERENCES: Record<InterfaceMode, InterfacePreferences> = {
  classic: { textScale: 100, controlScale: 100, spacingScale: 100, sidebarWidth: 236, chatWidthPercent: 100, chatHeight: 620, inspectorWidth: 322, inspectorVisible: true, minimapVisible: true },
  nexus: { textScale: 100, controlScale: 100, spacingScale: 100, sidebarWidth: 236, chatWidthPercent: 100, chatHeight: 620, inspectorWidth: 322, inspectorVisible: true, minimapVisible: true }
};

export const DEFAULT_SETTINGS: AppSettings = {
  appearance: {
    theme: "mono-graphite",
    density: "comfortable",
    corners: "sharp",
    motion: "full"
  },
  application: {
    appName: "Kirieshcka v2",
    assistantName: "Kirieshcka v2",
    testingMode: false
  },
  voice: {
    wakeWord: "шпрота",
    microphone: "system",
    silenceSeconds: 1.2
  },
  workspace: {
    root: "Папка ещё не подключена",
    scope: "workspace-only"
  },
  ai: {
    model: "qwen3:1.7b",
    thinking: false,
    contextTokens: 4096,
    temperature: 0.7
  },
  language: "ru"
};

export function createInitialState(): AppState {
  return {
    interfaceMode: "classic",
    interfacePreferences: structuredClone(DEFAULT_INTERFACE_PREFERENCES),
    activePage: "home",
    settings: structuredClone(DEFAULT_SETTINGS),
    chatInput: "",
    chatMessages: []
  };
}

function isInterfaceMode(value: unknown): value is InterfaceMode {
  return value === "classic" || value === "nexus";
}

function isThemeName(value: unknown): value is ThemeName {
  return typeof value === "string" && THEME_OPTIONS.some((option) => option.value === value);
}

function mergeStoredSettings(rawValue: unknown): AppSettings {
  if (!rawValue || typeof rawValue !== "object") return structuredClone(DEFAULT_SETTINGS);
  const raw = rawValue as Partial<AppSettings>;
  const appearance: Partial<AppSettings["appearance"]> = raw.appearance && typeof raw.appearance === "object" ? raw.appearance : {};
  const application: Partial<AppSettings["application"]> = raw.application && typeof raw.application === "object" ? raw.application : {};
  const voice: Partial<AppSettings["voice"]> = raw.voice && typeof raw.voice === "object" ? raw.voice : {};
  const workspace: Partial<AppSettings["workspace"]> = raw.workspace && typeof raw.workspace === "object" ? raw.workspace : {};
  const ai: Partial<AppSettings["ai"]> = raw.ai && typeof raw.ai === "object" ? raw.ai : {};
  const normalizeLegacyName = (value: unknown, fallback: string) => {
    if (typeof value !== "string" || value.trim() === "" || value.trim().toLowerCase() === "jarvis") return fallback;
    return value.trim();
  };

  return {
    appearance: {
      ...DEFAULT_SETTINGS.appearance,
      ...appearance,
      theme: isThemeName(appearance.theme) ? appearance.theme : DEFAULT_SETTINGS.appearance.theme
    },
    application: {
      ...DEFAULT_SETTINGS.application,
      ...application,
      appName: normalizeLegacyName(application.appName, DEFAULT_SETTINGS.application.appName),
      assistantName: normalizeLegacyName(application.assistantName, DEFAULT_SETTINGS.application.assistantName)
    },
    voice: { ...DEFAULT_SETTINGS.voice, ...voice },
    workspace: { ...DEFAULT_SETTINGS.workspace, ...workspace },
    ai: { ...DEFAULT_SETTINGS.ai, ...ai },
    language: raw.language === "en" ? "en" : "ru"
  };
}

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.round(Math.min(max, Math.max(min, value)));
}

function mergeInterfacePreferences(rawValue: unknown): Record<InterfaceMode, InterfacePreferences> {
  const merged = structuredClone(DEFAULT_INTERFACE_PREFERENCES);
  if (!rawValue || typeof rawValue !== "object") return merged;

  const raw = rawValue as Partial<Record<InterfaceMode, Partial<InterfacePreferences>>>;
  for (const mode of ["classic", "nexus"] as InterfaceMode[]) {
    const candidate = raw[mode];
    if (!candidate || typeof candidate !== "object") continue;
    merged[mode] = {
      textScale: clampNumber(candidate.textScale, merged[mode].textScale, 80, 160),
      controlScale: clampNumber(candidate.controlScale, merged[mode].controlScale, 80, 160),
      spacingScale: clampNumber(candidate.spacingScale, merged[mode].spacingScale, 70, 150),
      sidebarWidth: clampNumber(candidate.sidebarWidth, merged[mode].sidebarWidth, 180, 360),
      chatWidthPercent: clampNumber(candidate.chatWidthPercent, merged[mode].chatWidthPercent, 45, 100),
      chatHeight: clampNumber(candidate.chatHeight, merged[mode].chatHeight, 360, 900),
      inspectorWidth: clampNumber(candidate.inspectorWidth, merged[mode].inspectorWidth, 240, 480),
      inspectorVisible: typeof candidate.inspectorVisible === "boolean" ? candidate.inspectorVisible : merged[mode].inspectorVisible,
      minimapVisible: typeof candidate.minimapVisible === "boolean" ? candidate.minimapVisible : merged[mode].minimapVisible
    };
  }
  return merged;
}

export function loadInitialState(): AppState {
  const fallback = createInitialState();
  if (typeof window === "undefined") return fallback;

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as { interfaceMode?: unknown; settings?: unknown; interfacePreferences?: unknown };
      return {
        ...fallback,
        interfaceMode: isInterfaceMode(parsed.interfaceMode) ? parsed.interfaceMode : "classic",
        interfacePreferences: mergeInterfacePreferences(parsed.interfacePreferences),
        settings: mergeStoredSettings(parsed.settings)
      };
    }

    const legacyInterface = window.localStorage.getItem("jarvis-interface");
    const legacyTheme = window.localStorage.getItem("jarvis-theme");
    return {
      ...fallback,
      interfaceMode: isInterfaceMode(legacyInterface) ? legacyInterface : "classic",
      settings: {
        ...fallback.settings,
        appearance: {
          ...fallback.settings.appearance,
          theme: isThemeName(legacyTheme) ? legacyTheme : fallback.settings.appearance.theme
        }
      }
    };
  } catch {
    return fallback;
  }
}

export function getSettingValue(state: AppState, key: SettingKey): SettingValue {
  switch (key) {
    case "interfaceMode": return state.interfaceMode;
    case "theme": return state.settings.appearance.theme;
    case "density": return state.settings.appearance.density;
    case "corners": return state.settings.appearance.corners;
    case "motion": return state.settings.appearance.motion;
    case "appName": return state.settings.application.appName;
    case "assistantName": return state.settings.application.assistantName;
    case "testingMode": return state.settings.application.testingMode;
    case "wakeWord": return state.settings.voice.wakeWord;
    case "microphone": return state.settings.voice.microphone;
    case "silenceSeconds": return state.settings.voice.silenceSeconds;
    case "workspaceRoot": return state.settings.workspace.root;
    case "workspaceScope": return state.settings.workspace.scope;
    case "aiModel": return state.settings.ai.model;
    case "aiThinking": return state.settings.ai.thinking;
    case "contextTokens": return state.settings.ai.contextTokens;
    case "temperature": return state.settings.ai.temperature;
    case "language": return state.settings.language;
  }
}

function updateNestedSetting(settings: AppSettings, key: SettingKey, value: SettingValue): AppSettings {
  switch (key) {
    case "theme": return { ...settings, appearance: { ...settings.appearance, theme: value as ThemeName } };
    case "density": return { ...settings, appearance: { ...settings.appearance, density: value as AppSettings["appearance"]["density"] } };
    case "corners": return { ...settings, appearance: { ...settings.appearance, corners: value as AppSettings["appearance"]["corners"] } };
    case "motion": return { ...settings, appearance: { ...settings.appearance, motion: value as AppSettings["appearance"]["motion"] } };
    case "appName": return { ...settings, application: { ...settings.application, appName: String(value) } };
    case "assistantName": return { ...settings, application: { ...settings.application, assistantName: String(value) } };
    case "testingMode": return { ...settings, application: { ...settings.application, testingMode: Boolean(value) } };
    case "wakeWord": return { ...settings, voice: { ...settings.voice, wakeWord: String(value) } };
    case "microphone": return { ...settings, voice: { ...settings.voice, microphone: String(value) } };
    case "silenceSeconds": return { ...settings, voice: { ...settings.voice, silenceSeconds: Number(value) } };
    case "workspaceRoot": return { ...settings, workspace: { ...settings.workspace, root: String(value) } };
    case "workspaceScope": return { ...settings, workspace: { ...settings.workspace, scope: value as AppSettings["workspace"]["scope"] } };
    case "aiModel": return { ...settings, ai: { ...settings.ai, model: String(value) } };
    case "aiThinking": return { ...settings, ai: { ...settings.ai, thinking: Boolean(value) } };
    case "contextTokens": return { ...settings, ai: { ...settings.ai, contextTokens: Number(value) } };
    case "temperature": return { ...settings, ai: { ...settings.ai, temperature: Number(value) } };
    case "language": return { ...settings, language: value === "en" ? "en" : "ru" };
    case "interfaceMode": return settings;
  }
}

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "navigate":
      return { ...state, activePage: action.page };
    case "settings/update":
      if (action.key === "interfaceMode") {
        return { ...state, interfaceMode: action.value === "nexus" ? "nexus" : "classic" };
      }
      return { ...state, settings: updateNestedSetting(state.settings, action.key, action.value) };
    case "interfacePreference/update": {
      const current = state.interfacePreferences[action.mode];
      let value: number | boolean = action.value;
      if (action.key === "inspectorVisible" || action.key === "minimapVisible") {
        value = Boolean(action.value);
      } else {
        const limits: Record<Exclude<keyof InterfacePreferences, "inspectorVisible" | "minimapVisible">, [number, number]> = {
          textScale: [80, 160],
          controlScale: [80, 160],
          spacingScale: [70, 150],
          sidebarWidth: [180, 360],
          chatWidthPercent: [45, 100],
          chatHeight: [360, 900],
          inspectorWidth: [240, 480]
        };
        const [min, max] = limits[action.key as Exclude<keyof InterfacePreferences, "inspectorVisible" | "minimapVisible">];
        const numeric = Number(action.value);
        value = Number.isFinite(numeric) ? Math.round(Math.min(max, Math.max(min, numeric))) : current[action.key] as number;
      }
      return {
        ...state,
        interfacePreferences: {
          ...state.interfacePreferences,
          [action.mode]: { ...current, [action.key]: value }
        }
      };
    }
    case "chat/input":
      return { ...state, chatInput: action.value };
    case "chat/clear":
      return { ...state, chatMessages: [], chatInput: "" };
    case "chat/send": {
      const text = state.chatInput.trim();
      if (!text) return state;
      const prefix = Date.now().toString() + "-" + state.chatMessages.length;
      return {
        ...state,
        chatInput: "",
        chatMessages: [
          ...state.chatMessages,
          { id: "user-" + prefix, role: "user", text },
          {
            id: "assistant-" + prefix,
            role: "assistant",
            text: "Сообщение осталось внутри макета. На этом этапе подключение к ИИ и выполнение команд отключены."
          }
        ]
      };
    }
  }
}
