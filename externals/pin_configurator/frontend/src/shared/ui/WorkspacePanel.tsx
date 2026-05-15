import type { ReactNode } from "react";
import { StatusChip } from "./StatusChip";

interface WorkspacePanelProps {
  eyebrow: string;
  title: string;
  detail: string;
  children: ReactNode;
}

export function WorkspacePanel({ eyebrow, title, detail, children }: WorkspacePanelProps) {
  return (
    <section className="workspace-panel">
      <header className="workspace-panel__header">
        <span className="workspace-panel__eyebrow">
          <StatusChip label={eyebrow} tone="neutral" />
        </span>
        <h2>{title}</h2>
        <p>{detail}</p>
      </header>
      <div className="workspace-panel__body">{children}</div>
    </section>
  );
}