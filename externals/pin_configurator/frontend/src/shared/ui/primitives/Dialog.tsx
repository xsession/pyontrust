import * as DialogPrimitive from "@radix-ui/react-dialog";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { joinClassNames } from "./_utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export const DialogOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay ref={ref} className={joinClassNames("radix-overlay", className)} {...props} />
));

DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

export const DialogContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={joinClassNames("radix-surface", "radix-dialog__content", className)}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DialogPortal>
));

DialogContent.displayName = DialogPrimitive.Content.displayName;

export function DialogHeader({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div className={joinClassNames("radix-dialog__header", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div className={joinClassNames("radix-dialog__footer", className)} {...props} />;
}