import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VirtualizedTreeList } from "./VirtualizedTreeList";

describe("VirtualizedTreeList", () => {
  it("renders grouped rows and collapses sections", () => {
    render(
      <VirtualizedTreeList
        ariaLabel="Virtualized sample"
        sections={[
          { id: "recent", label: "Recently used", items: [{ id: "one", label: "First" }] },
          { id: "group", label: "Project", items: [{ id: "two", label: "Second" }], collapsible: true },
        ]}
        getItemId={(item) => item.id}
        renderItem={({ item }) => <button type="button">{item.label}</button>}
      />,
    );

    expect(screen.getByRole("button", { name: "First" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Second" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Project/i }));

    expect(screen.queryByRole("button", { name: "Second" })).not.toBeInTheDocument();
  });
});