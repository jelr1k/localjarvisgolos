import { ArrowUpRight, FileText, Folder, FolderOpen, LockKeyhole, Plus, ShieldCheck } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

export function WorkspacePage() {
  const { state, dispatch } = useAppState();

  return (
    <div className="page-content workspace-page">
      <PageHeader
        eyebrow="FILES / ALIASES"
        title="Рабочая область"
        description="Здесь будет список доступных папок, документов и алиасов. Пока данные не получаются с диска."
        action={<button className="secondary-button" type="button" disabled title="Будет подключено на следующем этапе"><Plus size={15} /> Добавить ресурс</button>}
      />
      <PrototypeNotice />
      <div className="workspace-layout">
        <section className="workspace-list-card">
          <div className="panel-heading"><span><FolderOpen size={16} /> ИЗВЕСТНЫЕ РЕСУРСЫ</span><span className="demo-chip">0 ПОДКЛЮЧЕНО</span></div>
          <div className="workspace-empty">
            <span className="workspace-empty-icon"><Folder size={23} /></span>
            <h2>Рабочая область не подключена</h2>
            <p>После интеграции здесь появятся реальные каталоги и алиасы. Ничего на компьютере сейчас не сканируется.</p>
          </div>
          <div className="workspace-path-row"><Folder size={16} /><div><strong>Путь для Workspace</strong><small>{state.settings.workspace.root}</small></div><span className="path-placeholder">ПЛЕЙСХОЛДЕР</span></div>
        </section>
        <aside className="workspace-side">
          <section className="info-panel workspace-policy">
            <span className="eyebrow">ACCESS POLICY</span>
            <span className="large-panel-icon"><ShieldCheck size={22} /></span>
            <h2>{state.settings.workspace.scope === "workspace-only" ? "Только Workspace" : "Разрешённые каталоги"}</h2>
            <p>Ограничение доступа отображается здесь как настройка интерфейса. Реальные разрешения пока не применяются.</p>
            <button className="text-action" type="button" onClick={() => dispatch({ type: "navigate", page: "settings" })}>Изменить политику <ArrowUpRight size={14} /></button>
          </section>
          <section className="info-panel workspace-queue">
            <div className="panel-heading"><span><FileText size={16} /> АКТИВНОСТЬ</span><LockKeyhole size={15} /></div>
            <strong>Нет операций</strong>
            <p>Файловые операции выключены до подключения backend.</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
