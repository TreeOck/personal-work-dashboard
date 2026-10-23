import type { Commit, DeskData, Note, TodoItem } from "./types";
import palette from "../../../src/personal_tracker/data/inks.json";
import { binderPeriods, type BinderKind, type Period } from "./binders";

export interface Ink { hex: string; name: string; variant: number }
export interface CardVM { id: string; title: string; where: string; ink: Ink; notes: Note[]; commits: Commit[]; started: string | null; closed?: string | null }
export interface DeskModel {
  cards: CardVM[]; cardOverflow: CardVM[]; stickies: CardVM[]; stickyOverflow: CardVM[]; done: CardVM[];
  pens: { project: string; ink: Ink }[];
  today: { ymd: string; day: number; monthName: string; weekday: string };
  week: { commits: number; tasks: number; activeDays: number };
  days: DayTally[];
  binders: Record<BinderKind, Period[]>;
}
export interface DayTally { ymd: string; label: string; commits: number; tasks: number; todosDone: number; first: string | null; last: string | null }
const istHM = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const dayLabel = (ymd: string) => new Date(ymd + "T12:00:00Z").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).replace(",", "");

/** One entry per IST day, newest first, contiguous (days without data are real zero days). */
export function dailyTallies(data: DeskData, now: Date, days = 14): DayTally[] {
  const today = istYmd(now);
  return [...Array(days)].map((_, i) => {
    const ymd = addDays(today, -i);
    const cs = data.commits.filter(c => istYmd(c.date) === ymd).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    return { ymd, label: i === 0 ? "Today" : i === 1 ? "Yesterday" : dayLabel(ymd), commits: cs.length,
      tasks: data.tasks.filter(t => t.date === ymd).length,
      todosDone: data.todo.filter(t => t.status === "done" && t.closed_at && istYmd(t.closed_at) === ymd).length,
      first: cs.length ? istHM(cs[0].date) : null, last: cs.length ? istHM(cs[cs.length - 1].date) : null };
  });
}
export const CAPS = { cards: 6, stickies: 8 } as const;
const FALLBACK = palette.find(p => p.id === "take-sumi")!;
const TZ = "Asia/Kolkata";

export const istYmd = (iso: string | Date) => new Date(iso).toLocaleDateString("en-CA", { timeZone: TZ });
export const addDays = (ymd: string, n: number) => { const d = new Date(ymd + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
export const weekStart = (ymd: string) => addDays(ymd, -((new Date(ymd + "T12:00:00Z").getUTCDay() + 6) % 7));

export function inkFor(project: string | null, data: DeskData): Ink {
  const r = project ? data.inks[project] : undefined;
  return r ? { hex: r.hex, name: r.name, variant: r.variant } : { hex: FALLBACK.hex, name: FALLBACK.name, variant: 0 };
}

export function buildModel(data: DeskData, now: Date): DeskModel {
  const byKey = new Map(data.commits.map(c => [c.repo_path + ":" + c.sha, c]));
  const vm = (i: TodoItem): CardVM => ({ id: i.id, title: i.title, where: [i.project, i.repo].filter(Boolean).join(" / ") || "no project",
    ink: inkFor(i.project, data), notes: i.notes, commits: (i.linked ?? []).map(k => byKey.get(k)).filter((c): c is Commit => !!c),
    started: i.started_at ?? null, closed: i.closed_at });
  const prog = data.todo.filter(i => i.status === "in_progress").sort((a, b) => a.created_at.localeCompare(b.created_at)).map(vm);
  const todo = data.todo.filter(i => i.status === "todo").sort((a, b) => a.created_at.localeCompare(b.created_at)).map(vm);
  const cutoff = now.getTime() - 7 * 864e5;
  const done = data.todo.filter(i => i.status === "done" && i.closed_at && new Date(i.closed_at).getTime() >= cutoff)
    .sort((a, b) => b.closed_at!.localeCompare(a.closed_at!)).map(vm);
  const projects = [...new Set([...data.commits.map(c => c.project), ...data.tasks.map(t => t.project),
    ...data.todo.map(i => i.project).filter((p): p is string => !!p)])].sort();
  const ymd = istYmd(now), ws = weekStart(ymd), we = addDays(ws, 6);
  const inWeek = (d: string) => d >= ws && d <= we;
  const weekCommits = data.commits.filter(c => inWeek(istYmd(c.date)));
  return {
    cards: prog.slice(0, CAPS.cards), cardOverflow: prog.slice(CAPS.cards),
    stickies: todo, stickyOverflow: [],                                   // Plan 2a: stickyLayout() decides singles vs pile
    done,
    pens: projects.map(project => ({ project, ink: inkFor(project, data) })),
    today: { ymd, day: Number(ymd.slice(8)), monthName: now.toLocaleDateString("en-GB", { timeZone: TZ, month: "long" }).toUpperCase(),
      weekday: now.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "long" }) },
    days: dailyTallies(data, now),
    binders: { day: binderPeriods(data, "day", now), week: binderPeriods(data, "week", now), month: binderPeriods(data, "month", now) },
    week: { commits: weekCommits.length, tasks: data.tasks.filter(t => inWeek(t.date)).length,
      activeDays: new Set(weekCommits.map(c => istYmd(c.date))).size },
  };
}
