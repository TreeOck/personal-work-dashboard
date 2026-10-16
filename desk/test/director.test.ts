import { describe, expect, test } from "vitest";
import { START, reduce, top, type Action, type Item, type Stack } from "../src/camera/director";

const items: Item[] = [
  { id: "card:a", group: "cards", pages: 1, turnable: false },
  { id: "card:b", group: "cards", pages: 4, turnable: true },
  { id: "sticky:s", group: "stickies", pages: 2, turnable: true },
  { id: "calendar", group: "calendar", pages: 1, turnable: false },
  { id: "notepad", group: "notepad", pages: 14, turnable: true },
  { id: "cardPile", group: "cardPile", pages: 1, turnable: false },
  { id: "card:p1", group: "cards", pages: 1, turnable: false, pile: "cardPile" },
  { id: "card:p2", group: "cards", pages: 2, turnable: true, pile: "cardPile" },
];
const run = (actions: Action[], from: Stack = START, it = items) => actions.reduce((s, a) => reduce(s, a, it), from);
const page = (s: Stack) => (top(s) as { page: number }).page;

describe("director", () => {
  test("select focuses; back returns; back at overview stays put", () => {
    expect(top(run([{ type: "select", id: "card:a" }]))).toEqual({ kind: "focus", id: "card:a", page: 0 });
    expect(run([{ type: "select", id: "card:a" }, { type: "back" }])).toEqual(START);
    expect(run([{ type: "back" }, { type: "back" }])).toEqual(START);
  });
  test("switching between top-level objects replaces the focus instead of stacking", () => {
    expect(run([{ type: "select", id: "card:a" }, { type: "select", id: "notepad" }])).toEqual([...START, { kind: "focus", id: "notepad", page: 0 }]);
  });
  test("turning forward walks the pages; past the last page the stack is gathered (back to page 1)", () => {
    const pages = [1, 2, 3, 4].map(n => top(run([{ type: "select", id: "card:b" }, ...Array(n).fill({ type: "turn", dir: 1 })])));
    expect(pages.map(f => (f as { page: number }).page)).toEqual([1, 2, 3, 0]);
  });
  test("turning back goes one page back and stops at the first page", () => {
    const s = run([{ type: "select", id: "card:b" }, { type: "turn", dir: 1 }, { type: "turn", dir: 1 }, { type: "turn", dir: -1 }]);
    expect(page(s)).toBe(1);
    expect(run([{ type: "turn", dir: -1 }, { type: "turn", dir: -1 }], s)).toEqual([...START, { kind: "focus", id: "card:b", page: 0, dir: -1 }]);
  });
  test("a one-page task and the calendar have nothing to turn (no state change at all)", () => {
    for (const id of ["card:a", "calendar"]) { const s = run([{ type: "select", id }]); expect(reduce(s, { type: "turn", dir: 1 }, items)).toBe(s); }
    expect(reduce(START, { type: "turn", dir: 1 }, items)).toBe(START);
  });
  test("the notepad turns through its 14 days", () => {
    const pad: Item[] = [{ id: "notepad", group: "notepad", pages: 14, turnable: true }];
    expect(page(run([{ type: "select", id: "notepad" }, ...Array(13).fill({ type: "turn", dir: 1 })], START, pad))).toBe(13);
  });
  test("neighbor moves within the same group, clamped at the ends, starting on page 1", () => {
    expect(top(run([{ type: "select", id: "card:a" }, { type: "neighbor", dir: 1 }]))).toEqual({ kind: "focus", id: "card:b", page: 0 });
    expect(top(run([{ type: "select", id: "card:b" }, { type: "turn", dir: 1 }, { type: "neighbor", dir: 1 }]))).toEqual({ kind: "focus", id: "card:b", page: 1, dir: 1 });
  });
  test("pile: select fans it; members are only reachable from the fan; back goes card → fan → overview", () => {
    expect(run([{ type: "select", id: "card:p1" }])).toEqual(START);
    const s = run([{ type: "select", id: "cardPile" }, { type: "select", id: "card:p1" }]);
    expect(s).toEqual([...START, { kind: "fan", pile: "cardPile" }, { kind: "focus", id: "card:p1", page: 0 }]);
    expect(top(reduce(s, { type: "neighbor", dir: 1 }, items))).toEqual({ kind: "focus", id: "card:p2", page: 0 });
    expect(run([{ type: "back" }, { type: "back" }], s)).toEqual(START);
  });
  test("keys: 1/2/5/6 jump to the first item of their group, 0 resets, empty groups do nothing", () => {
    expect(top(run([{ type: "key", key: "1" }]))).toEqual({ kind: "focus", id: "card:a", page: 0 });
    expect(top(run([{ type: "key", key: "2" }]))).toEqual({ kind: "focus", id: "sticky:s", page: 0 });
    expect(run([{ type: "key", key: "5" }, { type: "key", key: "0" }])).toEqual(START);
    expect(run([{ type: "key", key: "1" }], START, [])).toEqual(START);
  });
  test("unknown ids are ignored; mashing actions never breaks the invariant stack[0] = overview", () => {
    const pool: Action[] = [{ type: "select", id: "card:b" }, { type: "turn", dir: 1 }, { type: "back" }, { type: "select", id: "cardPile" },
      { type: "select", id: "card:p2" }, { type: "neighbor", dir: -1 }, { type: "select", id: "nope" }, { type: "key", key: "6" }];
    let s = START;
    for (let i = 0; i < 300; i++) { s = reduce(s, pool[(i * 7) % 8], items); expect(s[0]).toEqual({ kind: "overview" }); expect(s.length).toBeLessThanOrEqual(3); }
  });
});

