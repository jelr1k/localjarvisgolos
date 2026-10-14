import { useAppState } from "../app/context";
import { getSettingValue } from "../app/state";
import type { SettingDefinition } from "../app/settingsCatalog";

interface SettingsFieldProps {
  field: SettingDefinition;
  compact?: boolean;
}

export function SettingsField({ field, compact = false }: SettingsFieldProps) {
  const { state, dispatch } = useAppState();
  const value = getSettingValue(state, field.key);
  const update = (nextValue: string | boolean | number) => {
    dispatch({ type: "settings/update", key: field.key, value: nextValue });
  };

  return (
    <div className={"setting-field" + (compact ? " setting-field-compact" : "")}>
      <div className="setting-field-copy">
        <label htmlFor={"setting-" + field.key}>{field.label}</label>
        <p>{field.description}</p>
      </div>
      <div className="setting-field-control">
        {field.kind === "select" && (
          <select
            id={"setting-" + field.key}
            value={String(value)}
            onChange={(event) => update(event.currentTarget.value)}
          >
            {(field.options ?? []).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        )}
        {field.kind === "text" && (
          <input
            id={"setting-" + field.key}
            type="text"
            value={String(value)}
            onChange={(event) => update(event.currentTarget.value)}
            spellCheck={false}
          />
        )}
        {field.kind === "number" && (
          <div className="number-control">
            <input
              id={"setting-" + field.key}
              type="number"
              value={Number(value)}
              min={field.min}
              max={field.max}
              step={field.step}
              onChange={(event) => {
                if (event.currentTarget.value !== "") update(Number(event.currentTarget.value));
              }}
            />
            {field.unit && <span>{field.unit}</span>}
          </div>
        )}
        {field.kind === "toggle" && (
          <button
            id={"setting-" + field.key}
            type="button"
            className={"toggle-control" + (value ? " is-on" : "")}
            role="switch"
            aria-checked={Boolean(value)}
            aria-label={field.label}
            onClick={() => update(!Boolean(value))}
          >
            <span />
          </button>
        )}
      </div>
    </div>
  );
}
