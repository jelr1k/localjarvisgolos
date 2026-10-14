import { useRef, type FormEvent, type PointerEvent } from "react";
import { ArrowUp, Bot, Mic, Send, Sparkles, Trash2, UserRound } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

export function ChatPage() {
  const { state, dispatch } = useAppState();
  const preferences = state.interfacePreferences[state.interfaceMode];
  const resizeStart = useRef<{ pointerId: number; startX: number; startY: number; startWidth: number; startHeight: number; availableWidth: number } | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    dispatch({ type: "chat/send" });
  }

  return (
    <div className="page-content chat-page">
      <PageHeader eyebrow="CONVERSATION / LOCAL PREVIEW" title="Чат" description="Здесь останется единый диалог независимо от выбранного оформления."
        action={<button className="secondary-button" type="button" onClick={() => dispatch({ type: "chat/clear" })}><Trash2 size={15} /> Очистить</button>} />
      <PrototypeNotice />
      <section className="chat-workspace" style={{ width: `${preferences.chatWidthPercent}%`, height: `${preferences.chatHeight}px` }}>
        <div className="chat-workspace-head">
          <div className="chat-agent"><span className="chat-agent-mark"><Sparkles size={17} /></span><span><strong>{state.settings.application.assistantName || "Jarvis"}</strong><small>Локальный диалог · демонстрационный режим</small></span></div>
          <span className="not-connected"><i /> Нет подключения к ИИ</span>
        </div>
        <div className="chat-messages" role="log" aria-live="polite">
          {state.chatMessages.length === 0 && (
            <div className="chat-empty-state">
              <span className="chat-empty-icon"><Bot size={24} /></span>
              <h2>Начни с любого сообщения</h2>
              <p>На этом этапе сообщения остаются внутри интерфейса. Реальный ответ модели и выполнение команд будут подключены позже.</p>
              <button className="chat-suggestion" type="button" onClick={() => dispatch({ type: "chat/input", value: "Покажи доступные команды" })}>Покажи доступные команды <ArrowUp size={14} /></button>
            </div>
          )}
          {state.chatMessages.map((message) => (
            <article key={message.id} className={"chat-message " + message.role}>
              <span className="chat-message-avatar">{message.role === "assistant" ? <Bot size={16} /> : <UserRound size={16} />}</span>
              <div><small>{message.role === "assistant" ? state.settings.application.assistantName || "JARVIS" : "ВЫ"}</small><p>{message.text}</p></div>
            </article>
          ))}
        </div>
        <form className="chat-composer" onSubmit={submit}>
          <button className="icon-button disabled-look" type="button" disabled title="Микрофон появится после подключения голосового сервиса" aria-label="Микрофон отключён"><Mic size={17} /></button>
          <input value={state.chatInput} onChange={(event) => dispatch({ type: "chat/input", value: event.currentTarget.value })} placeholder="Напиши тестовое сообщение..." aria-label="Текст сообщения" />
          <span className="composer-local-label">LOCAL ONLY</span>
          <button className="primary-button send-message-button" type="submit" disabled={!state.chatInput.trim()}><Send size={15} /> Отправить</button>
        </form>
        <div
          className="chat-resize-handle"
          role="separator"
          aria-orientation="both"
          aria-label="Изменить размер области чата"
          tabIndex={0}
          onPointerDown={(event: PointerEvent<HTMLDivElement>) => {
            const workspace = event.currentTarget.parentElement;
            const container = workspace?.parentElement;
            const style = container ? window.getComputedStyle(container) : null;
            const availableWidth = container
              ? container.clientWidth - Number.parseFloat(style?.paddingLeft ?? "0") - Number.parseFloat(style?.paddingRight ?? "0")
              : workspace?.getBoundingClientRect().width ?? 600;
            const rect = workspace?.getBoundingClientRect();
            event.currentTarget.setPointerCapture(event.pointerId);
            resizeStart.current = {
              pointerId: event.pointerId,
              startX: event.clientX,
              startY: event.clientY,
              startWidth: rect?.width ?? availableWidth,
              startHeight: rect?.height ?? preferences.chatHeight,
              availableWidth: Math.max(1, availableWidth)
            };
          }}
          onPointerMove={(event: PointerEvent<HTMLDivElement>) => {
            const start = resizeStart.current;
            if (!start || start.pointerId !== event.pointerId) return;
            const widthPercent = Math.min(100, Math.max(45, Math.round(((start.startWidth + event.clientX - start.startX) / start.availableWidth) * 100)));
            const height = Math.min(900, Math.max(360, Math.round(start.startHeight + event.clientY - start.startY)));
            dispatch({ type: "interfacePreference/update", mode: state.interfaceMode, key: "chatWidthPercent", value: widthPercent });
            dispatch({ type: "interfacePreference/update", mode: state.interfaceMode, key: "chatHeight", value: height });
          }}
          onPointerUp={(event: PointerEvent<HTMLDivElement>) => {
            if (resizeStart.current?.pointerId === event.pointerId) resizeStart.current = null;
          }}
          onPointerCancel={() => { resizeStart.current = null; }}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              const delta = event.key === "ArrowRight" ? 5 : -5;
              dispatch({ type: "interfacePreference/update", mode: state.interfaceMode, key: "chatWidthPercent", value: preferences.chatWidthPercent + delta });
            } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              const delta = event.key === "ArrowDown" ? 20 : -20;
              dispatch({ type: "interfacePreference/update", mode: state.interfaceMode, key: "chatHeight", value: preferences.chatHeight + delta });
            }
          }}
        />
      </section>
    </div>
  );
}
