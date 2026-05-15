import type { ReactNode } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../primitives/index";

interface SplitButtonItem {
  id: string;
  label: string;
  shortcut?: ReactNode;
  disabled?: boolean;
  onSelect: () => void;
}

interface SplitButtonProps {
  primaryLabel: string;
  primaryDisabled?: boolean;
  primaryTone?: "default" | "primary" | "command";
  primaryAriaExpanded?: boolean;
  primaryHasPopup?: "dialog" | "menu";
  primaryAriaKeyShortcuts?: string;
  menuLabel: string;
  menuItems: SplitButtonItem[];
  onPrimaryClick: () => void;
}

export function SplitButton({
  primaryLabel,
  primaryDisabled = false,
  primaryTone = "command",
  primaryAriaExpanded,
  primaryHasPopup,
  primaryAriaKeyShortcuts,
  menuLabel,
  menuItems,
  onPrimaryClick,
}: SplitButtonProps) {
  return (
    <DropdownMenu>
      <div className="split-button">
        <button
          type="button"
          className={`shell-button ${primaryTone === "primary" ? "shell-button--primary" : primaryTone === "command" ? "shell-button--command" : ""}`}
          onClick={onPrimaryClick}
          disabled={primaryDisabled}
          aria-expanded={primaryAriaExpanded}
          aria-haspopup={primaryHasPopup}
          aria-keyshortcuts={primaryAriaKeyShortcuts}
        >
          <span className="shell-button__label">{primaryLabel}</span>
        </button>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="shell-button shell-button--split-toggle"
            aria-label={menuLabel}
            disabled={primaryDisabled}
          >
            <span aria-hidden="true">▾</span>
          </button>
        </DropdownMenuTrigger>
      </div>
      <DropdownMenuContent align="start" className="command-menu">
        {menuItems.map((item, index) => (
          <div key={item.id}>
            {index === 1 ? <DropdownMenuSeparator /> : null}
            <DropdownMenuItem onSelect={item.onSelect} disabled={item.disabled} className="command-menu__item">
              <span>{item.label}</span>
              {item.shortcut ? <span className="command-menu__shortcut">{item.shortcut}</span> : null}
            </DropdownMenuItem>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}