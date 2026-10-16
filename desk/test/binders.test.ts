import { expect, test } from "vitest";
import { binderPeriods, binderSheets } from "../src/data/binders";
import type { DeskData, Task } from "../src/data/types";

const task = (id: string, date: string, project: string, thread: string, commits = 1): Task =>
  ({ id, date, project, kind: "feature", thread, title: "T " + id, summary: "S " + id, details: [], commits: Array(commits).fill("abc1234") });
const data: DeskData = { generated_at: "", commits: [], todo: [], inks: { alpha: { ink: "a", name: "A", hex: "#123456", variant: 0 } },
  tasks: [task("1", "2026-09-28", "alpha", "Login"), task("2", "2026-09-28", "alpha", "Login", 3), task("3", "2026-09-28", "beta", "Docs"),
    task("4", "2026-10-05", "alpha", "Login"), task("5", "2026-10-14", "beta", "Docs", 2)] };
const now = new Date("2026-10-16T10:00:00+05:30");

test("day binder: one period per day with tasks, oldest first, plus today even when empty", () => {
  const p = binderPeriods(data, "day", now);
  expect(p.map(x => x.key)).toEqual(["2026-09-28", "2026-10-05", "2026-10-14", "2026-10-16"]);
  expect(p[3]).toMatchObject({ current: true, threads: [], label: "Fri 16 Oct 2026" });
  expect(p[0].threads.map(t => [t.name, t.project, t.tasks.length, t.commits])).toEqual([["Login", "alpha", 2, 4], ["Docs", "beta", 1, 1]]);
  expect(p[0].threads[0].ink.hex).toBe("#123456");
});
test("week and month binders group by Monday-start week and calendar month", () => {
  expect(binderPeriods(data, "week", now).map(x => x.key)).toEqual(["2026-09-28", "2026-10-05", "2026-10-12"]);
  expect(binderPeriods(data, "week", now)[2].label).toBe("Week of 12 Oct 2026");
  const m = binderPeriods(data, "month", now);
  expect(m.map(x => [x.key, x.label])).toEqual([["2026-09", "September 2026"], ["2026-10", "October 2026"]]);
  expect(m[1].days.find(d => d.ymd === "2026-10-14")).toMatchObject({ commits: 2 });
  expect(m[1].days).toHaveLength(31);
});
test("only the most recent periods are kept (a binder holds so many leaves)", () => {
  const many: DeskData = { ...data, tasks: [...Array(80)].map((_, i) => task(String(i), new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), "alpha", "X")) };
  const p = binderPeriods(many, "day", now, 60);
  expect(p).toHaveLength(60); expect(p[59].current).toBe(true);
});
test("sheets: each period takes as many leaves as its text needs; marks point at each period's first sheet (after the cover)", () => {
  const p = binderPeriods(data, "day", now), measure = (t: string, _l: string, size: number) => t.length * size * 0.5;
  const s = binderSheets(p, "day", measure, { width: 186, height: 40 });          // a short page forces continuation leaves
  expect(s.marks[0]).toBe(1);
  expect(s.marks).toHaveLength(p.length);
  expect(s.sheets.length).toBeGreaterThan(p.length);
  expect(s.start).toBe(s.marks[s.marks.length - 1]);
  s.marks.forEach((m, i) => expect(s.sheets[m - 1].period).toBe(i));
});

import * as THREE from "three";
import { binderRack } from "../src/objects/binders";
import type { Focusable } from "../src/scene/focusables";
test("binder stack: taking one out drops the ones above a place; putting it back puts it on top", () => {
  const pose = () => ({ position: new THREE.Vector3(), rotation: new THREE.Euler() });
  const ms = new Map(["d", "w", "m"].map(id => [id, { rest: pose() } as unknown as Focusable]));
  const r = binderRack(ms), y = (id: string) => ms.get(id)!.rest.position.y;
  r.put("d"); r.put("w"); r.put("m");
  const [y0, y1, y2] = [y("d"), y("w"), y("m")];
  expect(y0).toBeLessThan(y1); expect(y1).toBeLessThan(y2);
  expect(r.take("d")).toEqual(["w", "m"]);
  expect([y("w"), y("m")]).toEqual([y0, y1]);
  r.put("d"); expect(r.order()).toEqual(["w", "m", "d"]); expect(y("d")).toBe(y2);
});

import { daySheetFor } from "../src/objects/binders";
test("the calendar opens the Day binder at that date, or the nearest earlier day with a page", () => {
  const keys = ["2026-10-05", "2026-10-09", "2026-10-16"], marks = [1, 3, 4];
  expect(daySheetFor(keys, marks, "2026-10-09")).toBe(3);
  expect(daySheetFor(keys, marks, "2026-10-12")).toBe(3);
  expect(daySheetFor(keys, marks, "2026-10-01")).toBe(1);
});
