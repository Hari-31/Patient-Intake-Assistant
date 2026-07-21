import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";

type NoticeTone = "info" | "success" | "warning" | "danger";

type NoticeProps = {
  tone?: NoticeTone;
  title?: string;
  children: ReactNode;
};

const icons = {
  info: Info,
  success: CheckCircle2,
  warning: AlertCircle,
  danger: AlertCircle,
};

export function Notice({ tone = "info", title, children }: NoticeProps) {
  const Icon = icons[tone];
  return (
    <div className={`notice notice-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon aria-hidden="true" size={18} />
      <div>
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}
