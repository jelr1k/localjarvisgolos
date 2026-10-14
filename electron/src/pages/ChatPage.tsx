import type { FormEvent } from "react";
import { ArrowUp, Bot, Mic, Send, Sparkles, Trash2, UserRound } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

export function ChatPage() {
  const { state, dispatch } = useAppState();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    dispatch({ type: "chat/send" });
  }

  return (
    <div className="page-content chat-page">
      <PageHeader eyebrow="CONVERSATION / LOCAL PREVIEW" title="Чат" description="Здесь останется единый диалог независимо от выбранного оформления."
        action={<button className="secondary-button" type="button" onClick={() => dispatch({ type: "chat/clear" })}><Trash2 size={15} /> Очистить</button>} />
      <PrototypeNotice />
      <section className="chat-workspace">
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
      </section>
    </div>
  );
}
