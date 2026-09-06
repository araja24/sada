import { describe, expect, it } from "vitest";
import { clampPercent, groupByVerse } from "./resultsHelpers";
import type { Tip } from "../api/types";

function tip(verse: number, text: string): Tip {
  return { verse, word_index: null, type: "melody", text };
}

describe("groupByVerse", () => {
  it("groups tips and orders verses numerically", () => {
    const groups = groupByVerse([tip(3, "c"), tip(1, "a"), tip(3, "d"), tip(2, "b")]);
    expect(groups.map((g) => g.verse)).toEqual([1, 2, 3]);
    expect(groups[2].tips.map((t) => t.text)).toEqual(["c", "d"]);
  });

  it("returns nothing for no tips", () => {
    expect(groupByVerse([])).toEqual([]);
  });

  it("orders 2 before 10 rather than lexically", () => {
    expect(groupByVerse([tip(10, "x"), tip(2, "y")]).map((g) => g.verse)).toEqual([2, 10]);
  });
});

describe("clampPercent", () => {
  it("clamps to 0..100", () => {
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(42)).toBe(42);
    expect(clampPercent(140)).toBe(100);
  });
});
