import { ArrowRight, Command, ExternalLink, Search } from "lucide-react";
import { useAppState } from "../app/context";
import { PrototypeNotice } from "../components/PrototypeNotice";
import { PageHeader } from "./PageHeader";

const commandGroups = [
  {
    title: "Окна и приложения",
    tag: "WINDOWS",
    commands: [
      ["Свернуть окно", "«сверни окно», «минимизируй»"],
      ["Восстановить окно", "«разверни окно», «восстанови»"],
      ["Открыть приложение", "«открой Discord», «запусти браузер»"]
    ]
  },
  {
    title: "Локальная модель",
    tag: "OLLAMA",
    commands: [
      ["Запустить Ollama", "«запусти Ollama»"],
      ["Выгрузить модель", "«выгрузи модель», «освободи память»"]
    ]
  },
  {
    title: "Файлы и Workspace",
    tag: "FILES",
    commands: [
      ["Найти файл", "«найди документ», «покажи файл»"],
      ["Открыть Workspace", "«открой рабочую область»"]
    ]
  }
];

export function CommandsPage() {
  const { dispatch } = useAppState();

  return (
    <div className="page-content commands-page">
      <PageHeader eyebrow="COMMAND ROUTER / CATALOG" title="Команды" description="Примеры будущих команд. В этом прототипе они не запускают программы и не обращаются к системе." />
      <PrototypeNotice />
      <div className="command-search"><Search size={17} /><input aria-label="Поиск по каталогу команд" placeholder="Поиск по примерам команд..." /><span>ПОИСК ПО МАКЕТУ</span></div>
      <div className="command-groups">
        {commandGroups.map((group, index) => (
          <section className="command-group-card" key={group.tag}>
            <div className="command-group-heading">
              <div><span className="eyebrow">{group.tag} / 0{index + 1}</span><h2>{group.title}</h2></div>
              <span className="command-count">{group.commands.length.toString().padStart(2, "0")} ПРИМЕРА</span>
            </div>
            <div className="command-example-list">
              {group.commands.map(([title, example]) => (
                <div className="command-example" key={title}>
                  <span className="command-example-icon"><Command size={16} /></span>
                  <div><strong>{title}</strong><p>{example}</p></div>
                  <span className="command-example-tag">МАКЕТ</span>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
      <button className="text-action command-page-action" type="button" onClick={() => dispatch({ type: "navigate", page: "settings" })}>Настройки ассистента <ArrowRight size={14} /></button>
    </div>
  );
}
