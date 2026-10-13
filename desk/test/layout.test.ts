import { describe, expect, test } from "vitest";
import { layoutSides, seededRandom, type Block } from "../src/paper/layout";

// Monospace stand-in: every character is 0.6 × size wide.
const measure = (t: string, _l: Block["layer"], size: number) => t.length * size * 0.6;
const box = { width: 100, height: 60 };
const b = (text: string, extra: Partial<Block> = {}): Block => ({ layer: "typed", text, size: 10, minSize: 7, gapBefore: 0, ...extra });
const allText = (sides: ReturnType<typeof layoutSides>) => sides.flat().map(l => l.text).join(" ").replace(/\s+/g, " ").trim();

describe("layoutSides", () => {
  test("short text fits on one side at full size", () => {
    const s = layoutSides([b("hello world")], measure, box);
    expect(s).toHaveLength(1);
    expect(s[0][0]).toMatchObject({ text: "hello world", size: 10 });
  });
  test("a block shrinks toward minSize before spilling", () => {
    const words = Array(14).fill("abcd").join(" ");          // too tall at 10, fits at 8
    const s = layoutSides([b(words)], measure, box);
    expect(s).toHaveLength(1);
    expect(s[0][0].size).toBeLessThan(10);
    expect(s[0][0].size).toBeGreaterThanOrEqual(7);
  });
  test("300-char title spills onto further sides and loses nothing", () => {
    const long = Array(60).fill("lorem").join(" ");
    const s = layoutSides([b(long)], measure, box);
    expect(s.length).toBeGreaterThan(1);
    expect(allText(s)).toBe(long);
    for (const side of s) for (const l of side) expect(measure(l.text, l.layer, l.size)).toBeLessThanOrEqual(box.width + 1e-9);
  });
  test("a single word wider than the box is broken by characters", () => {
    const s = layoutSides([b("x".repeat(40))], measure, box);
    expect(allText(s).replace(/ /g, "")).toBe("x".repeat(40));
    for (const l of s.flat()) expect(measure(l.text, l.layer, l.size)).toBeLessThanOrEqual(box.width + 1e-9);
  });
  test("emoji and CJK survive intact", () => {
    const t = "Fix 🔥 upload — 日本語 テスト ✓";
    expect(allText(layoutSides([b(t)], measure, box))).toBe(t);
  });
  test("lines never overflow the box height", () => {
    const s = layoutSides([b(Array(80).fill("word").join(" ")), b("tail", { layer: "hand", gapBefore: 4 })], measure, box);
    for (const side of s) for (const l of side) expect(l.y).toBeLessThanOrEqual(box.height);
  });
});

test("seededRandom is deterministic per seed", () => {
  const a = seededRandom("t-0019"), b2 = seededRandom("t-0019"), c = seededRandom("t-0020");
  const xs = [a(), a(), a()];
  expect([b2(), b2(), b2()]).toEqual(xs);
  expect(c()).not.toBe(xs[0]);
});

// Review I1: only side 1 is drawn on the desk; content beyond it must be flagged, never silently cut.
import { overflowMark } from "../src/paper/layout";
test("a card with more sides says so; a one-sided card doesn't", () => {
  expect(overflowMark(1)).toBeNull();
  expect(overflowMark(2)).toBe("↷ continued overleaf");
  expect(overflowMark(4)).toBe("↷ continued overleaf (4 sides)");
});

import { pageFooter } from "../src/paper/layout";
test("every page of a multi-page task is numbered; a one-page task isn't", () => {
  expect(pageFooter(0, 1)).toBeNull();
  expect([0, 1, 2].map(i => pageFooter(i, 3))).toEqual(["1/3", "2/3", "3/3"]);
});
