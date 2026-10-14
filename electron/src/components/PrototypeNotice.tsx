import { Info } from "lucide-react";

interface PrototypeNoticeProps {
  compact?: boolean;
}

export function PrototypeNotice({ compact = false }: PrototypeNoticeProps) {
  return (
    <div className={"prototype-notice" + (compact ? " prototype-notice-compact" : "")} role="status">
      <Info size={16} aria-hidden="true" />
      <span>
        <strong>Режим макета.</strong> Сервисы ассистента пока не подключены; значения ниже сохраняются только в настройках интерфейса.
      </span>
    </div>
  );
}
