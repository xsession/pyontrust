import type { ReactNode } from "react";
import { StatusChip } from "../../shared/ui/StatusChip";

interface PenpotWorkspacePanelProps {
  eyebrow: string;
  title: string;
  detail: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

function joinClassNames(...values: Array<string | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function PenpotWorkspacePanel({ eyebrow, title, detail, children, className, bodyClassName }: PenpotWorkspacePanelProps) {
  return (
    <section className={joinClassNames("workspace-panel", "penpot-workspace-panel", className)}>
      <header className="workspace-panel__header penpot-workspace-panel__header">
        <span className="workspace-panel__eyebrow penpot-workspace-panel__eyebrow">
          <StatusChip label={eyebrow} tone="neutral" />
        </span>
        <h2>{title}</h2>
        <p>{detail}</p>
      </header>
      <div className={joinClassNames("workspace-panel__body", "penpot-workspace-panel__body", bodyClassName)}>{children}</div>
    </section>
  );
}