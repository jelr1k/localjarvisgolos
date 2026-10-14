import { useEffect } from "react";
import { AppProvider, useAppState } from "./app/context";
import { ClassicShell } from "./layout/ClassicShell";
import { NexusShell } from "./layout/NexusShell";
import { AiPage } from "./pages/AiPage";
import { ChatPage } from "./pages/ChatPage";
import { CommandsPage } from "./pages/CommandsPage";
import { HomePage } from "./pages/HomePage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { SettingsGraph } from "./nexus/SettingsGraph";

function ActivePage() {
  const { state } = useAppState();

  switch (state.activePage) {
    case "home": return <HomePage />;
    case "chat": return <ChatPage />;
    case "commands": return <CommandsPage />;
    case "workspace": return <WorkspacePage />;
    case "ai": return <AiPage />;
    case "settings": return state.interfaceMode === "nexus" ? <SettingsGraph /> : <SettingsPage />;
  }
}

function AppLayout() {
  const { state } = useAppState();

  useEffect(() => {
    document.documentElement.dataset.theme = state.settings.appearance.theme;
    document.documentElement.dataset.density = state.settings.appearance.density;
    document.documentElement.dataset.corners = state.settings.appearance.corners;
    document.documentElement.dataset.motion = state.settings.appearance.motion;
  }, [state.settings.appearance]);

  return state.interfaceMode === "nexus"
    ? <NexusShell><ActivePage /></NexusShell>
    : <ClassicShell><ActivePage /></ClassicShell>;
}

export default function App() {
  return <AppProvider><AppLayout /></AppProvider>;
}
