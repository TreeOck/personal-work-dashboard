import { describe, expect, test } from "vitest";
import { buildModel, inkFor, istYmd } from "../src/data/model";
import inks from "../../src/personal_tracker/data/inks.json";
import { NOW, data, item } from "./fixture";

describe("buildModel", () => {
  test("caps cards at 6 with overflow; stickies are all kept (layout piles them)", () => {
    const todo = [...Array(9)].map((_, i) => item(`p${i}`, "in_progress")).concat([...Array(11)].map((_, i) => item(`t${i}`, "todo")));
    const m = buildModel(data(todo), NOW);
    expect([m.cards.length, m.cardOverflow.length, m.stickies.length, m.stickyOverflow.length]).toEqual([6, 3, 11, 0]);
  });
  test("done = last 7 days only, newest first; dropped excluded", () => {
    const m = buildModel(data([
      item("old", "done", { closed_at: "2026-10-05T10:00:00+05:30" }),
      item("a", "done", { closed_at: "2026-10-12T10:00:00+05:30" }),
      item("b", "done", { closed_at: "2026-10-13T09:00:00+05:30" }),
      item("x", "dropped", { closed_at: "2026-10-13T09:00:00+05:30" }),
    ]), NOW);
    expect(m.done.map(c => c.id)).toEqual(["b", "a"]);
  });
  test("item with null project still renders, in the fallback ink", () => {
    const m = buildModel(data([item("n", "todo", { project: null, repo: null })]), NOW);
    expect(m.stickies[0].ink.hex).toBe("#2d2b29");
    expect(m.stickies[0].where).toBe("no project");
  });
  test("empty data gives an empty desk, not an error", () => {
    const m = buildModel(data([]), NOW);
    expect([m.cards, m.stickies, m.done, m.pens]).toEqual([[], [], [], []]);
  });
  test("today is computed in IST even near UTC midnight", () => {
    expect(buildModel(data([]), new Date("2026-10-12T19:00:00Z")).today.ymd).toBe("2026-10-13");
  });
  test("week tallies count commits, tasks and active days Mon-Sun (IST)", () => {
    const c = (date: string) => ({ sha: date, date, project: "alpha", repo: "r", repo_path: "alpha/r", subject: "s", body: "", files: [], ins: 1, del: 0 });
    const d = data([], { commits: [c("2026-10-12T10:00:00+05:30"), c("2026-10-13T10:00:00+05:30"), c("2026-10-11T10:00:00+05:30")],
      tasks: [{ id: "k", date: "2026-10-12", project: "alpha", kind: "feature", title: "t", summary: "s", details: [], commits: [] }] });
    expect(buildModel(d, NOW).week).toEqual({ commits: 2, tasks: 1, activeDays: 2 });
  });
});

test("inkFor falls back for unknown projects", () => {
  expect(inkFor("nope", data([])).hex).toBe("#2d2b29");
  expect(inkFor("alpha", data([])).hex).toBe("#1f3a5c");
});
test("istYmd handles UTC 'Z' timestamps", () => { expect(istYmd("2026-10-05T18:57:40Z")).toBe("2026-10-06"); });

// Spec §4: every ink legible on paper (≥ 4.5:1) in daylight and under the evening lamp.
test("every ink keeps ≥ 4.5:1 contrast on paper in both lights", () => {
  const lin = (c: number) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = ([r, g, b]: number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const rgb = (h: string) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const ratio = (a: number[], b: number[]) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const lamp = [1, 198 / 255, 138 / 255], tint = (c: number[]) => c.map((v, i) => v * lamp[i]);
  const paper = rgb("#f1ebde");
  for (const ink of inks) {
    expect(ratio(rgb(ink.hex), paper), ink.id).toBeGreaterThanOrEqual(4.5);
    expect(ratio(tint(rgb(ink.hex)), tint(paper)), ink.id + " under lamp").toBeGreaterThanOrEqual(4.5);
  }
});

import { dailyTallies } from "../src/data/model";
test("daily tallies: 14 contiguous IST days, newest first, gaps are real zero days", () => {
  const c = (sha: string, date: string) => ({ sha, date, project: "alpha", repo: "r", repo_path: "alpha/r", subject: "s", body: "", files: [], ins: 1, del: 0 });
  const d = data([item("x", "done", { closed_at: "2026-10-13T11:00:00+05:30" })], {
    commits: [c("a", "2026-10-13T09:12:00+05:30"), c("b", "2026-10-13T18:40:00+05:30"), c("z", "2026-10-12T19:00:00Z"), c("y", "2026-10-10T10:00:00+05:30")],
    tasks: [{ id: "k", date: "2026-10-13", project: "alpha", kind: "feature", title: "t", summary: "s", details: [], commits: [] }] });
  const t = dailyTallies(d, NOW);
  expect(t).toHaveLength(14);
  expect(t.map(x => x.ymd).slice(0, 4)).toEqual(["2026-10-13", "2026-10-12", "2026-10-11", "2026-10-10"]);
  expect(t[0]).toEqual({ ymd: "2026-10-13", label: "Today", commits: 3, tasks: 1, todosDone: 1, first: "00:30", last: "18:40" }); // 19:00Z on the 12th = 00:30 IST on the 13th
  expect(t[1]).toMatchObject({ label: "Yesterday", commits: 0, first: null, last: null });
  expect(t[3]).toMatchObject({ label: "Sat 10 Oct", commits: 1 });
});
