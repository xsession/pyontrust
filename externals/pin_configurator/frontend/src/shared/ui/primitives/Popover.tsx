import * as PopoverPrimitive from "@radix-ui/react-popover";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { joinClassNames } from "./_utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = forwardRef<
  ElementRef<typeof PopoverPrimitive.Content>,
  ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, sideOffset = 8, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={joinClassNames("radix-surface", "radix-popover__content", className)}
      {...props}
    />
  </PopoverPrimitive.Portal>
));

PopoverContent.displayName = PopoverPrimitive.Content.displayName;