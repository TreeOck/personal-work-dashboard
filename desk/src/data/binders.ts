import type { Block, Measure, Side } from "../paper/layout";
import { layoutSides } from "../paper/layout";
import { addDays, inkFor, istYmd, weekStart, type Ink } from "./model";
import type { DeskData } from "./types";

export type BinderKind = "day" | "week" | "month";
export interface Thread { name: string; project: string; ink: Ink; commits: number; tasks: { title: string; summary: string; date: string; commits: number }[] }
export interface Period { key: string; label: string; current: boolean; threads: Thread[]; commits: number;
  days: { ymd: string; commits: number; ink: Ink | null }[] }                 // month binders: one entry per day for the heatmap
export const CAPS: Record<BinderKind, number> = { day: 60, week: 26, month: 12 };

const utc = (ymd: string) => new Date(ymd + "T12:00:00Z");
const fmt = (ymd: string, o: Intl.DateTimeFormatOptions) => utc(ymd).toLocaleDateString("en-GB", { timeZone: "UTC", ...o }).replace(",", "");
const keyOf = (kind: BinderKind, ymd: string) => (kind === "day" ? ymd : kind === "week" ? weekStart(ymd) : ymd.slice(0, 7));
const labelOf = (kind: BinderKind, key: string) => kind === "day" ? fmt(key, { weekday: "short", day: "numeric", month: "short", year: "numeric" })
  : kind === "week" ? "Week of " + fmt(key, { day: "numeric", month: "short", year: "numeric" }) : fmt(key + "-01", { month: "long", year: "numeric" });

/** The periods a binder holds, oldest first: every period with summarised tasks, plus the current one (even if empty), the
 *  most recent `cap` of them. Tasks are grouped by thread, threads in order of first appearance. */
export function binderPeriods(data: DeskData, kind: BinderKind, now: Date, cap = CAPS[kind]): Period[] {
  const today = istYmd(now), cur = keyOf(kind, today), by = new Map<string, DeskData["tasks"]>();
  for (const t of [...data.tasks].sort((a, b) => a.date.localeCompare(b.date))) { const k = keyOf(kind, t.date); by.set(k, [...(by.get(k) ?? []), t]); }
  if (!by.has(cur)) by.set(cur, []);
  return [...by.keys()].filter(k => k <= cur).sort().slice(-cap).map(key => {
    const tasks = by.get(key)!, threads: Thread[] = [];
    for (const t of tasks) {
      const name = t.thread ?? t.title; let th = threads.find(x => x.name === name && x.project === t.project);
      if (!th) threads.push(th = { name, project: t.project, ink: inkFor(t.project, data), commits: 0, tasks: [] });
      th.tasks.push({ title: t.title, summary: t.summary, date: t.date, commits: t.commits.length }); th.commits += t.commits.length;
    }
    const days: Period["days"] = [];
    if (kind === "month") for (let d = key + "-01"; d.startsWith(key); d = addDays(d, 1)) {
      const on = tasks.filter(t => t.date === d), n = on.reduce((a, t) => a + t.commits.length, 0);
      const top = on.sort((a, b) => b.commits.length - a.commits.length)[0];
      days.push({ ymd: d, commits: n, ink: top ? inkFor(top.project, data) : null });
    }
    return { key, label: labelOf(kind, key), current: key === cur, threads, commits: threads.reduce((a, t) => a + t.commits, 0), days };
  });
}

export const HEATMAP_MM = 70;                                   // month: the first leaf keeps this much room for the heatmap
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
/** A period typed up as a report: heading, totals, then each thread underlined in its project's ink with its tasks. */
export function binderBlocks(p: Period, kind: BinderKind): Block[] {
  const tasks = p.threads.reduce((a, t) => a + t.tasks.length, 0);
  const b: Block[] = [{ layer: "typed", text: p.label, size: 7, minSize: 6, gapBefore: kind === "month" ? HEATMAP_MM : 0 },
    { layer: "typed", text: tasks ? `${plural(tasks, "task")} · ${plural(p.commits, "commit")}` : "", size: 3.2, minSize: 3, gapBefore: 1.5 }];
  if (!tasks) b.push({ layer: "hand", text: p.current ? "Nothing logged yet." : "Nothing logged.", size: 6, minSize: 5, gapBefore: 6 });
  for (const t of p.threads) {
    b.push({ layer: "typed", text: `${t.name}  ·  ${t.project}  ·  ${plural(t.commits, "commit")}`, size: 4.2, minSize: 3.6, gapBefore: 6, underline: true, ink: t.ink.hex });
    for (const x of t.tasks) {
      b.push({ layer: "typed", text: (kind === "day" ? "" : fmt(x.date, { weekday: "short", day: "numeric" }) + "  ") + x.title, size: 3.6, minSize: 3.2, gapBefore: 2.5 });
      b.push({ layer: "typed", text: x.summary, size: 3, minSize: 2.6, gapBefore: 0.8 });
    }
  }
  return b.filter(x => x.text);
}

export interface Sheet { period: number; side: Side; part: number; parts: number }
/** Lay every period out on leaves (one side each; long periods continue on the next leaf). Sheet numbers start at 1 because
 *  sheet 0 is the cover: marks[i] is period i's first sheet, start the current period's. */
export function binderSheets(periods: Period[], kind: BinderKind, measure: Measure, box: { width: number; height: number }) {
  const sheets: Sheet[] = [], marks: number[] = [];
  periods.forEach((p, i) => {
    const sides = layoutSides(binderBlocks(p, kind), measure, box);
    marks.push(sheets.length + 1);
    sides.forEach((side, part) => sheets.push({ period: i, side, part, parts: sides.length }));
  });
  return { sheets, marks, start: marks[marks.length - 1] };
}
