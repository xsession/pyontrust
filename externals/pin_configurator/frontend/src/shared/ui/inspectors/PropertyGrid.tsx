import type { ReactNode } from "react";

interface PropertyGridProps {
  children: ReactNode;
}

interface PropertyRowProps {
  label: string;
  value: ReactNode;
}

export function PropertyGrid({ children }: PropertyGridProps) {
  return <dl className="property-grid">{children}</dl>;
}

export function PropertyRow({ label, value }: PropertyRowProps) {
  return (
    <div className="property-grid__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}