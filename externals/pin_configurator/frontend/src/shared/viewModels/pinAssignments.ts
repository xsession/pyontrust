export interface PinAssignmentSummaryViewModel {
  resolvedCount: number;
  savedCount: number;
  unresolvedCount: number;
}

export interface PinAssignmentRowViewModel {
  pinNumber: string;
  savedLabel: string;
  resolvedLabel: string;
  resolvedRoute: string;
  propertyKeys: string[];
  resolution: "resolved" | "unresolved";
  selectedAltFunctionValue: string;
}

export interface PinAssignmentIssueViewModel {
  id: string;
  title: string;
  summary: string;
}

export interface PinAssignmentAltFunctionOptionViewModel {
  value: string;
  label: string;
  detail: string;
  functionId: number;
  pincm: number | string;
  name: string;
  peripheral: string;
  signal: string;
  direction: string;
}

export interface PinAssignmentsViewModel {
  summary: PinAssignmentSummaryViewModel;
  rows: PinAssignmentRowViewModel[];
  issuesByPinNumber: Record<string, PinAssignmentIssueViewModel[]>;
  propertyValuesByPinNumber: Record<string, Record<string, unknown>>;
  altFunctionOptionsByPinNumber: Record<string, PinAssignmentAltFunctionOptionViewModel[]>;
}