import { buildLegacyCutoverSummary, legacyDomainRetirementPlan, listRemainingLegacyDomains } from "./legacyDomainRetirementPlan";

describe("legacyDomainRetirementPlan", () => {
  it("tracks migrated and legacy domain ownership explicitly", () => {
    expect(legacyDomainRetirementPlan.find((entry) => entry.id === "pin-configurator")).toMatchObject({
      status: "react-presenter",
    });
    expect(legacyDomainRetirementPlan.find((entry) => entry.id === "zephyr-catalog")).toMatchObject({
      status: "react-presenter",
    });
    expect(legacyDomainRetirementPlan.find((entry) => entry.id === "board-editor")).toMatchObject({
      status: "react-presenter",
    });
  });

  it("shows that the React shell no longer has unmigrated legacy-global domains in the retirement plan", () => {
    expect(listRemainingLegacyDomains()).toEqual([]);
  });

  it("defines the cutover threshold around zero remaining legacy-global workflows", () => {
    expect(buildLegacyCutoverSummary()).toMatchObject({
      cutoverThresholdMet: true,
      legacySupportLabel: "No workflows still require legacy-only support",
      cutoverThresholdLabel: "Legacy feature freeze is active",
    });
  });
});