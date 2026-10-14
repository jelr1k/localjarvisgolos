import { useEffect, useState } from "react";
import { Eye, EyeOff, PanelRight, RotateCcw } from "lucide-react";
import { useAppState } from "../app/context";
import type { InterfaceMode, InterfacePreferenceKey, InterfacePreferences } from "../app/types";

interface InterfaceTuningProps {
  mode: InterfaceMode;
  compact?: boolean;
}

type NumericPreferenceKey = Exclude<InterfacePreferenceKey, "inspectorVisible" | "minimapVisible">;

const DEFAULTS: InterfacePreferences = {
  textScale: 100,
  controlScale: 100,
  spacingScale: 100,
  sidebarWidth: 236,
  chatWidthPercent: 100,
  chatHeight: 620,
  inspectorWidth: 322,
  inspectorVisible: true,
  minimapVisible: true
};

interface RangeSettingProps {
  prefKey: NumericPreferenceKey;
  label: string;
  min: number;
  max: number;
  unit: string;
  value: number;
  onValueChange: (value: number) => void;
}

function RangeSetting({ prefKey, label, min, max, unit, value, onValueChange }: RangeSettingProps) {
  const [draft, setDraft] = useState(String(value));

  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const commitDraft = () => {
    if (draft.trim() === "") {
      setDraft(String(value));
      return;
    }
    const parsed = Number(draft);
    if (!Number.isFinite(parsed)) {
      setDraft(String(value));
      return;
    }
    const bounded = Math.min(max, Math.max(min, parsed));
    onValueChange(bounded);
    setDraft(String(bounded));
  };

  return (
    <div className="interface-tuning-range">
      <span className="interface-tuning-range-label">
        <span>{label}</span>
        <output>{value}{unit}</output>
      </span>
      <div className="interface-tuning-range-controls">
        <input
          className="interface-tuning-slider"
          type="range"
          min={min}
          max={max}
          step="any"
          value={value}
          onChange={(event) => {
            const next = Number(event.currentTarget.value);
            onValueChange(next);
            setDraft(String(next));
          }}
          aria-label={label}
        />
        <input
          className="interface-tuning-number"
          type="number"
          min={min}
          max={max}
          step="any"
          value={draft}
          onChange={(event) => setDraft(event.currentTarget.value)}
          onBlur={commitDraft}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            } else if (event.key === "Escape") {
              setDraft(String(value));
              event.currentTarget.blur();
            }
          }}
          aria-label={label + ": точное значение"}
          title={`Допустимый диапазон: ${min}–${max}${unit}`}
        />
      </div>
    </div>
  );
}

export function InterfaceTuning({ mode, compact = false }: InterfaceTuningProps) {
  const { state, dispatch } = useAppState();
  const preferences = state.interfacePreferences[mode];

  const update = (key: InterfacePreferenceKey, value: number | boolean) => {
    dispatch({ type: "interfacePreference/update", mode, key, value });
  };

  const reset = () => {
    for (const key of Object.keys(DEFAULTS) as InterfacePreferenceKey[]) {
      update(key, DEFAULTS[key]);
    }
  };

  const rangeField = (
    prefKey: NumericPreferenceKey,
    label: string,
    min: number,
    max: number,
    unit: string
  ) => (
    <RangeSetting
      key={prefKey}
      prefKey={prefKey}
      label={label}
      min={min}
      max={max}
      unit={unit}
      value={preferences[prefKey]}
      onValueChange={(value) => update(prefKey, value)}
    />
  );

  return (
    <section className={"interface-tuning" + (compact ? " interface-tuning-compact" : "")}>
      <header className="interface-tuning-heading">
        <div>
          <span className="eyebrow">PERSONALIZATION / {mode === "classic" ? "CLASSIC" : "NEXUS"}</span>
          <h2>Масштаб и раскладка</h2>
          {!compact && <p>Ползунок для быстрой настройки или точное значение в поле справа.</p>}
        </div>
        <button type="button" className="interface-tuning-reset" onClick={reset} title="Сбросить настройки этой оболочки">
          <RotateCcw size={14} /><span>Сброс</span>
        </button>
      </header>
      {rangeField("textScale", "Размер текста", 80, 160, "%")}
      {rangeField("controlScale", "Размер кнопок и полей", 80, 160, "%")}
      {rangeField("spacingScale", "Интервалы и отступы", 70, 150, "%")}
      {mode === "classic" && (
        <>
          {rangeField("sidebarWidth", "Ширина боковой панели", 180, 360, " px")}
          {rangeField("chatWidthPercent", "Ширина рабочей области чата", 45, 100, "%")}
          {rangeField("chatHeight", "Высота рабочей области чата", 360, 900, " px")}
        </>
      )}
      {mode === "nexus" && (
        <>
          {rangeField("inspectorWidth", "Ширина панели настроек", 240, 480, " px")}
          <button
            type="button"
            className={"interface-tuning-toggle" + (preferences.inspectorVisible ? " is-enabled" : "")}
            onClick={() => update("inspectorVisible", !preferences.inspectorVisible)}
            aria-pressed={preferences.inspectorVisible}
          >
            <PanelRight size={15} />
            <span>{preferences.inspectorVisible ? "Скрыть панель настроек" : "Показать панель настроек"}</span>
          </button>
          <button
            type="button"
            className={"interface-tuning-toggle" + (preferences.minimapVisible ? " is-enabled" : "")}
            onClick={() => update("minimapVisible", !preferences.minimapVisible)}
            aria-pressed={preferences.minimapVisible}
          >
            {preferences.minimapVisible ? <EyeOff size={15} /> : <Eye size={15} />}
            <span>{preferences.minimapVisible ? "Скрыть мини-карту" : "Показать мини-карту"}</span>
          </button>
        </>
      )}
      <p className="interface-tuning-note">
        {mode === "classic"
          ? "Перетаскивай границу боковой панели или угол чата. Размеры можно точно подстроить ползунками или числами."
          : "Панель настроек и мини-карту можно скрывать независимо друг от друга. Настройки Classic хранятся отдельно."}
      </p>
    </section>
  );
}