// Revision 2: a held card stack is thumbed round (cyclic both ways); every turn says which way it went, because with two
// cards forward and back reach the same page but are different motions.
describe("handheld stacks", () => {
  const held: Item[] = [{ id: "card:h", group: "cards", pages: 3, turnable: true, cyclic: true }, { id: "card:t", group: "cards", pages: 2, turnable: true, cyclic: true }];
  test("Shift+Space on page 1 brings the bottom card up; Space past the last card restores the order", () => {
    expect(top(run([{ type: "select", id: "card:h" }, { type: "turn", dir: -1 }], START, held))).toEqual({ kind: "focus", id: "card:h", page: 2, dir: -1 });
    expect(top(run([{ type: "select", id: "card:h" }, ...Array(3).fill({ type: "turn", dir: 1 })], START, held))).toEqual({ kind: "focus", id: "card:h", page: 0, dir: 1 });
  });
  test("two cards: forward and back both reach the other card, and the frame records which way", () => {
    const s = run([{ type: "select", id: "card:t" }], START, held);
    expect(top(reduce(s, { type: "turn", dir: 1 }, held))).toEqual({ kind: "focus", id: "card:t", page: 1, dir: 1 });
    expect(top(reduce(s, { type: "turn", dir: -1 }, held))).toEqual({ kind: "focus", id: "card:t", page: 1, dir: -1 });
  });
});

// Plan 2b binders: sheet 0 is the cover, so an open binder never shows page 0; it opens at the current period, ← → jump
// between periods (marks = first sheet of each period), Space turns single sheets, Home goes back to the current period.
describe("binders", () => {
  const bind: Item[] = [{ id: "binder:day", group: "binders", pages: 9, turnable: true, min: 1, start: 7, marks: [1, 3, 4, 7, 8] },
    { id: "binder:week", group: "binders", pages: 3, turnable: true, min: 1, start: 2, marks: [1, 2] }];
  const pg = (s: Stack) => (top(s) as { page: number }).page;
  test("opens at the current period, not the cover", () => { expect(pg(run([{ type: "select", id: "binder:day" }], START, bind))).toBe(7); });
  test("← → jump to the previous / next period's first sheet, clamped at both ends", () => {
    const s = run([{ type: "select", id: "binder:day" }], START, bind);
    expect(pg(reduce(s, { type: "neighbor", dir: -1 }, bind))).toBe(4);
    expect(pg(run([{ type: "turn", dir: 1 }, { type: "neighbor", dir: -1 }], s, bind))).toBe(7);    // mid-period: back to its start
    expect(pg(reduce(s, { type: "neighbor", dir: 1 }, bind))).toBe(8);
    expect(reduce(run([{ type: "neighbor", dir: 1 }], s, bind), { type: "neighbor", dir: 1 }, bind)).toEqual(run([{ type: "neighbor", dir: 1 }], s, bind));
  });
  test("Space turns single sheets and never back onto the cover; Home returns to the current period", () => {
    const s = run([{ type: "select", id: "binder:day" }, { type: "neighbor", dir: -1 }, { type: "neighbor", dir: -1 }, { type: "neighbor", dir: -1 }], START, bind);
    expect(pg(s)).toBe(1);
    expect(reduce(s, { type: "turn", dir: -1 }, bind)).toBe(s);
    expect(pg(reduce(s, { type: "turn", dir: 1 }, bind))).toBe(2);
    expect(pg(reduce(s, { type: "home" }, bind))).toBe(7);
  });
  test("select can open at a given sheet (the calendar opens the Day binder at a date)", () => {
    expect(pg(run([{ type: "select", id: "binder:day", page: 3 }], START, bind))).toBe(3);
  });
});

describe("done tray", () => {
  const tray: Item[] = [{ id: "tray", group: "tray", pages: 4, turnable: true, cyclic: true, marks: [0, 1, 2, 3] }];
  test("3 picks the tray up; Space thumbs round; ← → move one sheet, clamped", () => {
    const s = run([{ type: "key", key: "3" }], START, tray);
    expect(top(s)).toEqual({ kind: "focus", id: "tray", page: 0 });
    expect((top(reduce(s, { type: "turn", dir: -1 }, tray)) as { page: number }).page).toBe(3);
    expect((top(reduce(s, { type: "neighbor", dir: 1 }, tray)) as { page: number }).page).toBe(1);
    expect(reduce(s, { type: "neighbor", dir: -1 }, tray)).toBe(s);
  });
});
