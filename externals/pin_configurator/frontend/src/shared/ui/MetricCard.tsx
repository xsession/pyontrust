import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  accent?: "sun" | "mint" | "signal";
  icon?: ReactNode;
}

export function MetricCard({ label, value, detail, accent = "sun", icon }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${accent}`}>
      <div className="metric-card__label-row">
        <span className="metric-card__label">{label}</span>
        <span className="metric-card__icon" aria-hidden="true">{icon}</span>
      </div>
      <strong className="metric-card__value">{value}</strong>
      <p className="metric-card__detail">{detail}</p>
    </article>
  );
}