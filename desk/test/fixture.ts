import type { DeskData, TodoItem } from "../src/data/types";

export const NOW = new Date("2026-10-13T12:00:00+05:30");
export function item(id: string, status: TodoItem["status"], extra: Partial<TodoItem> = {}): TodoItem {
  return { id, title: `Task ${id}`, project: "alpha", repo: "alpha-be", status, created_at: "2026-10-10T09:00:00+05:30",
    updated_at: "2026-10-10T09:00:00+05:30", started_at: null, closed_at: null, plan: null, notes: [], linked: [], ...extra };
}
export function data(todo: TodoItem[], extra: Partial<DeskData> = {}): DeskData {
  return { generated_at: "2026-10-13T11:00:00+05:30", commits: [], tasks: [], todo,
    inks: { alpha: { ink: "shin-kai", name: "Shin-kai · deep sea", hex: "#1f3a5c", variant: 0 } }, ...extra };
}
