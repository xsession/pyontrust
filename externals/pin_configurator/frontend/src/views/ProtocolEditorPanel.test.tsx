import { render, screen } from "@testing-library/react";
import { createDefaultProtocolEditorDocument } from "../contracts/api";
import { ProtocolEditorPanel } from "./ProtocolEditorPanel";

describe("ProtocolEditorPanel", () => {
  it("surfaces readiness counts and keeps editable values separate from derived metadata", () => {
    const document = createDefaultProtocolEditorDocument();

    render(
      <ProtocolEditorPanel
        document={document}
        onAddEntry={() => undefined}
        onSelectEntry={() => undefined}
        onRemoveEntry={() => undefined}
        onToggleEntry={() => undefined}
        onUpdateEntryValue={() => undefined}
      />,
    );

    expect(screen.getByText("Protocol readiness")).toBeInTheDocument();
    expect(screen.getByText("Generated interface review")).toBeInTheDocument();
    expect(screen.getByText("Editable protocol values")).toBeInTheDocument();
    expect(screen.getByText("Template family")).toBeInTheDocument();
    expect(screen.getByText("Editable entry values stay below derived metadata")).toBeInTheDocument();
    expect(screen.getByText(/header .*_init\(void\).*source .*_attach\(void\)/i)).toBeInTheDocument();
  });
});