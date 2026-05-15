import type { ReactNode } from "react";
import { joinClassNames } from "../primitives/_utils";

interface InspectorNoticeProps {
  title: string;
  detail: string;
  tone?: "info" | "success" | "warning" | "error";
  actions?: ReactNode;
}

export function InspectorNotice({ title, detail, tone = "info", actions }: InspectorNoticeProps) {
  return (
    <div className={joinClassNames("inspector-notice", `inspector-notice--${tone}`)}>
      <div className="inspector-notice__body">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      {actions ? <div className="inspector-notice__actions">{actions}</div> : null}
    </div>
  );
}