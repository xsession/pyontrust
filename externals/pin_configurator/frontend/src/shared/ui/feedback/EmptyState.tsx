import type { ReactNode } from "react";
import { joinClassNames } from "../primitives/_utils";

interface EmptyStateProps {
  title: string;
  detail: string;
  tone?: "info" | "warning" | "error";
  compact?: boolean;
  actions?: ReactNode;
}

export function EmptyState({ title, detail, tone = "info", compact = false, actions }: EmptyStateProps) {
  return (
    <div className={joinClassNames("workspace-feedback", `workspace-feedback--${tone}`, compact && "workspace-feedback--compact")}>
      <div className="workspace-feedback__body">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      {actions ? <div className="workspace-feedback__actions">{actions}</div> : null}
    </div>
  );
}