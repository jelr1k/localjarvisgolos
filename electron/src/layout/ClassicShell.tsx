import type { ReactNode } from "react";
import { ArrowRight, CircleHelp, Settings, Sparkles } from "lucide-react";
import { NAV_ITEMS, getPageLabel } from "../app/navigation";
import { useAppState } from "../app/context";
import type { AppPage } from "../app/types";

interface ShellProps {
  children: ReactNode;
}

export function ClassicShell({ children }: ShellProps) {
  const { state, dispatch } = useAppState();
  const navigate = (page: AppPage) => dispatch({ type: "navigate", page });

  return (
    <div className="app-frame classic-frame">
      <aside className="classic-sidebar">
        <button className="brand-lockup" type="button" onClick={() => navigate("home")} aria-label="На главную">
          <span className="brand-mark"><Sparkles size={18} /></span>
          <span className="brand-copy">
            <strong>{state.settings.application.appName || "JARVIS"}</strong>
            <small>ЛОКАЛЬНЫЙ АССИСТЕНТ</small>
          </span>
        </button>
        <div className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav className="classic-nav" aria-label="Основная навигация">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className={"nav-entry" + (state.activePage === item.id ? " is-active" : "")}
                onClick={() => navigate(item.id)}
                aria-current={state.activePage === item.id ? "page" : undefined}
              >
                <Icon size={17} strokeWidth={1.8} />
                <span>{item.label}</span>
                {state.activePage === item.id && <ArrowRight className="nav-entry-arrow" size={14} />}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-state"><span className="status-dot" /><span>UI / сервисы отключены</span></div>
          <button className="sidebar-help" type="button" onClick={() => navigate("settings")}>
            <Settings size={16} /><span>Параметры оболочки</span><CircleHelp size={14} className="muted-icon" />
          </button>
          <div className="sidebar-version"><span>JARVIS UI</span><span>0.2 · preview</span></div>
        </div>
      </aside>
      <main className="classic-main">
        <header className="classic-topbar">
          <div className="breadcrumbs"><span>JARVIS</span><span className="breadcrumb-separator">/</span><strong>{getPageLabel(state.activePage)}</strong></div>
          <div className="topbar-actions">
            <span className="preview-pill"><span /> ПРЕДПРОСМОТР</span>
            <button className="icon-button" type="button" onClick={() => navigate("settings")} title="Настройки" aria-label="Настройки"><Settings size={18} /></button>
          </div>
        </header>
        <div className="classic-content">{children}</div>
      </main>
    </div>
  );
}
