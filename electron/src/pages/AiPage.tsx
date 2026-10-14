import { Activity, Brain, Cpu, Database, Gauge, HardDrive, Settings2 } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

export function AiPage() {
  const { state, dispatch } = useAppState();
  const ai = state.settings.ai;

  return (
    <div className="page-content ai-page">
      <PageHeader eyebrow="LOCAL INTELLIGENCE / CONFIGURATION" title="Искусственный интеллект" description="Представление параметров будущего контура Ollama. Показатели системы не имитируются случайными цифрами." />
      <PrototypeNotice />
      <div className="ai-overview-grid">
        <section className="ai-model-card">
          <div className="panel-heading"><span><Brain size={16} /> SELECTED MODEL</span><span className="not-connected"><i /> Не подключена</span></div>
          <span className="ai-model-mark"><Brain size={25} /></span>
          <h2>{ai.model}</h2>
          <p>Модель выбрана в настройках, но не проверялась и не загружалась приложением.</p>
          <div className="ai-model-stats">
            <div><span>Контекст</span><strong>{ai.contextTokens.toLocaleString("ru-RU")} токенов</strong></div>
            <div><span>Температура</span><strong>{ai.temperature.toFixed(1)}</strong></div>
            <div><span>Размышления</span><strong>{ai.thinking ? "Включены в настройках" : "Выключены в настройках"}</strong></div>
          </div>
          <button className="primary-button" type="button" onClick={() => dispatch({ type: "navigate", page: "settings" })}><Settings2 size={15} /> Настроить модель</button>
        </section>
        <section className="ai-status-panel">
          <div className="panel-heading"><span><Activity size={16} /> СИСТЕМНЫЙ СТАТУС</span><span className="demo-chip">НЕТ ДАННЫХ</span></div>
          <div className="ai-status-row"><span><Cpu size={16} /> Процессор</span><strong>Нет источника данных</strong></div>
          <div className="ai-status-row"><span><Gauge size={16} /> Скорость генерации</span><strong>Нет запросов</strong></div>
          <div className="ai-status-row"><span><HardDrive size={16} /> Видеопамять</span><strong>Не измеряется</strong></div>
          <div className="ai-status-row"><span><Database size={16} /> Контекст и токены</span><strong>Нет статистики</strong></div>
        </section>
      </div>
      <div className="ai-footnote"><span className="status-dot" /> Данные появятся после подключения сервисов. Макет не вызывает Ollama и не нагружает модель.</div>
    </div>
  );
}
