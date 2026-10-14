import { SlidersHorizontal } from "lucide-react";
import { SETTING_DEFINITIONS, SETTING_GROUPS } from "../app/settingsCatalog";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { SettingsSection } from "../components/SettingsSection";
import { InterfaceTuning } from "../components/InterfaceTuning";
import { PageHeader } from "./PageHeader";

export function SettingsPage() {
  return (
    <div className="page-content settings-page">
      <PageHeader
        eyebrow="PREFERENCES / SINGLE SOURCE OF TRUTH"
        title="Настройки"
        description="Одна модель параметров для обоих интерфейсов. Изменения сразу отражаются в классическом виде и в NEXUS."
        action={<span className="page-icon-badge"><SlidersHorizontal size={20} /></span>}
      />
      <PrototypeNotice />
      <InterfaceTuning mode="classic" />
      <div className="settings-page-layout">
        <div className="settings-page-sections">
          {SETTING_GROUPS.map((group, index) => (
            <SettingsSection
              key={group.id}
              title={group.label}
              description={group.description}
              fields={SETTING_DEFINITIONS.filter((field) => field.group === group.id)}
              className={"settings-group-" + group.id}
            />
          ))}
        </div>
        <aside className="settings-summary">
          <span className="eyebrow">ARCHITECTURE NOTE</span>
          <h2>Одна модель.<br />Два способа просмотра.</h2>
          <p>Классический интерфейс показывает поля последовательно. NEXUS размещает те же поля на интерактивной карте и открывает редактор выбранного узла.</p>
          <div className="settings-summary-divider" />
          <div className="summary-metric"><span>Общие настройки</span><strong>{SETTING_DEFINITIONS.length.toString().padStart(2, "0")}</strong></div>
          <div className="summary-metric"><span>Интерфейса</span><strong>02</strong></div>
          <div className="summary-metric"><span>Backend</span><strong>OFF</strong></div>
        </aside>
      </div>
    </div>
  );
}
