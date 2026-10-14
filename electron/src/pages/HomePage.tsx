import { Activity, ArrowRight, AudioLines, Brain, ChevronRight, Command, FolderOpen, Gauge, MessageCircle, Settings2, Sparkles, Workflow } from "lucide-react";
import { useAppState } from "../app/context";
import { PageHeader } from "./PageHeader";

export function HomePage() {
  const { state, dispatch } = useAppState();
  const appName = state.settings.application.appName.trim() || "Kirieshcka v2";
  const navigate = (page: "chat" | "commands" | "workspace" | "ai" | "settings") => dispatch({ type: "navigate", page });

  return (
    <div className="page-content home-page">
      <PageHeader
        eyebrow="РАБОЧИЙ СТОЛ / LOCAL"
        title="Главная"
        description="Состояние модулей и быстрый доступ к основным инструментам."
        action={<span className="local-mode-chip"><span className="status-dot" /> ЛОКАЛЬНО</span>}
      />

      <section className="home-hero">
        <div className="hero-copy">
          <div className="hero-kicker"><span className="status-dot" /> СЕАНС / ЛОКАЛЬНЫЙ РЕЖИМ</div>
          <h2>Центр<br /><span>управления</span></h2>
          <p>Чат, локальная модель, файлы и команды. Состояние подключений видно в карточках ниже.</p>
          <div className="hero-actions">
            <button className="primary-button" type="button" onClick={() => navigate("chat")}><MessageCircle size={16} /> Открыть чат <ArrowRight size={15} /></button>
            <button className="secondary-button" type="button" onClick={() => navigate("settings")}><Settings2 size={16} /> Настроить</button>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orb-grid" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="orb-core"><span /></div>
          <div className="orb-crosshair orb-crosshair-x" />
          <div className="orb-crosshair orb-crosshair-y" />
          <div className="orb-coordinate orb-coordinate-one">K / 001</div>
          <div className="orb-coordinate orb-coordinate-two">LOCAL CORE</div>
        </div>
        <div className="hero-foot"><span>APP / {appName}</span><span>СЕРВИСЫ НЕ ПОДКЛЮЧЕНЫ</span></div>
      </section>

      <div className="section-line-heading"><span>МОДУЛИ</span><i /></div>
      <section className="overview-grid">
        <button className="overview-card" type="button" onClick={() => navigate("chat")}>
          <span className="overview-card-icon"><MessageCircle size={19} /></span>
          <span className="overview-card-title">Чат</span>
          <span className="overview-card-value">Локальный диалог</span>
          <span className="overview-card-bottom">ИИ не подключён <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("ai")}>
          <span className="overview-card-icon"><Brain size={19} /></span>
          <span className="overview-card-title">Локальный ИИ</span>
          <span className="overview-card-value">{state.settings.ai.model}</span>
          <span className="overview-card-bottom">Модель не запущена <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("workspace")}>
          <span className="overview-card-icon"><FolderOpen size={19} /></span>
          <span className="overview-card-title">Файлы</span>
          <span className="overview-card-value">Рабочие каталоги</span>
          <span className="overview-card-bottom">Доступ к диску выключен <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("commands")}>
          <span className="overview-card-icon"><Command size={19} /></span>
          <span className="overview-card-title">Команды</span>
          <span className="overview-card-value">Каталог команд</span>
          <span className="overview-card-bottom">Выполнение выключено <ChevronRight size={15} /></span>
        </button>
      </section>

      <div className="home-lower-grid">
        <section className="info-panel current-shell-panel">
          <div className="panel-heading"><span><Workflow size={16} /> ТЕКУЩИЙ РЕЖИМ</span><span className="panel-index">0{state.interfaceMode === "classic" ? "1" : "2"}</span></div>
          <strong>{state.interfaceMode === "classic" ? "Классический интерфейс" : "NEXUS Workspace"}</strong>
          <p>Параметры внешнего вида и размеры панелей.</p>
          <button className="text-action" type="button" onClick={() => navigate("settings")}>Настроить интерфейс <ArrowRight size={14} /></button>
        </section>
        <section className="info-panel quick-status-panel">
          <div className="panel-heading"><span><Activity size={16} /> СОСТОЯНИЕ СЕРВИСОВ</span><span className="not-connected"><i /> OFFLINE</span></div>
          <div className="quick-status-row"><span><AudioLines size={15} /> Голосовой модуль</span><b>Не подключён</b></div>
          <div className="quick-status-row"><span><Gauge size={15} /> Системные метрики</span><b>Нет данных</b></div>
          <div className="quick-status-row"><span><Sparkles size={15} /> Настройки</span><b>Сохранены локально</b></div>
        </section>
      </div>
    </div>
  );
}
