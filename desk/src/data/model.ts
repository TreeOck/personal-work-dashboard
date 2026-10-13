import type { Commit, DeskData, Note, TodoItem } from "./types";
import palette from "./inks.json";

export interface Ink { hex: string; name: string; variant: number }
export interface CardVM { id: string; title: string; where: string; ink: Ink; notes: Note[]; commits: Commit[]; started: string | null }
export interface DeskModel {
  cards: CardVM[]; cardOverflow: CardVM[]; stickies: CardVM[]; stickyOverflow: CardVM[]; done: CardVM[];
  pens: { project: string; ink: Ink }[];
  today: { ymd: string; day: number; monthName: string; weekday: string };
  week: { commits: number; tasks: number; activeDays: number };
}
export const CAPS = { cards: 6, stickies: 8 } as const;
const FALLBACK = palette.find(p => p.id === "take-sumi")!;
const TZ = "Asia/Kolkata";

export const istYmd = (iso: string | Date) => new Date(iso).toLocaleDateString("en-CA", { timeZone: TZ });
const addDays = (ymd: string, n: number) => { const d = new Date(ymd + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekStart = (ymd: string) => addDays(ymd, -((new Date(ymd + "T12:00:00Z").getUTCDay() + 6) % 7));

export function inkFor(project: string | null, data: DeskData): Ink {
  const r = project ? data.inks[project] : undefined;
  return r ? { hex: r.hex, name: r.name, variant: r.variant } : { hex: FALLBACK.hex, name: FALLBACK.name, variant: 0 };
}

export function buildModel(data: DeskData, now: Date): DeskModel {
  const byKey = new Map(data.commits.map(c => [c.repo_path + ":" + c.sha, c]));
  const vm = (i: TodoItem): CardVM => ({ id: i.id, title: i.title, where: [i.project, i.repo].filter(Boolean).join(" / ") || "no project",
    ink: inkFor(i.project, data), notes: i.notes, commits: (i.linked ?? []).map(k => byKey.get(k)).filter((c): c is Commit => !!c),
    started: i.started_at ?? null });
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
    stickies: todo.slice(0, CAPS.stickies), stickyOverflow: todo.slice(CAPS.stickies),
    done,
    pens: projects.map(project => ({ project, ink: inkFor(project, data) })),
    today: { ymd, day: Number(ymd.slice(8)), monthName: now.toLocaleDateString("en-GB", { timeZone: TZ, month: "long" }).toUpperCase(),
      weekday: now.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "long" }) },
    week: { commits: weekCommits.length, tasks: data.tasks.filter(t => inWeek(t.date)).length,
      activeDays: new Set(weekCommits.map(c => istYmd(c.date))).size },
  };
}
