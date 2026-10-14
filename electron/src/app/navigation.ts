import { Brain, Command, FolderOpen, House, MessageCircle, Settings, type LucideIcon } from "lucide-react";
import type { AppPage } from "./types";

export const NAV_ITEMS: Array<{ id: AppPage; label: string; icon: LucideIcon }> = [
  { id: "home", label: "Главная", icon: House },
  { id: "chat", label: "Чат", icon: MessageCircle },
  { id: "commands", label: "Команды", icon: Command },
  { id: "workspace", label: "Рабочая область", icon: FolderOpen },
  { id: "ai", label: "ИИ", icon: Brain },
  { id: "settings", label: "Настройки", icon: Settings }
];

export function getPageLabel(page: AppPage): string {
  return NAV_ITEMS.find((item) => item.id === page)?.label ?? "Jarvis";
}
