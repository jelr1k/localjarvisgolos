import { useRef, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import { ArrowRight, CircleHelp, Settings, Sparkles } from "lucide-react";
import { NAV_ITEMS, getPageLabel } from "../app/navigation";
import { useAppState } from "../app/context";
import type { AppPage } from "../app/types";

interface ShellProps {
  children: ReactNode;
}

export function ClassicShell({ children }: ShellProps) {
  const { state, dispatch } = useAppState();
  const preferences = state.interfacePreferences.classic;
  const resizeStart = useRef<{ pointerId: number; startX: number; startWidth: number } | null>(null);
  const navigate = (page: AppPage) => dispatch({ type: "navigate", page });

  return (
    <div className="app-frame classic-frame" style={{ "--classic-sidebar-width": `${preferences.sidebarWidth}px` } as CSSProperties}>
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
      <div
        className="classic-resize-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Изменить ширину боковой панели"
        aria-valuemin={180}
        aria-valuemax={360}
        aria-valuenow={preferences.sidebarWidth}
        tabIndex={0}
        onPointerDown={(event: PointerEvent<HTMLDivElement>) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          resizeStart.current = { pointerId: event.pointerId, startX: event.clientX, startWidth: preferences.sidebarWidth };
        }}
        onPointerMove={(event: PointerEvent<HTMLDivElement>) => {
          const start = resizeStart.current;
          if (!start || start.pointerId !== event.pointerId) return;
          const width = Math.min(360, Math.max(180, Math.round(start.startWidth + event.clientX - start.startX)));
          dispatch({ type: "interfacePreference/update", mode: "classic", key: "sidebarWidth", value: width });
        }}
        onPointerUp={(event: PointerEvent<HTMLDivElement>) => {
          if (resizeStart.current?.pointerId === event.pointerId) resizeStart.current = null;
        }}
        onPointerCancel={() => { resizeStart.current = null; }}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            const delta = event.key === "ArrowRight" ? 10 : -10;
            dispatch({ type: "interfacePreference/update", mode: "classic", key: "sidebarWidth", value: preferences.sidebarWidth + delta });
          }
        }}
      />
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
