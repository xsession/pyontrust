interface StatusChipProps {
  label: string;
  tone?: "neutral" | "info" | "success" | "warning" | "error";
}

export function StatusChip({ label, tone = "neutral" }: StatusChipProps) {
  return <span className={`status-chip status-chip--${tone}`}>{label}</span>;
}