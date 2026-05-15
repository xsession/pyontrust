import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { joinClassNames } from "./_utils";

export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipProvider({ delayDuration = 120, ...props }: TooltipPrimitive.TooltipProviderProps) {
  return <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />;
}

export const TooltipContent = forwardRef<
  ElementRef<typeof TooltipPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 8, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={joinClassNames("radix-tooltip__content", className)}
      {...props}
    />
  </TooltipPrimitive.Portal>
));

TooltipContent.displayName = TooltipPrimitive.Content.displayName;