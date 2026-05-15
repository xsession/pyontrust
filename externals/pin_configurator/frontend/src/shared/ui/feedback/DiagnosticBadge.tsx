interface DiagnosticBadgeProps {
  label: string;
  tone?: "info" | "success" | "warning" | "error";
}

export function DiagnosticBadge({ label, tone = "info" }: DiagnosticBadgeProps) {
  return <span className={`diagnostic-badge diagnostic-badge--${tone}`}>{label}</span>;
}