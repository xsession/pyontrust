import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { joinClassNames } from "../primitives/_utils";

interface ToolbarGroupProps extends ComponentPropsWithoutRef<"div"> {
  label?: string;
  children: ReactNode;
}

export function ToolbarGroup({ label, className, children, ...props }: ToolbarGroupProps) {
  return (
    <div className={joinClassNames("toolbar-group", className)} {...props}>
      {label ? <span className="toolbar-group__label">{label}</span> : null}
      <div className="toolbar-group__controls">{children}</div>
    </div>
  );
}