import type { SettingDefinition } from "../app/settingsCatalog";
import { SettingsField } from "./SettingsField";

interface SettingsSectionProps {
  title: string;
  description?: string;
  fields: SettingDefinition[];
  compact?: boolean;
  className?: string;
}

export function SettingsSection({ title, description, fields, compact = false, className = "" }: SettingsSectionProps) {
  return (
    <section className={"settings-section-card" + (compact ? " settings-section-compact" : "") + (className ? " " + className : "")}>
      <header className="settings-section-heading">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </header>
      <div className="settings-fields">
        {fields.map((field) => <SettingsField key={field.key} field={field} compact={compact} />)}
      </div>
    </section>
  );
}
