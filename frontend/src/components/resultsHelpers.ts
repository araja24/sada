import type { Tip } from "../api/types";

export interface VerseGroup {
  verse: number;
  tips: Tip[];
}

export function groupByVerse(tips: Tip[]): VerseGroup[] {
  const byVerse = new Map<number, Tip[]>();
  for (const t of tips) {
    const existing = byVerse.get(t.verse);
    if (existing) existing.push(t);
    else byVerse.set(t.verse, [t]);
  }
  return [...byVerse.keys()]
    .sort((a, b) => a - b)
    .map((verse) => ({ verse, tips: byVerse.get(verse) as Tip[] }));
}

export function clampPercent(n: number): number {
  return Math.max(0, Math.min(100, n));
}
