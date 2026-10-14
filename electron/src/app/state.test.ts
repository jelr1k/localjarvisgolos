import { describe, expect, it } from "vitest";
import { appReducer, createInitialState } from "./state";

describe("shared UI state", () => {
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
