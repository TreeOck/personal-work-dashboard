export interface Commit { sha: string; date: string; project: string; repo: string; repo_path: string; subject: string; body: string; files: string[]; ins: number; del: number; }
export interface Task { id: string; date: string; project: string; kind: "feature" | "fix" | "infra" | "docs"; thread?: string; title: string; summary: string; details: string[]; commits: string[]; }
export interface Note { at: string; text: string; }
export interface TodoItem { id: string; title: string; project: string | null; repo: string | null; status: "todo" | "in_progress" | "done" | "dropped";
  created_at: string; updated_at: string; started_at?: string | null; closed_at: string | null; plan: string | null; notes: Note[]; linked?: string[]; }
export interface InkRef { ink: string; name: string; hex: string; variant: number; }
export interface DeskData { generated_at: string; commits: Commit[]; tasks: Task[]; todo: TodoItem[]; inks: Record<string, InkRef>; }

declare global { interface Window { __DESK_DATA__: DeskData | null; } }

export function readData(): DeskData | null {
  return typeof window !== "undefined" && window.__DESK_DATA__ ? window.__DESK_DATA__ : null;
}
