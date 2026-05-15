import { describe, expect, it } from "vitest";
import { filterAndRankByFuzzyMatch, scoreFuzzyMatch } from "./fuzzySearch";

describe("fuzzySearch", () => {
  it("prefers direct and token-start matches", () => {
    expect(scoreFuzzyMatch("Save Project", "save pro") ?? 0).toBeGreaterThan(scoreFuzzyMatch("Project Save", "save pro") ?? 0);
  });

  it("filters and ranks subsequence matches", () => {
    const items = ["MSPM0G3507 Board", "Clock Tree", "Save Project"];
    expect(filterAndRankByFuzzyMatch(items, "m0g35", (item) => item)).toEqual(["MSPM0G3507 Board"]);
  });
});