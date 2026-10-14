import { describe, expect, it } from "vitest";
import { appReducer, createInitialState } from "./state";

describe("shared UI state", () => {
  it("uses the selected application name as the default identity", () => {
    const initial = createInitialState();
    expect(initial.settings.application.appName).toBe("Kirieshcka v2");
    expect(initial.settings.application.assistantName).toBe("Kirieshcka v2");
  });

  it("switches only between the supported Classic and NEXUS views", () => {
    const initial = createInitialState();
    const next = appReducer(initial, { type: "settings/update", key: "interfaceMode", value: "nexus" });
    expect(next.interfaceMode).toBe("nexus");
    expect(next.settings).toEqual(initial.settings);
    expect(next.activePage).toBe("home");
  });

  it("updates a setting that both interfaces read from the same model", () => {
    const initial = createInitialState();
    const next = appReducer(initial, { type: "settings/update", key: "assistantName", value: "Джелрик" });
    expect(next.settings.application.assistantName).toBe("Джелрик");
    expect(next.interfaceMode).toBe("classic");
  });

  it("keeps interface sizing independent and clamps unsafe values", () => {
    const initial = createInitialState();
    const scaled = appReducer(initial, { type: "interfacePreference/update", mode: "classic", key: "textScale", value: 145 });
    const resized = appReducer(scaled, { type: "interfacePreference/update", mode: "classic", key: "sidebarWidth", value: 40 });

    expect(resized.interfacePreferences.classic.textScale).toBe(145);
    expect(resized.interfacePreferences.classic.sidebarWidth).toBe(180);
    expect(resized.interfacePreferences.nexus.textScale).toBe(100);
    expect(initial.interfacePreferences.classic.textScale).toBe(100);
  });

  it("rounds interface scales to whole numbers and keeps NEXUS minimap visibility independent", () => {
    const initial = createInitialState();
    const scaled = appReducer(initial, { type: "interfacePreference/update", mode: "nexus", key: "textScale", value: 117.25 });
    const spaced = appReducer(scaled, { type: "interfacePreference/update", mode: "nexus", key: "spacingScale", value: 123.5 });
    const hidden = appReducer(spaced, { type: "interfacePreference/update", mode: "nexus", key: "minimapVisible", value: false });

    expect(hidden.interfacePreferences.nexus.textScale).toBe(117);
    expect(hidden.interfacePreferences.nexus.spacingScale).toBe(124);
    expect(hidden.interfacePreferences.nexus.minimapVisible).toBe(false);
    expect(hidden.interfacePreferences.classic.minimapVisible).toBe(true);
  });

  it("keeps demo chat messages local and marks the reply as non-integrated", () => {
    const initial = appReducer(createInitialState(), { type: "chat/input", value: "Открой браузер" });
    const next = appReducer(initial, { type: "chat/send" });
    expect(next.chatMessages).toHaveLength(2);
    expect(next.chatMessages[0].role).toBe("user");
    expect(next.chatMessages[1].text).toContain("подключение к ИИ");
    expect(next.chatInput).toBe("");
  });

  it("does not add a chat message for whitespace-only input", () => {
    const initial = appReducer(createInitialState(), { type: "chat/input", value: "   " });
    expect(appReducer(initial, { type: "chat/send" })).toBe(initial);
  });
});
