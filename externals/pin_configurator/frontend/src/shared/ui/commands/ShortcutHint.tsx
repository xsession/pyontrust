import { joinClassNames } from "../primitives/_utils";

interface ShortcutHintProps {
  shortcut: string;
  className?: string;
}

export function ShortcutHint({ shortcut, className }: ShortcutHintProps) {
  return (
    <span aria-hidden="true" className={joinClassNames("shortcut-hint", className)}>
      {shortcut}
    </span>
  );
}