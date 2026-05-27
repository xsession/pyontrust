import { StatusChip } from "../../shared/ui/StatusChip";

interface PenpotHealthBannerProps {
  title: string;
  summary: string;
  tone: "success" | "warning";
  statusLabel: string;
}

export function PenpotHealthBanner({ title, summary, tone, statusLabel }: PenpotHealthBannerProps) {
  return (
    <section className={`workspace-health-banner penpot-health-banner workspace-health-banner--${tone}`}>
      <div className="penpot-health-banner__content">
        <strong>{title}</strong>
        <p>{summary}</p>
      </div>
      <StatusChip label={statusLabel} tone={tone} />
    </section>
  );
}