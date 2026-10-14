import { Activity, ArrowRight, AudioLines, Brain, ChevronRight, Command, FolderOpen, Gauge, MessageCircle, Settings2, Sparkles, Workflow } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

export function HomePage() {
  const { state, dispatch } = useAppState();
  const navigate = (page: "chat" | "commands" | "workspace" | "ai" | "settings") => dispatch({ type: "navigate", page });

  return (
    <div className="page-content home-page">
      <PageHeader
        eyebrow="LOCAL ASSISTANT / OVERVIEW"
        title="Рабочее пространство"
        description="Основная точка входа в Jarvis. Выбранное оформление меняет способ работы с теми же настройками."
        action={<span className="page-index">01 <span>/ 06</span></span>}
      />
      <PrototypeNotice />

      <section className="home-hero">
        <div className="hero-copy">
          <div className="hero-kicker"><span className="status-dot" /> ИНТЕРФЕЙСНЫЙ ПРОТОТИП</div>
          <h2>Твой компьютер.<br /><span>Твои правила.</span></h2>
          <p>Jarvis объединит команды, локальный ИИ, голос и рабочую область в одном приложении. Сейчас здесь перестраивается оболочка, сервисы подключаются отдельно.</p>
          <div className="hero-actions">
            <button className="primary-button" type="button" onClick={() => navigate("chat")}><MessageCircle size={16} /> Открыть чат <ArrowRight size={15} /></button>
            <button className="secondary-button" type="button" onClick={() => navigate("settings")}><Settings2 size={16} /> Настройки</button>
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
          <div className="orb-coordinate orb-coordinate-one">J / 001</div>
          <div className="orb-coordinate orb-coordinate-two">LOCAL CORE</div>
        </div>
        <div className="hero-foot"><span>ASSISTANT / {state.settings.application.assistantName || "JARVIS"}</span><span>СЕРВИСЫ НЕ ПОДКЛЮЧЕНЫ</span></div>
      </section>

      <div className="section-line-heading"><span>ОБЛАСТИ ПРИЛОЖЕНИЯ</span><i /></div>
      <section className="overview-grid">
        <button className="overview-card" type="button" onClick={() => navigate("chat")}>
          <span className="overview-card-icon"><MessageCircle size={19} /></span>
          <span className="overview-card-title">Чат и команды</span>
          <span className="overview-card-value">Макет взаимодействия</span>
          <span className="overview-card-bottom">Диалог не отправляется в ИИ <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("ai")}>
          <span className="overview-card-icon"><Brain size={19} /></span>
          <span className="overview-card-title">Локальный ИИ</span>
          <span className="overview-card-value">{state.settings.ai.model}</span>
          <span className="overview-card-bottom">Модель не загружалась <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("workspace")}>
          <span className="overview-card-icon"><FolderOpen size={19} /></span>
          <span className="overview-card-title">Рабочая область</span>
          <span className="overview-card-value">Файлы и алиасы</span>
          <span className="overview-card-bottom">Файловый сервис отключён <ChevronRight size={15} /></span>
        </button>
        <button className="overview-card" type="button" onClick={() => navigate("commands")}>
          <span className="overview-card-icon"><Command size={19} /></span>
          <span className="overview-card-title">Команды</span>
          <span className="overview-card-value">Каталог примеров</span>
          <span className="overview-card-bottom">Не выполняются из макета <ChevronRight size={15} /></span>
        </button>
      </section>

      <div className="home-lower-grid">
        <section className="info-panel current-shell-panel">
          <div className="panel-heading"><span><Workflow size={16} /> ТЕКУЩАЯ ОБОЛОЧКА</span><span className="panel-index">UI / 0{state.interfaceMode === "classic" ? "1" : "2"}</span></div>
          <strong>{state.interfaceMode === "classic" ? "Классический интерфейс" : "NEXUS Workspace"}</strong>
          <p>{state.interfaceMode === "classic" ? "Привычная боковая навигация и последовательные формы настроек." : "Рабочая область с узлами и связями. Каждый узел управляет теми же настройками."}</p>
          <button className="text-action" type="button" onClick={() => navigate("settings")}>Изменить оболочку <ArrowRight size={14} /></button>
        </section>
        <section className="info-panel quick-status-panel">
          <div className="panel-heading"><span><Activity size={16} /> СТАТУС ПРОЕКТА</span><span className="demo-chip">DEMO DATA</span></div>
          <div className="quick-status-row"><span><AudioLines size={15} /> Голосовой контур</span><b>Не подключён</b></div>
          <div className="quick-status-row"><span><Gauge size={15} /> Системные метрики</span><b>Нет источника</b></div>
          <div className="quick-status-row"><span><Sparkles size={15} /> Хранилище настроек</span><b>Локальное</b></div>
        </section>
      </div>
    </div>
  );
}
