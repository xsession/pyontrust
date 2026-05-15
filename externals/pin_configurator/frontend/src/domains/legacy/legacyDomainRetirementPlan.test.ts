import { legacyDomainRetirementPlan, listRemainingLegacyDomains } from "./legacyDomainRetirementPlan";

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
});