import type { ReactNode } from "react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../primitives/index";

interface ContextMenuItem {
  id: string;
  label: string;
  shortcut?: ReactNode;
  disabled?: boolean;
  onSelect: () => void;
}

interface ContextMenuProps {
  triggerLabel: string;
  triggerText?: string;
  items: ContextMenuItem[];
}

export function ContextMenu({ triggerLabel, triggerText = "Actions", items }: ContextMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="context-menu__trigger" aria-label={triggerLabel}>
          {triggerText}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="command-menu command-menu--context">
        {items.map((item) => (
          <DropdownMenuItem key={item.id} onSelect={item.onSelect} disabled={item.disabled} className="command-menu__item">
            <span>{item.label}</span>
            {item.shortcut ? <span className="command-menu__shortcut">{item.shortcut}</span> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}