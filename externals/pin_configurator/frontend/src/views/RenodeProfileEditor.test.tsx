import { render, screen } from "@testing-library/react";
import { defaultRenodeProfile } from "../contracts/api";
import { RenodeProfileEditor } from "./RenodeProfileEditor";

describe("RenodeProfileEditor", () => {
  it("surfaces readiness first and separates editable source fields from generated bundle semantics", () => {
    const renode = defaultRenodeProfile("");
    renode.enabled = true;

    render(<RenodeProfileEditor renode={renode} onFieldChange={() => undefined} />);

    expect(screen.getByText("Renode readiness")).toBeInTheDocument();
    expect(screen.getByText("Simulation bundle loop")).toBeInTheDocument();
    expect(screen.getByText("Editable runtime fields")).toBeInTheDocument();
    expect(screen.getByText("Editable automation source fields")).toBeInTheDocument();
    expect(screen.getByText("Generated simulation bundles stay derived from these source fields")).toBeInTheDocument();
  });
});