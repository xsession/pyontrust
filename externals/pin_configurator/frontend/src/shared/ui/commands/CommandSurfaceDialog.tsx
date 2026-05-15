import type { ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../primitives/index";
import { joinClassNames } from "../primitives/_utils";

interface CommandSurfaceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  className?: string;
  footer?: ReactNode;
  children: ReactNode;
}

export function CommandSurfaceDialog({
  open,
  onOpenChange,
  title,
  description,
  className,
  footer,
  children,
}: CommandSurfaceDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={joinClassNames("command-surface-dialog", className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
        {footer ? <DialogFooter>{footer}</DialogFooter> : null}
      </DialogContent>
    </Dialog>
  );
}