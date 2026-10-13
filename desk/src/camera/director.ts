export type Group = "cards" | "stickies" | "calendar" | "notepad" | "cardPile" | "stickyPile";
export type PileId = "cardPile" | "stickyPile";
export interface Item { id: string; group: Group; pages: number; turnable: boolean; pile?: PileId; cyclic?: boolean }   // cyclic: a held stack, thumbed round
export type Frame = { kind: "overview" } | { kind: "focus"; id: string; page: number; dir?: 1 | -1 } | { kind: "fan"; pile: PileId };
export type Stack = Frame[];
export type Action = { type: "select"; id: string } | { type: "back" } | { type: "turn"; dir: 1 | -1 } | { type: "neighbor"; dir: 1 | -1 }
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
      const frame: Frame = { kind: "focus", id: it.id, page: 0 };
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
      const page = it.cyclic ? (t.page + a.dir + it.pages) % it.pages                   // thumbed round either way
        : a.dir === 1 ? (t.page < it.pages - 1 ? t.page + 1 : 0) : Math.max(0, t.page - 1);   // past the last page: gather (page 0)
      return page === t.page ? s : [...s.slice(0, -1), { ...t, page, dir: a.dir }];
    }
    case "neighbor": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it) return s;
      const peers = items.filter(i => i.group === it.group && i.pile === it.pile);
      const k = peers.findIndex(p => p.id === it.id) + a.dir;
      return k < 0 || k >= peers.length ? s : [...s.slice(0, -1), { kind: "focus", id: peers[k].id, page: 0 }];
    }
  }
}
