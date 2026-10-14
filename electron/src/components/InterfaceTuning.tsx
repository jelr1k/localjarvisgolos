import { RotateCcw } from "lucide-react";
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
  label: string;
  min: number;
  max: number;
  unit: string;
  value: number;
  onValueChange: (value: number) => void;
}

function RangeSetting({ label, min, max, unit, value, onValueChange }: RangeSettingProps) {
  const wholeValue = Math.round(value);

  return (
    <div className="interface-tuning-range">
      <span className="interface-tuning-range-label">
        <span>{label}</span>
        <output>{wholeValue}{unit}</output>
      </span>
      <div className="interface-tuning-range-controls">
        <input
          className="interface-tuning-slider"
          type="range"
          min={min}
          max={max}
          step={1}
          value={wholeValue}
          onChange={(event) => onValueChange(Math.round(Number(event.currentTarget.value)))}
          aria-label={label}
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
          {!compact && <p>Все значения целые. Перемещай ползунки, чтобы подстроить интерфейс.</p>}
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
            <span>{preferences.inspectorVisible ? "Скрыть панель настроек" : "Показать панель настроек"}</span>
          </button>
          <button
            type="button"
            className={"interface-tuning-toggle" + (preferences.minimapVisible ? " is-enabled" : "")}
            onClick={() => update("minimapVisible", !preferences.minimapVisible)}
            aria-pressed={preferences.minimapVisible}
          >
            <span>{preferences.minimapVisible ? "Скрыть мини-карту" : "Показать мини-карту"}</span>
          </button>
        </>
      )}
      <p className="interface-tuning-note">
        {mode === "classic"
          ? "Можно перетаскивать границу боковой панели и угол чата. Значения меняются целыми шагами."
          : "Панель настроек и мини-карта скрываются независимо. Параметры Classic хранятся отдельно."}
      </p>
    </section>
  );
}
