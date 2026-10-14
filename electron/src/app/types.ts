export type InterfaceMode = "classic" | "nexus";

export type AppPage = "home" | "chat" | "commands" | "workspace" | "ai" | "settings";

export type ThemeName =
  | "dark"
  | "light"
  | "gradient-amber"
  | "gradient-blue"
  | "gradient-purple"
  | "gradient-cyan"
  | "gradient-green"
  | "gradient-red"
  | "gradient-sunset"
  | "mono-slate"
  | "mono-graphite"
  | "mono-silver"
  | "mono-cream";

export type Density = "comfortable" | "compact" | "dense";
export type Corners = "sharp" | "soft" | "round";
export type Motion = "full" | "reduced" | "off";
export type SettingGroup = "appearance" | "application" | "voice" | "workspace" | "ai" | "system";
export type SettingValue = string | boolean | number;

export type SettingKey =
  | "interfaceMode"
  | "theme"
  | "density"
  | "corners"
  | "motion"
  | "appName"
  | "assistantName"
  | "testingMode"
  | "wakeWord"
  | "microphone"
  | "silenceSeconds"
  | "workspaceRoot"
  | "workspaceScope"
  | "aiModel"
  | "aiThinking"
  | "contextTokens"
  | "temperature"
  | "language";

export interface AppSettings {
  appearance: {
    theme: ThemeName;
    density: Density;
    corners: Corners;
    motion: Motion;
  };
  application: {
    appName: string;
    assistantName: string;
    testingMode: boolean;
  };
  voice: {
    wakeWord: string;
    microphone: string;
    silenceSeconds: number;
  };
  workspace: {
    root: string;
    scope: "workspace-only" | "allow-listed";
  };
  ai: {
    model: string;
    thinking: boolean;
    contextTokens: number;
    temperature: number;
  };
  language: "ru" | "en";
}

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  text: string;
}

export interface InterfacePreferences {
  textScale: number;
  controlScale: number;
  sidebarWidth: number;
  chatWidthPercent: number;
  chatHeight: number;
  inspectorWidth: number;
  inspectorVisible: boolean;
}

export type InterfacePreferenceKey = keyof InterfacePreferences;

export interface AppState {
  interfaceMode: InterfaceMode;
  interfacePreferences: Record<InterfaceMode, InterfacePreferences>;
  activePage: AppPage;
  settings: AppSettings;
  chatInput: string;
  chatMessages: ChatMessage[];
}

export type AppAction =
  | { type: "navigate"; page: AppPage }
  | { type: "settings/update"; key: SettingKey; value: SettingValue }
  | { type: "interfacePreference/update"; mode: InterfaceMode; key: InterfacePreferenceKey; value: number | boolean }
  | { type: "chat/input"; value: string }
  | { type: "chat/send" }
  | { type: "chat/clear" };
