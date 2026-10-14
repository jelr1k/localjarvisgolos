import { PanelRight, RotateCcw } from "lucide-react";
import { useAppState } from "../app/context";
import type { InterfaceMode, InterfacePreferenceKey } from "../app/types";

interface InterfaceTuningProps {
  mode: InterfaceMode;
  compact?: boolean;
}

const DEFAULTS = {
  textScale: 100,
  controlScale: 100,
  sidebarWidth: 236,
  chatWidthPercent: 100,
  chatHeight: 620,
  inspectorWidth: 322,
  inspectorVisible: true
} as const;

export function InterfaceTuning({ mode, compact = false }: InterfaceTuningProps) {
  const { state, dispatch } = useAppState();
  const preferences = state.interfacePreferences[mode];

  const update = (key: InterfacePreferenceKey, value: number | boolean) => {
    dispatch({ type: "interfacePreference/update", mode, key, value });
  };

  const reset = () => {
    for (const key of ["textScale", "controlScale", "sidebarWidth", "chatWidthPercent", "chatHeight", "inspectorWidth", "inspectorVisible"] as const) {
      update(key, DEFAULTS[key]);
    }
  };

  const rangeField = (
    key: "textScale" | "controlScale" | "sidebarWidth" | "chatWidthPercent" | "chatHeight" | "inspectorWidth",
    label: string,
    min: number,
    max: number,
    unit: string
  ) => (
    <label className="interface-tuning-range" key={key}>
      <span className="interface-tuning-range-label">
        <span>{label}</span>
        <output>{preferences[key]}{unit}</output>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={key === "textScale" || key === "controlScale" ? 5 : key === "chatWidthPercent" ? 1 : key === "chatHeight" ? 5 : 2}
        value={preferences[key]}
        onChange={(event) => update(key, Number(event.currentTarget.value))}
        aria-label={label}
      />
    </label>
  );

  return (
    <section className={"interface-tuning" + (compact ? " interface-tuning-compact" : "")}>
      <header className="interface-tuning-heading">
        <div>
          <span className="eyebrow">PERSONALIZATION / {mode === "classic" ? "CLASSIC" : "NEXUS"}</span>
          <h2>Масштаб и раскладка</h2>
          {!compact && <p>Настраивай текст и элементы независимо друг от друга.</p>}
        </div>
        <button type="button" className="interface-tuning-reset" onClick={reset} title="Сбросить настройки этой оболочки">
          <RotateCcw size={14} /><span>Сброс</span>
        </button>
      </header>
      {rangeField("textScale", "Размер текста", 80, 160, "%")}
      {rangeField("controlScale", "Размер кнопок и полей", 80, 160, "%")}
      {mode === "classic" && <>{rangeField("sidebarWidth", "Ширина боковой панели", 180, 360, " px")}{rangeField("chatWidthPercent", "Ширина рабочей области чата", 45, 100, "%")}{rangeField("chatHeight", "Высота рабочей области чата", 360, 900, " px")}</>}
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
        </>
      )}
      <p className="interface-tuning-note">
        {mode === "classic"
          ? "Перетаскивай границу боковой панели или угол чата. Размеры можно точно подстроить ползунками."
          : "Размер панели меняется перетаскиванием разделителя. Настройки Classic хранятся отдельно."}
      </p>
    </section>
  );
}
