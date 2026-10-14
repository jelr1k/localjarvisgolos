import type { ReactNode } from "react";
import { ArrowUpRight, CircleDot, Settings2, Sparkles } from "lucide-react";
import { NAV_ITEMS, getPageLabel } from "../app/navigation";
import { useAppState } from "../app/context";
import type { AppPage } from "../app/types";

interface ShellProps {
  children: ReactNode;
}

export function NexusShell({ children }: ShellProps) {
  const { state, dispatch } = useAppState();
  const navigate = (page: AppPage) => dispatch({ type: "navigate", page });

  return (
    <div className="app-frame nexus-frame">
      <header className="nexus-topbar">
        <button className="nexus-brand" type="button" onClick={() => navigate("home")} aria-label="На главную">
          <span className="nexus-brand-glyph"><Sparkles size={17} /></span>
          <span><strong>NEXUS</strong><small>JARVIS WORKSPACE</small></span>
        </button>
        <nav className="nexus-nav" aria-label="Навигация NEXUS">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} type="button" className={"nexus-nav-entry" + (state.activePage === item.id ? " is-active" : "")}
                onClick={() => navigate(item.id)} aria-current={state.activePage === item.id ? "page" : undefined}>
                <Icon size={15} /><span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="nexus-topbar-meta">
          <span className="nexus-status"><CircleDot size={12} /> LOCAL / PREVIEW</span>
          <button className="nexus-icon-button" type="button" onClick={() => navigate("settings")} title="Открыть настройки" aria-label="Открыть настройки"><Settings2 size={17} /></button>
          <span className="nexus-build-tag">UI 0.2 <ArrowUpRight size={12} /></span>
        </div>
      </header>
      <main className={"nexus-main nexus-page-" + state.activePage}>{children}</main>
      <div className="nexus-corner-note"><span className="nexus-live-dot" /> {getPageLabel(state.activePage).toUpperCase()} / СХЕМА ИНТЕРФЕЙСА</div>
    </div>
  );
}
