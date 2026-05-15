import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { joinClassNames } from "./_utils";

export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

export const DropdownMenuContent = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 8, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={joinClassNames("radix-surface", "radix-dropdown__content", className)}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));

DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

export const DropdownMenuItem = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Item>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Item ref={ref} className={joinClassNames("radix-item", className)} {...props} />
));

DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

export const DropdownMenuCheckboxItem = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.CheckboxItem>,
  ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.CheckboxItem>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.CheckboxItem ref={ref} className={joinClassNames("radix-item", className)} {...props} />
));

DropdownMenuCheckboxItem.displayName = DropdownMenuPrimitive.CheckboxItem.displayName;

export function DropdownMenuSeparator({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <DropdownMenuPrimitive.Separator className={joinClassNames("radix-separator", className)} {...props} />;
}