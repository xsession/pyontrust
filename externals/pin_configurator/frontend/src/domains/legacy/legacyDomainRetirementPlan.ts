export interface LegacyDomainRetirementEntry {
  id:
    | "pin-configurator"
    | "module-configurator"
    | "peripheral-configurator"
    | "clock-configurator"
    | "protocol-editor"
    | "lvgl-layout"
    | "interrupt-configurator"
    | "board-editor"
    | "sensor-parser"
    | "package-manager"
    | "zephyr-catalog"
    | "generated-output"
    | "build-sim-test";
  label: string;
  status: "react-presenter" | "legacy-global";
  legacyGlobals: string[];
  retirementGoal: string;
}

export interface LegacyCutoverSummary {
  canonicalShellLabel: string;
  canonicalShellDetail: string;
  legacySupportLabel: string;
  legacySupportDetail: string;
  remainingLegacyWorkflows: LegacyDomainRetirementEntry[];
  portingRule: string;
  cutoverThresholdLabel: string;
  cutoverThresholdDetail: string;
  cutoverThresholdMet: boolean;
}

export const legacyDomainRetirementPlan: readonly LegacyDomainRetirementEntry[] = [
  {
    id: "pin-configurator",
    label: "Pin Configurator",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep pin selection, assignment, and validation flows in the React presenter layer.",
  },
  {
    id: "module-configurator",
    label: "Module Configurator",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep module definition loading, option editing, and module config generation inside the React presenter layer.",
  },
  {
    id: "peripheral-configurator",
    label: "Peripheral Configurator",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep peripheral enablement, core routing, and canonical external-device selection inside the React presenter layer.",
  },
  {
    id: "clock-configurator",
    label: "Clock Configurator",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep clock-tree loading, frequency recomputation, and generation workflows inside typed presenters.",
  },
  {
    id: "protocol-editor",
    label: "Protocol Editor",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep protocol composition and mutations inside the React protocol presenter.",
  },
  {
    id: "lvgl-layout",
    label: "LVGL Layout",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep LVGL import/export and canonical layout mutation inside the React presenter layer.",
  },
  {
    id: "interrupt-configurator",
    label: "Interrupt Configurator",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep interrupt-sensitive workflow derivation inside typed presenter composition instead of legacy snapshot scripts.",
  },
  {
    id: "board-editor",
    label: "Board Editor",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep board-editor draft discovery and JSON editing flows inside typed draft presenters while richer scene work moves to later phases.",
  },
  {
    id: "sensor-parser",
    label: "Sensor Parser",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep persisted sensor jobs and catalog-driven imports inside typed presenter commands.",
  },
  {
    id: "package-manager",
    label: "Package Manager",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep package-manager jobs and catalog imports inside typed presenter commands and canonical persistence.",
  },
  {
    id: "zephyr-catalog",
    label: "Zephyr Catalog",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep Zephyr catalog loading, filtering, selection, and workflow handoff inside the React presenter layer.",
  },
  {
    id: "generated-output",
    label: "Generated Output",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep generated artifact editing, seeding, clearing, and export in the React presenter layer.",
  },
  {
    id: "build-sim-test",
    label: "Build/Sim/Test",
    status: "react-presenter",
    legacyGlobals: [],
    retirementGoal: "Keep build, simulation, diagnostics, and test readiness orchestration in typed presenter modules.",
  },
] as const;

export function listRemainingLegacyDomains() {
  return legacyDomainRetirementPlan.filter((entry) => entry.status === "legacy-global");
}

export function buildLegacyCutoverSummary(
  entries: readonly LegacyDomainRetirementEntry[] = legacyDomainRetirementPlan,
): LegacyCutoverSummary {
  const remainingLegacyWorkflows = entries.filter((entry) => entry.status === "legacy-global");
  const cutoverThresholdMet = remainingLegacyWorkflows.length === 0;

  return {
    canonicalShellLabel: "React shell is canonical",
    canonicalShellDetail: "New workstation behavior is defined in the React shell first. The legacy web/index.html path stays aligned to that model instead of introducing competing shell patterns.",
    legacySupportLabel: remainingLegacyWorkflows.length
      ? `${remainingLegacyWorkflows.length} workflow${remainingLegacyWorkflows.length === 1 ? " still requires" : "s still require"} legacy-only support`
      : "No workflows still require legacy-only support",
    legacySupportDetail: remainingLegacyWorkflows.length
      ? `Legacy-only support remains limited to ${remainingLegacyWorkflows.map((entry) => entry.label).join(", ")} until those flows are replaced in React.`
      : "Legacy support is now maintenance-only. New feature work should stay in React unless a cutover blocker is discovered.",
    remainingLegacyWorkflows,
    portingRule: "Port shell-critical patterns only after they are stable in React, then backfill legacy only when compatibility is still required.",
    cutoverThresholdLabel: cutoverThresholdMet ? "Legacy feature freeze is active" : "Legacy feature freeze is blocked",
    cutoverThresholdDetail: cutoverThresholdMet
      ? "The legacy shell stops receiving feature work once all tracked workflows are owned by React presenters and no legacy-global flows remain."
      : "The legacy shell can stop receiving feature work only after every tracked workflow moves out of legacy-global ownership.",
    cutoverThresholdMet,
  };
}