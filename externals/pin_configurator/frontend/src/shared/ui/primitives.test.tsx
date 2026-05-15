import { fireEvent, render, screen } from "@testing-library/react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./primitives";

describe("shared Radix primitives", () => {
  it("opens wrapped dialog content", () => {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <button type="button">Open dialog</button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Primitive dialog</DialogTitle>
            <DialogDescription>Dialog wrapper content</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button">Close</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open dialog" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Primitive dialog")).toBeInTheDocument();
    expect(screen.getByText("Dialog wrapper content")).toBeInTheDocument();
  });

  it("opens wrapped popover content", () => {
    render(
      <Popover>
        <PopoverTrigger asChild>
          <button type="button">Open popover</button>
        </PopoverTrigger>
        <PopoverContent>Popover wrapper content</PopoverContent>
      </Popover>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open popover" }));
    expect(screen.getByText("Popover wrapper content")).toBeInTheDocument();
  });

  it("opens wrapped dropdown menu content", () => {
    const handleSelect = vi.fn();

    render(
      <DropdownMenu open>
        <DropdownMenuTrigger asChild>
          <button type="button">Open menu</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={handleSelect}>Inspect board</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    fireEvent.click(screen.getByText("Inspect board"));

    expect(handleSelect).toHaveBeenCalledTimes(1);
  });

  it("shows wrapped tooltip content", () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip open>
          <TooltipTrigger asChild>
            <button type="button">Hover target</button>
          </TooltipTrigger>
          <TooltipContent>Tooltip wrapper content</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    expect(screen.getByRole("tooltip")).toHaveTextContent("Tooltip wrapper content");
  });
});