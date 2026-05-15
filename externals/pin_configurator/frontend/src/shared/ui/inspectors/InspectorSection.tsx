import type { ReactNode } from "react";

interface InspectorSectionProps {
  title: string;
  summary?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function InspectorSection({ title, summary, actions, children }: InspectorSectionProps) {
  return (
    <section className="inspector-section">
      <header className="inspector-section__header">
        <div>
          <h3 className="inspector-section__title">{title}</h3>
          {summary ? <p className="inspector-section__summary">{summary}</p> : null}
        </div>
        {actions ? <div className="inspector-section__actions">{actions}</div> : null}
      </header>
      <div className="inspector-section__body">{children}</div>
    </section>
  );
}