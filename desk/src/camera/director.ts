export type Group = "cards" | "stickies" | "calendar" | "notepad" | "cardPile" | "stickyPile" | "binders";
export type PileId = "cardPile" | "stickyPile";
export interface Item { id: string; group: Group; pages: number; turnable: boolean; pile?: PileId; cyclic?: boolean;   // cyclic: a held stack, thumbed round
  min?: number; start?: number; marks?: number[] }   // binders: never back onto the cover; open at start; ← → jump between marks
export type Frame = { kind: "overview" } | { kind: "focus"; id: string; page: number; dir?: 1 | -1 } | { kind: "fan"; pile: PileId };
export type Stack = Frame[];
export type Action = { type: "select"; id: string; page?: number } | { type: "home" } | { type: "back" } | { type: "turn"; dir: 1 | -1 } | { type: "neighbor"; dir: 1 | -1 }
  | { type: "key"; key: "0" | "1" | "2" | "5" | "6" };

export const START: Stack = [{ kind: "overview" }];
export const top = (s: Stack): Frame => s[s.length - 1];
const KEY_GROUP: Record<"1" | "2" | "5" | "6", Group> = { "1": "cards", "2": "stickies", "5": "calendar", "6": "notepad" };
const isPile = (g: Group): g is PileId => g === "cardPile" || g === "stickyPile";

export function reduce(s: Stack, a: Action, items: Item[]): Stack {
  const byId = new Map(items.map(i => [i.id, i]));
  const t = top(s);
  switch (a.type) {
    case "back": return s.length > 1 ? s.slice(0, -1) : s;
    case "key": {
      const key = a.key;                                        // local const so TypeScript narrows away "0"
      if (key === "0") return START;
      const first = items.find(i => i.group === KEY_GROUP[key] && !i.pile);
      return first ? reduce(START, { type: "select", id: first.id }, items) : s;
    }
    case "select": {
      const it = byId.get(a.id);
      if (!it) return s;
      if (isPile(it.group)) return t.kind === "fan" && t.pile === it.group ? s : [...START, { kind: "fan", pile: it.group }];
      const frame: Frame = { kind: "focus", id: it.id, page: a.page ?? it.start ?? 0 };
      if (it.pile) {                                            // pile members: only from their open fan
        const fan = s.findIndex(f => f.kind === "fan" && f.pile === it.pile);
        return fan < 0 ? s : [...s.slice(0, fan + 1), frame];
      }
      return [...START, frame];
    }
    case "turn": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it?.turnable) return s;
      const lo = it.min ?? 0;
      const page = it.cyclic ? (t.page + a.dir + it.pages) % it.pages                   // thumbed round either way
        : a.dir === 1 ? (t.page < it.pages - 1 ? t.page + 1 : it.min !== undefined ? t.page : 0)   // past the last page: gather (page 0)
        : Math.max(lo, t.page - 1);
      return page === t.page ? s : [...s.slice(0, -1), { ...t, page, dir: a.dir }];
    }
    case "home": {
      const it = t.kind === "focus" ? byId.get(t.id) : undefined;
      if (t.kind !== "focus" || it?.start === undefined || t.page === it.start) return s;
      return [...s.slice(0, -1), { ...t, page: it.start, dir: it.start > t.page ? 1 : -1 }];
    }
    case "neighbor": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it) return s;
      if (it.marks) {                                             // a binder: previous / next period
        const i = it.marks.filter(m => m <= t.page).length - 1;
        const page = a.dir === 1 ? it.marks[Math.min(i + 1, it.marks.length - 1)] : t.page > it.marks[i] ? it.marks[i] : it.marks[Math.max(i - 1, 0)];
        return page === t.page ? s : [...s.slice(0, -1), { ...t, page, dir: a.dir }];
      }
      const peers = items.filter(i => i.group === it.group && i.pile === it.pile);
      const k = peers.findIndex(p => p.id === it.id) + a.dir;
      return k < 0 || k >= peers.length ? s : [...s.slice(0, -1), { kind: "focus", id: peers[k].id, page: 0 }];
    }
  }
}
