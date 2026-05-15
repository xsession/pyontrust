import type { ShellStatusItemViewModel } from "../../presenters/useShellPresenter";
import { StatusChip } from "../../shared/ui/StatusChip";

interface WorkspaceStatusBarProps {
  statusBarItems: ShellStatusItemViewModel[];
}

export function WorkspaceStatusBar({ statusBarItems }: WorkspaceStatusBarProps) {
  return (
    <section className="workspace-status-bar" aria-label="Workspace status bar">
      {statusBarItems.map((item) => (
        <div key={item.id} className={`workspace-status-bar__item workspace-status-bar__item--${item.tone}`}>
          <StatusChip label={item.label} tone={item.tone === "success" ? "success" : item.tone === "warning" ? "warning" : "neutral"} />
          <strong className="workspace-status-bar__value">{item.value}</strong>
          <span className="workspace-status-bar__detail">{item.detail}</span>
        </div>
      ))}
    </section>
  );
}
