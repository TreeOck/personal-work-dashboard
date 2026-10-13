# 3D Desk, Plan 2a: Focus & Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The desk responds to you:
- **Hover:** objects lift slightly and show a paper name tag.
- **Click:** clicking a card, sticky note, notepad or calendar glides the camera in to read it. Cards and sticky notes flip with `Space` (re-rendered sharp up close), and overflow piles fan out.
- **Navigate:** `Esc`, a right-click or clicking the empty desk goes back; keys `0` `1` `2` `5` `6`, `←` `→` and `Space` work. "Reduce motion" is respected.

**Architecture:**
- **Pure logic in plain TypeScript, unit-tested in Node:** an animator, camera shot maths, a navigation state machine (the "director", a stack of frames), input mapping, pile and fan placements, and the paper card's face orientation.
- **Thin three.js glue on top:** a picking/hover module and a focus controller that turns director states into animations.
- **A frame loop that runs only while something moves,** so the idle desk still renders 0 frames.

**Tech Stack:** TypeScript 7.0.2, three 0.186.1, Vite 8.3.4, vitest 5.0.4 (as in Plan 1). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-13-3d-desk-design.md` (§5 Interactions and animation). Builds on Plan 1: `docs/superpowers/plans/2026-10-13-desk-foundation.md`.

**Not in this plan:**
- **Plan 2b:** done-tray flip-through and the page-curl shader (the same bend gives sticky notes their "peel off" when picked up; in 2a they lift flat), Day/Week/Month binders and their pages, the pen filter, and the calendar → Day binder hand-off. Keys `3` `4` `7` are reserved for these.
- **Plan 3:** the clock lighting and the lamp (key `8`).
- **Plan 4:** drag gestures.

## Global Constraints

- **Camera moves:** 0.6–0.9 s, ease-in-out, on a slight arc. No free orbit. `Esc`, a right-click or clicking empty desk goes back one level (spec §5).
- **Hover:** the object lifts 2–4 mm, its shadow changes, a paper label tag appears, and the cursor becomes a hand (spec §5).
- **Focused card:** fills about 70% of the view (spec §5).
- **Flipping:** cards and sticky notes flip with `Space` or a click, through every side the text needs. A one-sided card flips to its blank back. Sticky notes flip like cards (decided 2026-10-13, spec §5 table).
- **Keyboard:** `0` returns to the overview, `1` cards, `2` sticky notes, `5` calendar, `6` notepad. `←` `→` move between neighbours, `Space` flips and `Esc` goes back. `3` `4` `7` `8` do nothing until Plans 2b/3.
- **Reduced motion:** when `prefers-reduced-motion: reduce` is set, moves are instant cuts covered by a 150 ms canvas fade.
- **Render on demand:** frames render only while something animates or the pointer moves. A static desk renders 0 frames.
- **No coplanar surfaces** (Plan 1 rule): anything resting or lifted sits at least `MIN_GAP` (0.6 mm) clear of the surface below. Fanned and stacked papers each get their own height.
- **Resolution:** the focused card or sticky is re-rendered at 24 px/mm and reverts to 6 px/mm when left. Only one high-resolution texture exists at a time.
- **Data and budget:** no personal data in committed files, `desk.html` stays at or under 25 MB, and no new npm dependencies.

## Review Focus

1. **Rapid input:** clicking another card mid-move, spamming `Esc` or mashing `Space`. The camera retargets smoothly from wherever it is, the director never gets stuck, and flips never leave a card upside down or half-turned. Pinned in Task 1 (animator retarget) and Task 3 (reducer under repeated actions).
2. **Window resized while focused on a card:** the shot is recomputed so the card still fills about 70%. Pinned in Task 2 (the shot depends on aspect) and Task 9 (resize check).
3. **A card that needs 4 or more sides:** `Space` cycles 1→2→3→4→1, and each side shows its own text right-way-up with its "n/total" footer. Pinned in Task 3 (side cycling), Task 5 (back-face orientation) and Task 6 (footers).
4. **Mouse down, move, up (a drag):** must not count as a click. Plan 4's drag gestures depend on this. Pinned in Task 4.
5. **An empty desk, or keys for groups with nothing in them:** `1` with no cards does nothing; no crash, no camera move. Pinned in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `desk/src/anim/animator.ts` | Keyed, time-based tweens with easing; the same key retargets; `busy` flag |
| `desk/src/camera/shots.ts` | `fitDistance` and `focusShot`: where the camera goes to frame an object |
| `desk/src/camera/director.ts` | Navigation state machine: a stack of overview / focus / fan frames |
| `desk/src/interaction/input.ts` | Click vs drag; key → action mapping; reduced-motion duration factor |
| `desk/src/objects/slots.ts` (modify) | Add `pileSlots`, `fanSlots`, `stickyLayout` |
| `desk/src/objects/paperCard.ts` | Two-plane paper card (front + back) with edges; orientation is testable |
| `desk/src/paper/cardTexture.ts` | Render any side of a card or sticky to a canvas at any px/mm, with its footer |
| `desk/src/paper/layout.ts` (modify) | Add `sideFooter` |
| `desk/src/objects/paperObjects.ts` (modify) | Build cards and stickies from `paperCard`; piles; register focusables |
| `desk/src/scene/focusables.ts` | Registry of focusable objects (item, object, size, normal, VM) |
| `desk/src/interaction/picking.ts` | Raycasting, hover lift, HTML label tag, cursor |
| `desk/src/interaction/focus.ts` | Director state → camera moves, lifts, flips, fans, hi-res swaps |
| `desk/src/scene/loop.ts` | Frame loop that runs only while busy |
| `desk/src/main.ts` (modify) | Wire everything; keep the `__desk` test handle |
| `desk/index.html` (modify) | Label tag element and its style |

---

### Task 1: Animator

**Files:**
- Create: `desk/src/anim/animator.ts`
- Test: `desk/test/animator.test.ts`

**Interfaces:**
- Produces: `easeInOutCubic(t: number): number`.
- Produces: `class Animator` with:
  - `play(key: string, duration: number, update: (p: number) => void, now: number, opts?: { done?: () => void; ease?: (t: number) => void | number }): void`. A duration ≤ 0 applies `update(1)` and calls `done` immediately. Calling `play` with an existing key replaces that animation without calling the old `done`.
  - `step(now: number): boolean`, which returns true while anything is still running;
  - `cancel(key: string): void`;
  - `get busy(): boolean`.

- [ ] **Step 1: Write the failing test**

`desk/test/animator.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { Animator, easeInOutCubic } from "../src/anim/animator";

describe("Animator", () => {
  test("eases from 0 to 1 over the duration, then finishes and calls done once", () => {
    const a = new Animator(), seen: number[] = []; let done = 0;
    a.play("cam", 1000, p => seen.push(p), 0, { done: () => done++ });
    expect(a.step(0)).toBe(true); expect(a.step(500)).toBe(true); expect(a.step(1000)).toBe(false); a.step(2000);
    expect(seen[0]).toBe(0); expect(seen[1]).toBeCloseTo(0.5, 6); expect(seen[2]).toBe(1); expect(seen.length).toBe(3);
    expect(done).toBe(1); expect(a.busy).toBe(false);
  });
  test("zero duration applies the end state immediately (reduced motion)", () => {
    const a = new Animator(); let v = 0, done = false;
    a.play("lift", 0, p => (v = p), 123, { done: () => (done = true) });
    expect([v, done, a.busy]).toEqual([1, true, false]);
  });
  test("same key retargets: the old animation stops without its done, the new one runs", () => {
    const a = new Animator(); const log: string[] = [];
    a.play("cam", 1000, p => log.push("A" + p), 0, { done: () => log.push("A done") });
    a.step(100);
    a.play("cam", 1000, p => log.push("B" + p), 100, { done: () => log.push("B done") });
    a.step(1100);
    expect(log.some(l => l === "A done")).toBe(false);
    expect(log[log.length - 1]).toBe("B done");
  });
  test("independent keys run together; cancel stops one", () => {
    const a = new Animator(); let x = 0, y = 0;
    a.play("x", 100, p => (x = p), 0); a.play("y", 100, p => (y = p), 0);
    a.cancel("y"); a.step(100);
    expect([x, y]).toEqual([1, 0]);
  });
  test("easeInOutCubic is symmetric and hits its ends", () => {
    expect([easeInOutCubic(0), easeInOutCubic(1)]).toEqual([0, 1]);
    expect(easeInOutCubic(0.25) + easeInOutCubic(0.75)).toBeCloseTo(1, 12);
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/animator.test.ts`
Expected: FAIL (`Cannot find module '../src/anim/animator'`)

- [ ] **Step 3: Implement**

`desk/src/anim/animator.ts`:
```ts
export const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

interface Anim { start: number; duration: number; update: (p: number) => void; done?: () => void; ease: (t: number) => number }

/** Keyed tweens. Playing a key that is already running replaces it: callers capture their "from" values when they
 *  call play(), so a retarget starts from wherever the object is now (smooth under rapid input). */
export class Animator {
  private anims = new Map<string, Anim>();

  play(key: string, duration: number, update: (p: number) => void, now: number, opts: { done?: () => void; ease?: (t: number) => number } = {}) {
    if (duration <= 0) { this.anims.delete(key); update(1); opts.done?.(); return; }
    this.anims.set(key, { start: now, duration, update, done: opts.done, ease: opts.ease ?? easeInOutCubic });
  }

  step(now: number): boolean {
    for (const [key, a] of [...this.anims]) {
      const p = Math.min(1, Math.max(0, (now - a.start) / a.duration));
      a.update(a.ease(p));
      if (p >= 1) { this.anims.delete(key); a.done?.(); }
    }
    return this.anims.size > 0;
  }

  cancel(key: string) { this.anims.delete(key); }
  get busy() { return this.anims.size > 0; }
}
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/animator.test.ts`
Expected: `5 passed`

- [ ] **Step 5: Commit** (message shown to the user for approval first, CLAUDE.md §6)

---

### Task 2: Camera shots

**Files:**
- Create: `desk/src/camera/shots.ts`
- Test: `desk/test/shots.test.ts`

**Interfaces:**
- Produces: `type V3 = [number, number, number]` and `interface Shot { position: V3; target: V3 }`.
- Produces: `fitDistance(size: { w: number; h: number }, fovDeg: number, aspect: number, fill?: number): number`, the camera distance at which a w×h rectangle facing the camera fills `fill` (default 0.7) of the tighter view axis.
- Produces: `focusShot(center: V3, normal: V3, size: { w: number; h: number }, fovDeg: number, aspect: number, fill?: number): Shot`. Here `position = center + normalize(normal) * fitDistance(...)` and `target = center`.
- Produces: `FLAT_NORMAL: V3`, the view direction for paper lying on the desk, seen from the seated side, tilted 0.35 rad from vertical: `[0, cos 0.35, sin 0.35]`.

- [ ] **Step 1: Write the failing test**

`desk/test/shots.test.ts`:
```ts
import { expect, test } from "vitest";
import { FLAT_NORMAL, fitDistance, focusShot } from "../src/camera/shots";

const projectedFraction = (extent: number, dist: number, fovRad: number) => (extent / 2) / (dist * Math.tan(fovRad / 2));

test("a wide object fills 70% of the horizontal view; a tall one 70% of the vertical", () => {
  const fov = 32, aspect = 16 / 9, v = (fov * Math.PI) / 180, h = 2 * Math.atan(Math.tan(v / 2) * aspect);
  const wide = fitDistance({ w: 0.148, h: 0.03 }, fov, aspect);
  expect(projectedFraction(0.148, wide, h)).toBeCloseTo(0.7, 6);
  const tall = fitDistance({ w: 0.03, h: 0.148 }, fov, aspect);
  expect(projectedFraction(0.148, tall, v)).toBeCloseTo(0.7, 6);
});

test("narrower windows move the camera back so the card still fits (resize while focused)", () => {
  expect(fitDistance({ w: 0.148, h: 0.105 }, 32, 9 / 16)).toBeGreaterThan(fitDistance({ w: 0.148, h: 0.105 }, 32, 16 / 9));
});

test("focusShot places the camera along the normal at the fit distance, aimed at the centre", () => {
  const s = focusShot([0.1, 0.02, 0.2], FLAT_NORMAL, { w: 0.148, h: 0.105 }, 32, 16 / 9);
  const d = fitDistance({ w: 0.148, h: 0.105 }, 32, 16 / 9);
  expect(s.target).toEqual([0.1, 0.02, 0.2]);
  const off = s.position.map((p, i) => p - s.target[i]);
  expect(Math.hypot(...off)).toBeCloseTo(d, 9);
  expect(off[1]).toBeGreaterThan(0); expect(off[2]).toBeGreaterThan(0);     // above, and from the seated (+z) side
  expect(focusShot([0, 0, 0], [0, 2, 0], { w: 1, h: 1 }, 32, 1).position[1]).toBeCloseTo(fitDistance({ w: 1, h: 1 }, 32, 1), 9); // normal is normalised
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/shots.test.ts`
Expected: FAIL (`Cannot find module '../src/camera/shots'`)

- [ ] **Step 3: Implement**

`desk/src/camera/shots.ts`:
```ts
export type V3 = [number, number, number];
export interface Shot { position: V3; target: V3 }

const TILT = 0.35;
/** Paper lying on the desk is viewed from the seated (+z) side, tilted 0.35 rad from straight down. */
export const FLAT_NORMAL: V3 = [0, Math.cos(TILT), Math.sin(TILT)];

/** Distance at which a w×h rectangle facing the camera fills `fill` of the view on its tighter axis. */
export function fitDistance(size: { w: number; h: number }, fovDeg: number, aspect: number, fill = 0.7): number {
  const v = (fovDeg * Math.PI) / 180, h = 2 * Math.atan(Math.tan(v / 2) * aspect);
  return Math.max(size.h / fill / 2 / Math.tan(v / 2), size.w / fill / 2 / Math.tan(h / 2));
}

export function focusShot(center: V3, normal: V3, size: { w: number; h: number }, fovDeg: number, aspect: number, fill = 0.7): Shot {
  const len = Math.hypot(...normal), d = fitDistance(size, fovDeg, aspect, fill);
  return { position: center.map((c, i) => c + (normal[i] / len) * d) as V3, target: [...center] as V3 };
}
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/shots.test.ts`
Expected: `3 passed`

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 3: Director (navigation state machine)

**Files:**
- Create: `desk/src/camera/director.ts`
- Test: `desk/test/director.test.ts`

**Interfaces:**
- Produces: `type Group = "cards" | "stickies" | "calendar" | "notepad" | "cardPile" | "stickyPile"`.
- Produces: `interface Item { id: string; group: Group; sides: number; flippable: boolean; pile?: "cardPile" | "stickyPile" }`. An item with `pile` is a member of that pile and can only be reached from its fan.
- Produces: `type Frame = { kind: "overview" } | { kind: "focus"; id: string; side: number } | { kind: "fan"; pile: "cardPile" | "stickyPile" }`.
- Produces: `type Stack = Frame[]`, where `stack[0]` is always the overview, plus the constant `START: Stack`.
- Produces: `type Action = { type: "select"; id: string } | { type: "back" } | { type: "flip" } | { type: "neighbor"; dir: 1 | -1 } | { type: "key"; key: "0" | "1" | "2" | "5" | "6" }`.
- Produces: `reduce(stack: Stack, action: Action, items: Item[]): Stack` (pure) and `top(stack): Frame`.

- [ ] **Step 1: Write the failing test**

`desk/test/director.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { START, reduce, top, type Action, type Item, type Stack } from "../src/camera/director";

const items: Item[] = [
  { id: "card:a", group: "cards", sides: 1, flippable: true },
  { id: "card:b", group: "cards", sides: 4, flippable: true },
  { id: "sticky:s", group: "stickies", sides: 2, flippable: true },
  { id: "calendar", group: "calendar", sides: 1, flippable: false },
  { id: "notepad", group: "notepad", sides: 1, flippable: false },
  { id: "cardPile", group: "cardPile", sides: 1, flippable: false },
  { id: "card:p1", group: "cards", sides: 1, flippable: true, pile: "cardPile" },
  { id: "card:p2", group: "cards", sides: 2, flippable: true, pile: "cardPile" },
];
const run = (actions: Action[], from: Stack = START, it = items) => actions.reduce((s, a) => reduce(s, a, it), from);

describe("director", () => {
  test("select focuses; back returns; back at overview stays put", () => {
    expect(top(run([{ type: "select", id: "card:a" }]))).toEqual({ kind: "focus", id: "card:a", side: 0 });
    expect(run([{ type: "select", id: "card:a" }, { type: "back" }])).toEqual(START);
    expect(run([{ type: "back" }, { type: "back" }])).toEqual(START);
  });
  test("switching between top-level objects replaces the focus instead of stacking", () => {
    expect(run([{ type: "select", id: "card:a" }, { type: "select", id: "notepad" }])).toEqual([...START, { kind: "focus", id: "notepad", side: 0 }]);
  });
  test("flip cycles through every side and wraps (4 sides: 1→2→3→4→1)", () => {
    const sides = [1, 2, 3, 4].map(n => top(run([{ type: "select", id: "card:b" }, ...Array(n).fill({ type: "flip" })])));
    expect(sides.map(f => (f as { side: number }).side)).toEqual([1, 2, 3, 0]);
  });
  test("a one-sided card flips to its blank back and back again", () => {
    const s = run([{ type: "select", id: "card:a" }, { type: "flip" }]);
    expect((top(s) as { side: number }).side).toBe(1);
    expect((top(reduce(s, { type: "flip" }, items)) as { side: number }).side).toBe(0);
  });
  test("calendar and notepad don't flip; flip at overview does nothing", () => {
    const s = run([{ type: "select", id: "calendar" }]);
    expect(reduce(s, { type: "flip" }, items)).toEqual(s);
    expect(reduce(START, { type: "flip" }, items)).toEqual(START);
  });
  test("neighbor moves within the same group, clamped at the ends, resetting to side 1", () => {
    expect(top(run([{ type: "select", id: "card:a" }, { type: "flip" }, { type: "neighbor", dir: 1 }]))).toEqual({ kind: "focus", id: "card:b", side: 0 });
    expect(top(run([{ type: "select", id: "card:b" }, { type: "neighbor", dir: 1 }]))).toEqual({ kind: "focus", id: "card:b", side: 0 });
  });
  test("pile: select fans it; members are only reachable from the fan; back goes card → fan → overview", () => {
    expect(run([{ type: "select", id: "card:p1" }])).toEqual(START);                 // not from the overview
    const s = run([{ type: "select", id: "cardPile" }, { type: "select", id: "card:p1" }]);
    expect(s).toEqual([...START, { kind: "fan", pile: "cardPile" }, { kind: "focus", id: "card:p1", side: 0 }]);
    expect(top(reduce(s, { type: "neighbor", dir: 1 }, items))).toEqual({ kind: "focus", id: "card:p2", side: 0 });   // neighbours stay in the pile
    expect(run([{ type: "back" }, { type: "back" }], s)).toEqual(START);
  });
  test("keys: 1/2/5/6 jump to the first item of their group, 0 resets, empty groups do nothing", () => {
    expect(top(run([{ type: "key", key: "1" }]))).toEqual({ kind: "focus", id: "card:a", side: 0 });
    expect(top(run([{ type: "key", key: "2" }]))).toEqual({ kind: "focus", id: "sticky:s", side: 0 });
    expect(run([{ type: "key", key: "5" }, { type: "key", key: "0" }])).toEqual(START);
    expect(run([{ type: "key", key: "1" }], START, [])).toEqual(START);               // empty desk
  });
  test("unknown ids are ignored; mashing actions never breaks the invariant stack[0] = overview", () => {
    const actions: Action[] = [];
    for (let i = 0; i < 300; i++) actions.push(([{ type: "select", id: "card:b" }, { type: "flip" }, { type: "back" }, { type: "select", id: "cardPile" },
      { type: "select", id: "card:p2" }, { type: "neighbor", dir: -1 }, { type: "select", id: "nope" }, { type: "key", key: "6" }] as Action[])[(i * 7) % 8]);
    let s = START;
    for (const a of actions) { s = reduce(s, a, items); expect(s[0]).toEqual({ kind: "overview" }); expect(s.length).toBeLessThanOrEqual(3); }
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/director.test.ts`
Expected: FAIL (`Cannot find module '../src/camera/director'`)

- [ ] **Step 3: Implement**

`desk/src/camera/director.ts`:
```ts
export type Group = "cards" | "stickies" | "calendar" | "notepad" | "cardPile" | "stickyPile";
export type PileId = "cardPile" | "stickyPile";
export interface Item { id: string; group: Group; sides: number; flippable: boolean; pile?: PileId }
export type Frame = { kind: "overview" } | { kind: "focus"; id: string; side: number } | { kind: "fan"; pile: PileId };
export type Stack = Frame[];
export type Action = { type: "select"; id: string } | { type: "back" } | { type: "flip" } | { type: "neighbor"; dir: 1 | -1 }
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
      if (a.key === "0") return START;
      const first = items.find(i => i.group === KEY_GROUP[a.key] && !i.pile);
      return first ? reduce(START, { type: "select", id: first.id }, items) : s;
    }
    case "select": {
      const it = byId.get(a.id);
      if (!it) return s;
      if (isPile(it.group)) return t.kind === "fan" && t.pile === it.group ? s : [...START, { kind: "fan", pile: it.group }];
      const frame: Frame = { kind: "focus", id: it.id, side: 0 };
      if (it.pile) {                                            // pile members: only from their open fan
        const fan = s.findIndex(f => f.kind === "fan" && f.pile === it.pile);
        return fan < 0 ? s : [...s.slice(0, fan + 1), frame];
      }
      return [...START, frame];
    }
    case "flip": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it?.flippable) return s;
      return [...s.slice(0, -1), { ...t, side: (t.side + 1) % Math.max(2, it.sides) }];   // one-sided cards flip to their blank back
    }
    case "neighbor": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it) return s;
      const peers = items.filter(i => i.group === it.group && i.pile === it.pile);
      const k = peers.findIndex(p => p.id === it.id) + a.dir;
      return k < 0 || k >= peers.length ? s : [...s.slice(0, -1), { kind: "focus", id: peers[k].id, side: 0 }];
    }
  }
}
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/director.test.ts`
Expected: `9 passed`

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 4: Input mapping (click vs drag, keys, reduced motion)

**Files:**
- Create: `desk/src/interaction/input.ts`
- Test: `desk/test/input.test.ts`

**Interfaces:**
- Consumes: `Action` (Task 3).
- Produces: `isClick(down: { x: number; y: number; t: number }, up: { x: number; y: number; t: number }): boolean`. It's true only when the pointer moved less than 6 px and was held for less than 500 ms.
- Produces: `keyToAction(key: string): Action | null`.
- Produces: `motionFactor(reduce: boolean): number`, which is 0 when reduced motion is on and 1 otherwise.

- [ ] **Step 1: Write the failing test**

`desk/test/input.test.ts`:
```ts
import { expect, test } from "vitest";
import { isClick, keyToAction, motionFactor } from "../src/interaction/input";

test("a short, still press is a click; moving or holding is not (Plan 4 drags rely on this)", () => {
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 13, y: 12, t: 150 })).toBe(true);
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 30, y: 10, t: 150 })).toBe(false);      // dragged 20 px
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 10, y: 10, t: 800 })).toBe(false);      // held
});

test("keys map to director actions; reserved and unknown keys do nothing", () => {
  expect(keyToAction("Escape")).toEqual({ type: "back" });
  expect(keyToAction(" ")).toEqual({ type: "flip" });
  expect(keyToAction("ArrowLeft")).toEqual({ type: "neighbor", dir: -1 });
  expect(keyToAction("ArrowRight")).toEqual({ type: "neighbor", dir: 1 });
  for (const k of ["0", "1", "2", "5", "6"]) expect(keyToAction(k)).toEqual({ type: "key", key: k });
  for (const k of ["3", "4", "7", "8", "x", "Enter"]) expect(keyToAction(k)).toBeNull();
});

test("reduced motion collapses durations to zero", () => {
  expect(motionFactor(true)).toBe(0); expect(motionFactor(false)).toBe(1);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/input.test.ts`
Expected: FAIL (`Cannot find module '../src/interaction/input'`)

- [ ] **Step 3: Implement**

`desk/src/interaction/input.ts`:
```ts
import type { Action } from "../camera/director";

type P = { x: number; y: number; t: number };
export const isClick = (down: P, up: P) => Math.hypot(up.x - down.x, up.y - down.y) < 6 && up.t - down.t < 500;

export function keyToAction(key: string): Action | null {
  switch (key) {
    case "Escape": return { type: "back" };
    case " ": return { type: "flip" };
    case "ArrowLeft": return { type: "neighbor", dir: -1 };
    case "ArrowRight": return { type: "neighbor", dir: 1 };
    case "0": case "1": case "2": case "5": case "6": return { type: "key", key };
    default: return null;                                     // 3, 4, 7 and 8 belong to Plans 2b and 3
  }
}

export const motionFactor = (reduce: boolean) => (reduce ? 0 : 1);
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/input.test.ts`
Expected: `3 passed`

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 5: Two-plane paper card (readable back after a flip)

**Files:**
- Create: `desk/src/objects/paperCard.ts`
- Test: `desk/test/paperCard.test.ts`

**Interfaces:**
- Produces: `makePaperCard(w: number, d: number, front: THREE.Material, back: THREE.Material, edge: THREE.Material): THREE.Group`.
  - Children are named `"front"` (plane facing +y, at y = +PAPER_T/2), `"back"` (plane facing −y, at y = −PAPER_T/2) and `"edge"` (box of height PAPER_T, whose top and bottom faces use an invisible material so nothing overlaps the planes).
  - The card flips about its local x axis (`group.rotation.x += Math.PI`).
- Produces: `faceFor(side: number): "front" | "back"`, which returns `"front"` for even sides and `"back"` for odd ones.

**Why:** a `BoxGeometry` bottom face has mirrored UVs, so text drawn on it would read backwards after a flip. Two planes rotated ±90° about x end up with the same orientation once the card is flipped about x. The test pins this.

- [ ] **Step 1: Write the failing test**

`desk/test/paperCard.test.ts`:
```ts
import * as THREE from "three";
import { expect, test } from "vitest";
import { faceFor, makePaperCard } from "../src/objects/paperCard";

const mat = () => new THREE.MeshBasicMaterial();
// World position of a plane's UV corner (u, v) — e.g. (0,1) is the top-left of the drawn canvas.
function uvCorner(plane: THREE.Mesh, u: number, v: number): THREE.Vector3 {
  const g = plane.geometry as THREE.PlaneGeometry, uv = g.attributes.uv, pos = g.attributes.position;
  for (let i = 0; i < uv.count; i++) if (Math.abs(uv.getX(i) - u) < 1e-6 && Math.abs(uv.getY(i) - v) < 1e-6)
    return new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(plane.matrixWorld);
  throw new Error("corner not found");
}
const facing = (plane: THREE.Object3D) => new THREE.Vector3(0, 0, 1).applyQuaternion(plane.getWorldQuaternion(new THREE.Quaternion()));

test("front reads correctly from the seated side: canvas top-left is far-left, facing up", () => {
  const c = makePaperCard(0.148, 0.105, mat(), mat(), mat()); c.updateMatrixWorld(true);
  const f = c.getObjectByName("front") as THREE.Mesh;
  expect(facing(f).y).toBeCloseTo(1, 6);
  const tl = uvCorner(f, 0, 1); expect(tl.x).toBeLessThan(0); expect(tl.z).toBeLessThan(0);
});

test("after a flip about x, the back faces up and reads the same way (not mirrored, not upside down)", () => {
  const c = makePaperCard(0.148, 0.105, mat(), mat(), mat()); c.rotation.x += Math.PI; c.updateMatrixWorld(true);
  const b = c.getObjectByName("back") as THREE.Mesh;
  expect(facing(b).y).toBeCloseTo(1, 6);
  const tl = uvCorner(b, 0, 1), br = uvCorner(b, 1, 0);
  expect(tl.x).toBeLessThan(0); expect(tl.z).toBeLessThan(0); expect(br.x).toBeGreaterThan(0); expect(br.z).toBeGreaterThan(0);
});

test("faces sit on the card's own surfaces; even sides on the front, odd on the back", () => {
  const c = makePaperCard(0.1, 0.1, mat(), mat(), mat());
  expect((c.getObjectByName("front")!.position.y)).toBeGreaterThan((c.getObjectByName("back")!.position.y));
  expect([0, 1, 2, 3].map(faceFor)).toEqual(["front", "back", "front", "back"]);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/paperCard.test.ts`
Expected: FAIL (`Cannot find module '../src/objects/paperCard'`)

- [ ] **Step 3: Implement**

`desk/src/objects/paperCard.ts`:
```ts
import * as THREE from "three";
import { PAPER_T } from "../scene/layout";

const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });

/** A sheet as two textured planes (front up, back down) plus its four edges. Flip it with rotation.x += π:
 *  both planes are rotated about x, so after the flip the back reads exactly like the front did. */
export function makePaperCard(w: number, d: number, front: THREE.Material, back: THREE.Material, edge: THREE.Material): THREE.Group {
  const g = new THREE.Group();
  const f = new THREE.Mesh(new THREE.PlaneGeometry(w, d), front);
  f.name = "front"; f.rotation.x = -Math.PI / 2; f.position.y = PAPER_T / 2;
  const b = new THREE.Mesh(new THREE.PlaneGeometry(w, d), back);
  b.name = "back"; b.rotation.x = Math.PI / 2; b.position.y = -PAPER_T / 2;
  const e = new THREE.Mesh(new THREE.BoxGeometry(w, PAPER_T, d), [edge, edge, HIDDEN, HIDDEN, edge, edge]);
  e.name = "edge";
  for (const m of [f, b, e]) { m.castShadow = m.receiveShadow = true; g.add(m); }
  return g;
}

export const faceFor = (side: number): "front" | "back" => (side % 2 === 0 ? "front" : "back");
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/paperCard.test.ts`
Expected: `3 passed`. If the second test fails on the z check, the back plane's rotation is wrong. Fix the code, not the test, because the test encodes what a reader sees.

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 6: Side rendering at any resolution, with per-side footers

**Files:**
- Modify: `desk/src/paper/layout.ts` (add `sideFooter`)
- Create: `desk/src/paper/cardTexture.ts`
- Test: `desk/test/layout.test.ts` (append)

**Interfaces:**
- Consumes: `cardBlocks`, `layoutSides` (Plan 1); `drawPaper`, `drawSide`, `canvasMeasure` (Plan 1); `CardVM` (Plan 1).
- Produces: `sideFooter(index: number, total: number): string | null`:
  - `null` for a one-sided card;
  - `"↷ continued overleaf"` on side 1 of 2;
  - `"↷ continued overleaf (i/n)"` on side i of a card with more than 2 sides, where i < n;
  - `"n/n"` on the last side.
- Produces: `type PaperKind = "card" | "sticky"` and `PAPER: Record<PaperKind, { wMm: number; hMm: number; base: string }>`.
- Produces: `cardSides(c: CardVM, kind: PaperKind): Side[]`, which uses the canvas measure and reserves the 6 mm footer strip.
- Produces: `renderSide(c: CardVM, kind: PaperKind, sides: Side[], index: number, pxPerMm: number): HTMLCanvasElement`. When `index >= sides.length` it draws a blank back: paper only.

- [ ] **Step 1: Write the failing test** (append to `desk/test/layout.test.ts`)

```ts
import { sideFooter } from "../src/paper/layout";
test("each side says where it is in the card (and one-sided cards say nothing)", () => {
  expect(sideFooter(0, 1)).toBeNull();
  expect([sideFooter(0, 2), sideFooter(1, 2)]).toEqual(["↷ continued overleaf", "2/2"]);
  expect([0, 1, 2, 3].map(i => sideFooter(i, 4))).toEqual(["↷ continued overleaf (1/4)", "↷ continued overleaf (2/4)", "↷ continued overleaf (3/4)", "4/4"]);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/layout.test.ts`
Expected: FAIL (`sideFooter is not a function`)

- [ ] **Step 3: Implement**

Append to `desk/src/paper/layout.ts`:
```ts

/** Footer for side `index` (0-based) of a card with `total` sides. */
export function sideFooter(index: number, total: number): string | null {
  if (total <= 1) return null;
  if (index >= total - 1) return `${total}/${total}`;
  return total === 2 ? "↷ continued overleaf" : `↷ continued overleaf (${index + 1}/${total})`;
}
```

`desk/src/paper/cardTexture.ts`:
```ts
import type { CardVM } from "../data/model";
import { cardBlocks, layoutSides, sideFooter, type Side } from "./layout";
import { canvasMeasure, drawPaper, drawSide } from "./render";

export type PaperKind = "card" | "sticky";
export const PAPER: Record<PaperKind, { wMm: number; hMm: number; base: string }> = {
  card: { wMm: 148, hMm: 105, base: "#f1ebde" },
  sticky: { wMm: 76, hMm: 76, base: "#f4d675" },
};

/** Lay out a card's text into sides, keeping a 6 mm strip at the bottom free for the footer. */
export const cardSides = (c: CardVM, kind: PaperKind): Side[] =>
  layoutSides(cardBlocks(c, kind), canvasMeasure(), { width: PAPER[kind].wMm - 12, height: PAPER[kind].hMm - 18 });

/** Draw one side at any resolution. index >= sides.length draws the blank back of a one-sided card. */
export function renderSide(c: CardVM, kind: PaperKind, sides: Side[], index: number, pxPerMm: number): HTMLCanvasElement {
  const { wMm, hMm, base } = PAPER[kind];
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(wMm * pxPerMm); canvas.height = Math.round(hMm * pxPerMm);
  const ctx = canvas.getContext("2d")!;
  drawPaper(ctx, canvas.width, canvas.height, base, c.id + ":" + index);
  if (index >= sides.length) return canvas;
  drawSide(ctx, sides[index], c.ink.hex, c.id + ":" + index, pxPerMm);
  const footer = sideFooter(index, sides.length);
  if (footer) {
    ctx.save(); ctx.fillStyle = c.ink.hex; ctx.globalAlpha = 0.9; ctx.font = `${4.2 * 1.25 * pxPerMm}px 'Caveat'`; ctx.textAlign = "right";
    ctx.fillText(footer, (wMm - 5) * pxPerMm, (hMm - 4) * pxPerMm); ctx.restore();
  }
  return canvas;
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd desk && npx vitest run test/layout.test.ts`
Expected: all pass (9 previous + 1 new = `10 passed`).

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 7: Piles, fans and sticky layout (pure placement)

**Files:**
- Modify: `desk/src/objects/slots.ts`
- Modify: `desk/src/scene/layout.ts` (add `CARD_PILE`)
- Test: `desk/test/objects.test.ts` (append)

**Interfaces:**
- Consumes: `CARD_SIZE`, `MAT`, `MIN_GAP`, `PAPER_T`, `restOn`, `stackY` (Plan 1); `stickySlots` (Plan 1).
- Produces: `CARD_PILE = { x: -0.352, z: 0.17, rotY: Math.PI / 2 }`. That's the mat's left margin: rotated, the pile fits between the mat edge (x −0.41) and the first card column (x −0.294).
- Produces: `pileSlots(n: number): { y: number }[]`, the bottom y of each pile card, starting at `restOn(MAT.t)`.
- Produces: `fanSlots(n: number, size: { w: number; d: number }): { x: number; y: number; z: number; rotY: number }[]`. It's a 3-column grid over the mat, lifted 2 cm, with every card at its own height.
- Produces: `stickyLayout(total: number): { singles: number; pile: number }`. With up to 8 sticky notes, all are singles. With more, 7 are singles and the rest form a pile in slot 8.

- [ ] **Step 1: Write the failing test** (append to `desk/test/objects.test.ts`)

```ts
// Plan 2a: overflow piles and the fan they open into.
import { CARD_PILE } from "../src/scene/layout";
import { fanSlots, pileSlots, stickyLayout } from "../src/objects/slots";

test("the card pile sits in the mat's left margin, clear of the card grid, on the mat", () => {
  const halfW = CARD_SIZE.d / 2, halfD = CARD_SIZE.w / 2;                 // rotated 90°
  expect(CARD_PILE.x - halfW).toBeGreaterThanOrEqual(MAT.x - MAT.w / 2);
  const grid = cardSlots(6); const leftCol = Math.min(...grid.map(s => s.x)) - CARD_SIZE.w / 2;
  expect(CARD_PILE.x + halfW).toBeLessThan(leftCol);
  expect(CARD_PILE.z - halfD).toBeGreaterThanOrEqual(MAT.z - MAT.d / 2); expect(CARD_PILE.z + halfD).toBeLessThanOrEqual(MAT.z + MAT.d / 2);
  const p = pileSlots(5);
  expect(p[0].y).toBeCloseTo(MAT.t + MIN_GAP, 12);
  for (let i = 1; i < p.length; i++) expect(p[i].y - p[i - 1].y).toBeCloseTo(PAPER_T + MIN_GAP, 12);
});

test("fanned cards are lifted, each at its own height, and stay over the desk", () => {
  const f = fanSlots(14, CARD_SIZE);
  expect(f.length).toBe(14);
  for (let i = 0; i < f.length; i++) {
    expect(f[i].y).toBeGreaterThan(MAT.t + 0.015);
    if (i) expect(f[i].y - f[i - 1].y).toBeGreaterThanOrEqual(PAPER_T + MIN_GAP - 1e-12);
    expect(Math.abs(f[i].x)).toBeLessThan(0.8 - CARD_SIZE.w / 2); expect(Math.abs(f[i].z)).toBeLessThan(0.4 - CARD_SIZE.d / 2);
  }
});

test("sticky notes: up to 8 singles; beyond that 7 singles and a pile in slot 8", () => {
  expect(stickyLayout(0)).toEqual({ singles: 0, pile: 0 });
  expect(stickyLayout(8)).toEqual({ singles: 8, pile: 0 });
  expect(stickyLayout(12)).toEqual({ singles: 7, pile: 5 });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/objects.test.ts`
Expected: FAIL (`CARD_PILE` undefined / `fanSlots is not a function`)

- [ ] **Step 3: Implement**

Add to `desk/src/scene/layout.ts`, after `MAT`:
```ts
export const CARD_PILE = { x: -0.352, z: 0.17, rotY: Math.PI / 2 } as const;   // mat's left margin, rotated to fit
```

Append to `desk/src/objects/slots.ts`:
```ts

/** Bottom y of each card in the overflow pile, starting just above the mat. */
export const pileSlots = (n: number) => [...Array(n)].map((_, i) => ({ y: stackY(restOn(MAT.t), i, PAPER_T) }));

/** Where a pile's cards go when fanned open: a 3-column grid over the mat, 2 cm up, each at its own height. */
export function fanSlots(n: number, size: { w: number; d: number }) {
  const cols = 3, gx = size.w + 0.015, gz = size.d + 0.015, r = seededRandom("fan");
  return [...Array(n)].map((_, i) => {
    const page = Math.floor(i / 9), k = i % 9;                         // past 9, later cards stagger over earlier ones
    return { x: MAT.x + (k % cols - 1) * gx + page * 0.03, z: MAT.z + (Math.floor(k / cols) - 1) * gz + page * 0.03,
      y: MAT.t + 0.02 + i * (PAPER_T + MIN_GAP), rotY: (r() - 0.5) * 0.06 };
  });
}

export const stickyLayout = (total: number) => (total <= 8 ? { singles: total, pile: 0 } : { singles: 7, pile: total - 7 });
```
`MAT` must be in the existing `slots.ts` import list from `../scene/layout`; add it if it's missing.

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/objects.test.ts`
Expected: all pass (12 previous + 3 new = `15 passed`).

- [ ] **Step 5: Commit** (message shown to the user for approval first)

---

### Task 8: Build cards, stickies and piles as focusables

**Files:**
- Create: `desk/src/scene/focusables.ts`
- Modify: `desk/src/objects/paperObjects.ts` (cards and stickies use `makePaperCard`; add piles; register focusables)
- Modify: `desk/src/objects/stationery.ts` (register calendar and notepad)
- Modify: `desk/src/objects/index.ts` (`buildObjects` returns the registry)
- Modify: `desk/src/data/model.ts` (no cap on stickies: `stickies` holds all, layout decides)

**Interfaces:**
- Consumes: `makePaperCard` (Task 5); `cardSides`, `renderSide`, `PAPER` (Task 6); `pileSlots`, `fanSlots`, `stickyLayout`, `CARD_PILE` (Task 7); `Item` (Task 3); `FLAT_NORMAL`, `V3` (Task 2).
- Produces, in `desk/src/scene/focusables.ts`:
  ```ts
  export interface Focusable {
    item: Item;                         // what the director sees
    object: THREE.Object3D;             // what moves
    size: { w: number; h: number };     // what the camera frames (metres)
    normal: V3;                         // which side the camera looks from
    paper?: { vm: CardVM; kind: PaperKind; sides: Side[]; low: [THREE.Texture, THREE.Texture] };   // cards and stickies
    home: { position: THREE.Vector3; rotation: THREE.Euler };   // where it rests
  }
  export class Registry {
    add(f: Focusable): void;
    get(id: string): Focusable | undefined;
    items(): Item[];
    ofObject(o: THREE.Object3D): Focusable | undefined;   // walks up parents to the registered object
  }
  ```
- Produces: `buildObjects(scene, model, m, matTop): Registry`.

- [ ] **Step 1: Write the failing test**

`desk/test/focusables.test.ts`:
```ts
import * as THREE from "three";
import { expect, test } from "vitest";
import { Registry } from "../src/scene/focusables";

test("registry finds the focusable from any nested child and lists director items in insertion order", () => {
  const r = new Registry(), card = new THREE.Group(), child = new THREE.Mesh(); card.add(child);
  r.add({ item: { id: "card:a", group: "cards", sides: 2, flippable: true }, object: card, size: { w: 0.148, h: 0.105 }, normal: [0, 1, 0],
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } });
  r.add({ item: { id: "notepad", group: "notepad", sides: 1, flippable: false }, object: new THREE.Group(), size: { w: 0.1, h: 0.14 }, normal: [0, 1, 0],
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } });
  expect(r.ofObject(child)?.item.id).toBe("card:a");
  expect(r.ofObject(new THREE.Mesh())).toBeUndefined();
  expect(r.items().map(i => i.id)).toEqual(["card:a", "notepad"]);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/focusables.test.ts`
Expected: FAIL (`Cannot find module '../src/scene/focusables'`)

- [ ] **Step 3: Implement the registry**

`desk/src/scene/focusables.ts`:
```ts
import * as THREE from "three";
import type { Item } from "../camera/director";
import type { V3 } from "../camera/shots";
import type { CardVM } from "../data/model";
import type { PaperKind } from "../paper/cardTexture";
import type { Side } from "../paper/layout";

export interface Focusable {
  item: Item;
  object: THREE.Object3D;
  size: { w: number; h: number };
  normal: V3;
  paper?: { vm: CardVM; kind: PaperKind; sides: Side[]; low: [THREE.Texture, THREE.Texture] };
  home: { position: THREE.Vector3; rotation: THREE.Euler };
}

export class Registry {
  private byId = new Map<string, Focusable>();
  private byObject = new Map<THREE.Object3D, Focusable>();
  add(f: Focusable) { this.byId.set(f.item.id, f); this.byObject.set(f.object, f); }
  get(id: string) { return this.byId.get(id); }
  items(): Item[] { return [...this.byId.values()].map(f => f.item); }
  all(): Focusable[] { return [...this.byId.values()]; }
  ofObject(o: THREE.Object3D | null): Focusable | undefined {
    for (let n: THREE.Object3D | null = o; n; n = n.parent) { const f = this.byObject.get(n); if (f) return f; }
    return undefined;
  }
}
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `cd desk && npx vitest run test/focusables.test.ts`
Expected: `1 passed`

- [ ] **Step 5: Rebuild cards and stickies as focusable paper cards**

In `desk/src/data/model.ts`, the sticky cap moves to placement. Replace:
```ts
    stickies: todo.slice(0, CAPS.stickies), stickyOverflow: todo.slice(CAPS.stickies),
```
with:
```ts
    stickies: todo, stickyOverflow: [],                                   // Plan 2a: stickyLayout() decides singles vs pile
```
Then update the cap test in `desk/test/model.test.ts`. The line `expect([m.cards.length, m.cardOverflow.length, m.stickies.length, m.stickyOverflow.length]).toEqual([6, 3, 8, 3]);` becomes `toEqual([6, 3, 11, 0])`, and the test name becomes `"caps cards at 6 with overflow; stickies are all kept (layout piles them)"`.

In `desk/src/objects/paperObjects.ts`, replace `addCards` and `addStickies` with this version, and keep `addTray`, `stackBlock`, `sheet` and `textureFor` as they are:
```ts
import { FLAT_NORMAL } from "../camera/shots";
import { cardSides, PAPER, renderSide, type PaperKind } from "../paper/cardTexture";
import { CARD_PILE, MAT } from "../scene/layout";
import { Registry } from "../scene/focusables";
import { makePaperCard } from "./paperCard";
import { pileSlots, stickyLayout } from "./slots";

const LOW_PX = 6;   // overview resolution; focus re-renders at 24 px/mm (Task 10)
const canvasTexture = (c: HTMLCanvasElement) => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

/** One focusable card or sticky: front shows side 1, back shows side 2 (or the blank back). */
function paperItem(m: M, vm: CardVM, kind: PaperKind, id: string, group: "cards" | "stickies", pile?: "cardPile" | "stickyPile") {
  const sides = cardSides(vm, kind);
  const low: [THREE.Texture, THREE.Texture] = [canvasTexture(renderSide(vm, kind, sides, 0, LOW_PX)), canvasTexture(renderSide(vm, kind, sides, 1, LOW_PX))];
  const size = { w: PAPER[kind].wMm / 1000, h: PAPER[kind].hMm / 1000 };
  const obj = makePaperCard(size.w, size.h, m.paper(low[0]), m.paper(low[1]), m.paper());
  obj.name = id;
  return { obj, focusable: { item: { id, group, sides: sides.length, flippable: true, pile }, object: obj, size, normal: FLAT_NORMAL,
    paper: { vm, kind, sides, low }, home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } } };
}
const rest = (f: { object: THREE.Object3D; home: { position: THREE.Vector3; rotation: THREE.Euler } }) => {
  f.home.position.copy(f.object.position); f.home.rotation.copy(f.object.rotation); };

export function addCards(scene: THREE.Scene, model: DeskModel, m: M, matTop: number, reg: Registry) {
  cardSlots(model.cards.length).forEach((s, i) => {
    const { obj, focusable } = paperItem(m, model.cards[i], "card", "card:" + model.cards[i].id, "cards");
    obj.position.set(s.x, restOn(matTop) + PAPER_T / 2, s.z); obj.rotation.y = s.rotY; scene.add(obj); rest(focusable); reg.add(focusable);
  });
  if (model.cardOverflow.length) {                                         // overflow pile in the mat's left margin
    const pile = new THREE.Group(); pile.name = "cardPile"; scene.add(pile);
    reg.add({ item: { id: "cardPile", group: "cardPile", sides: 1, flippable: false }, object: pile, size: { w: 0.33, h: 0.42 },
      normal: FLAT_NORMAL, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    pileSlots(model.cardOverflow.length).forEach((p, i) => {
      const vm = model.cardOverflow[i], { obj, focusable } = paperItem(m, vm, "card", "card:" + vm.id, "cards", "cardPile");
      obj.position.set(CARD_PILE.x, p.y + PAPER_T / 2, CARD_PILE.z); obj.rotation.y = CARD_PILE.rotY; pile.add(obj); rest(focusable); reg.add(focusable);
    });
  }
  if (!model.cards.length && !model.stickies.length) {   // spec §8: an empty desk gets one note
    const note: CardVM = { id: "empty", title: "Nothing on the go", where: "", ink: { hex: "#2d2b29", name: "", variant: 0 }, notes: [], commits: [], started: null };
    const { texture } = textureFor(note, "sticky", 76, 76, "#f4d675");
    const s = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006); s.position.set(-0.05, s.position.y, 0.12); scene.add(s);
  }
}

export function addStickies(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const { singles, pile } = stickyLayout(model.stickies.length), slots = stickySlots(8);
  model.stickies.slice(0, singles).forEach((vm, i) => {
    const { obj, focusable } = paperItem(m, vm, "sticky", "sticky:" + vm.id, "stickies");
    obj.position.set(slots[i].x, restOn(0) + PAPER_T / 2, slots[i].z); obj.rotation.y = slots[i].rotY; scene.add(obj); rest(focusable); reg.add(focusable);
  });
  if (pile) {                                                              // the rest pile up in slot 8
    const group = new THREE.Group(); group.name = "stickyPile"; scene.add(group);
    reg.add({ item: { id: "stickyPile", group: "stickyPile", sides: 1, flippable: false }, object: group, size: { w: 0.33, h: 0.42 },
      normal: FLAT_NORMAL, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    model.stickies.slice(singles).forEach((vm, i) => {
      const { obj, focusable } = paperItem(m, vm, "sticky", "sticky:" + vm.id, "stickies", "stickyPile");
      obj.position.set(slots[7].x, stackY(restOn(0), i, PAPER_T) + PAPER_T / 2, slots[7].z); obj.rotation.y = slots[7].rotY + i * 0.04;
      group.add(obj); rest(focusable); reg.add(focusable);
    });
  }
}
```
Update the imports at the top of `paperObjects.ts` so `restOn` and `stackY` come from `../scene/layout`, `stickySlots` comes from `./slots`, and `CardVM` and `DeskModel` remain.

In `desk/src/objects/stationery.ts`, register the calendar and notepad. Add a `reg: Registry` parameter to `addCalendar(scene, model, m, reg)` and `addNotepad(scene, model, m, reg)`, and at the end of each function call:
```ts
  // in addCalendar, after scene.add(easel):
  reg.add({ item: { id: "calendar", group: "calendar", sides: 1, flippable: false }, object: easel, size: { w: CALENDAR.w, h: CALENDAR.h },
    normal: [0, Math.sin(0.3), Math.cos(0.3)], home: { position: easel.position.clone(), rotation: easel.rotation.clone() } });
  // in addNotepad, after scene.add(pad):
  reg.add({ item: { id: "notepad", group: "notepad", sides: 1, flippable: false }, object: pad, size: { w: NOTEPAD.w, h: NOTEPAD.d },
    normal: FLAT_NORMAL, home: { position: pad.position.clone(), rotation: pad.rotation.clone() } });
```
(Import `Registry` from `../scene/focusables` and `FLAT_NORMAL` from `../camera/shots`.)

Replace `desk/src/objects/index.ts`:
```ts
import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { Registry } from "../scene/focusables";
import type { materials } from "../scene/materials";
import { addCards, addStickies, addTray } from "./paperObjects";
import { addPenCup } from "./pens";
import { addBinders, addCalendar, addNotepad } from "./stationery";

export function buildObjects(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>, matTop: number): Registry {
  const reg = new Registry();
  addCards(scene, model, m, matTop, reg);
  addStickies(scene, model, m, reg);
  addTray(scene, model, m, m.walnut);
  addPenCup(scene, model, m);
  addCalendar(scene, model, m, reg);
  addNotepad(scene, model, m, reg);
  addBinders(scene, m);
  return reg;
}
```

- [ ] **Step 6: Type-check and run the whole suite**

Run: `cd desk && npx tsc --noEmit && npx vitest run`
Expected: tsc clean; all tests pass. That's 33 from Plan 1, plus 5 + 3 + 9 + 3 + 3 + 1 + 3 + 1 new = `61 passed`.

- [ ] **Step 7: Build and check the overview didn't change**

Run: `cd desk && npm run build && cd .. && python3 build.py`. Then open `desk.html` in the browser and check:
- `__desk.scene` contains `card:<id>` groups with `front` / `back` / `edge` children;
- the overview screenshot looks the same as Plan 1's final screenshot (cards readable, nothing floating);
- there are 0 renders over 2 s idle.
- [ ] **Step 8: Commit** (message shown to the user for approval first)

---

### Task 9: Frame loop, picking, hover tag, focus controller, wiring

**Files:**
- Create: `desk/src/scene/loop.ts`, `desk/src/interaction/picking.ts`, `desk/src/interaction/focus.ts`
- Modify: `desk/src/main.ts`, `desk/index.html`
- Test: browser checks (Step 6). These modules are the three.js/DOM glue around the pure logic tested in Tasks 1–7.

**Interfaces:**
- Consumes: `Animator` (Task 1); `focusShot`, `FLAT_NORMAL`, `Shot` (Task 2); `reduce`, `top`, `START`, `Stack`, `Action` (Task 3); `isClick`, `keyToAction`, `motionFactor` (Task 4); `faceFor` (Task 5); `renderSide` (Task 6); `fanSlots` (Task 7); `Registry` and `Focusable` (Task 8); `OVERVIEW` and `CAMERA` (Plan 1).
- Produces: `createLoop(render: () => void, busy: () => boolean): { kick(): void }`. It runs requestAnimationFrame only while `busy()` is true, then renders one final frame and stops.
- Produces: `createFocus(ctx): { dispatch(a: Action): void; stack(): Stack; tick(now: number): boolean; onResize(): void }`.
- Produces: `createPicking(ctx): { onPointerMove(e), onPointerDown(e), onPointerUp(e), tick(now): boolean }`.
- The `window.__desk` handle gains `focus` (dispatch/stack) for browser checks.

- [ ] **Step 1: Loop**

`desk/src/scene/loop.ts`:
```ts
/** Render frames only while something is moving; then one final frame, then stop (idle desk = 0 renders). */
export function createLoop(render: () => void, busy: () => boolean) {
  let running = false;
  const frame = () => { const more = busy(); render(); if (more) requestAnimationFrame(frame); else running = false; };
  return { kick() { if (!running) { running = true; requestAnimationFrame(frame); } } };
}
```

- [ ] **Step 2: Focus controller**

`desk/src/interaction/focus.ts`:
```ts
import * as THREE from "three";
import { Animator } from "../anim/animator";
import { reduce, START, top, type Action, type Frame, type Stack } from "../camera/director";
import { FLAT_NORMAL, focusShot, type Shot, type V3 } from "../camera/shots";
import { faceFor } from "../objects/paperCard";
import { fanSlots } from "../objects/slots";
import { renderSide } from "../paper/cardTexture";
import { CAMERA, OVERVIEW } from "../scene/depth";
import type { Focusable, Registry } from "../scene/focusables";

const HI_PX = 24, LIFT = 0.015, CAM_MS = 750, LIFT_MS = 400, FLIP_MS = 520, FAN_MS = 600;

interface Ctx { camera: THREE.PerspectiveCamera; reg: Registry; animator: Animator; kick: () => void; motion: number;
  fade: () => void; parallax: () => THREE.Vector3 }

export function createFocus(ctx: Ctx) {
  const { camera, reg, animator } = ctx;
  let stack: Stack = START;
  const camPos = new THREE.Vector3(...OVERVIEW.position), camTarget = new THREE.Vector3(...OVERVIEW.target);
  let hi: { f: Focusable; face: "front" | "back"; tex: THREE.Texture } | null = null;
  const sideShown = new Map<string, number>();                         // side currently on top of each card
  const now = () => performance.now();
  const ms = (d: number) => d * ctx.motion;

  function shotFor(frame: Frame): Shot {
    if (frame.kind === "overview") return { position: [...OVERVIEW.position], target: [...OVERVIEW.target] };
    if (frame.kind === "fan") { const f = reg.get(frame.pile)!; const c = f.home.position;
      return focusShot([c.x, c.y + 0.02, c.z], FLAT_NORMAL, f.size, CAMERA.fov, camera.aspect, 0.9); }
    const f = reg.get(frame.id)!; const c = f.object.getWorldPosition(new THREE.Vector3());
    const lifted: V3 = [c.x, c.y + (f.paper ? LIFT : 0), c.z];
    return focusShot(lifted, f.normal, f.size, CAMERA.fov, camera.aspect);
  }

  function moveCamera(shot: Shot) {
    const fromP = camPos.clone(), fromT = camTarget.clone(), toP = new THREE.Vector3(...shot.position), toT = new THREE.Vector3(...shot.target);
    const arc = fromP.distanceTo(toP) * 0.12;                                  // slight arc, like a handheld move
    if (ctx.motion === 0) ctx.fade();
    animator.play("camera", ms(CAM_MS), p => {
      camPos.lerpVectors(fromP, toP, p); camPos.y += Math.sin(p * Math.PI) * arc; camTarget.lerpVectors(fromT, toT, p);
    }, now());
  }

  function liftTo(f: Focusable, up: boolean) {
    const from = f.object.position.y, to = f.home.position.y + (up ? LIFT : 0);
    animator.play("lift:" + f.item.id, ms(LIFT_MS), p => { f.object.position.y = from + (to - from) * p; }, now());
  }

  function setHiRes(f: Focusable | null, side: number) {
    if (hi) { (hi.f.object.getObjectByName(hi.face) as THREE.Mesh).material = hiMaterial(hi.f, hi.face, hi.f.paper!.low[hi.face === "front" ? 0 : 1]); hi.tex.dispose(); hi = null; }
    if (!f?.paper) return;
    const face = faceFor(side), tex = new THREE.CanvasTexture(renderSide(f.paper.vm, f.paper.kind, f.paper.sides, side, HI_PX));
    tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 16;
    (f.object.getObjectByName(face) as THREE.Mesh).material = hiMaterial(f, face, tex); hi = { f, face, tex };
  }
  const hiMaterial = (f: Focusable, face: "front" | "back", tex: THREE.Texture) => {
    const m = ((f.object.getObjectByName(face) as THREE.Mesh).material as THREE.MeshPhysicalMaterial).clone(); m.map = tex; return m; };

  function flipTo(f: Focusable, side: number) {
    const shown = sideShown.get(f.item.id) ?? 0;
    if (side === shown) return;
    // draw the incoming side onto the face that will end up on top, then turn the card over
    const face = faceFor(side);
    const tex = new THREE.CanvasTexture(renderSide(f.paper!.vm, f.paper!.kind, f.paper!.sides, side, HI_PX)); tex.colorSpace = THREE.SRGBColorSpace;
    const mesh = f.object.getObjectByName(face) as THREE.Mesh; mesh.material = hiMaterial(f, face, tex);
    if (hi) hi.tex.dispose(); hi = { f, face, tex };
    const from = f.object.rotation.x, to = side % 2 === 0 ? 0 : Math.PI, baseY = f.home.position.y + LIFT;
    animator.play("flip:" + f.item.id, ms(FLIP_MS), p => {
      f.object.rotation.x = from + (to - from) * p; f.object.position.y = baseY + Math.sin(p * Math.PI) * 0.03;   // lift while turning
    }, now());
    sideShown.set(f.item.id, side);
  }

  function restCard(f: Focusable) {
    const fromR = f.object.rotation.x, fromP = f.object.position.clone();
    animator.play("rest:" + f.item.id, ms(LIFT_MS), p => {
      f.object.rotation.x = fromR * (1 - p); f.object.position.lerpVectors(fromP, f.home.position, p);
    }, now(), { done: () => { if (f.paper) { (f.object.getObjectByName("front") as THREE.Mesh).material = hiMaterial(f, "front", f.paper.low[0]);
      (f.object.getObjectByName("back") as THREE.Mesh).material = hiMaterial(f, "back", f.paper.low[1]); } sideShown.set(f.item.id, 0); } });
  }

  function fan(pile: "cardPile" | "stickyPile", open: boolean) {
    const members = reg.all().filter(f => f.item.pile === pile);
    const slots = fanSlots(members.length, members[0]?.size ? { w: members[0].size.w, d: members[0].size.h } : { w: 0.1, d: 0.1 });
    members.forEach((f, i) => {
      const parent = f.object.parent!, from = f.object.position.clone(), fromRy = f.object.rotation.y;
      const to = open ? parent.worldToLocal(new THREE.Vector3(slots[i].x, slots[i].y, slots[i].z)) : f.home.position.clone();
      const toRy = open ? slots[i].rotY : f.home.rotation.y;
      animator.play("fan:" + f.item.id, ms(FAN_MS + i * 25), p => { f.object.position.lerpVectors(from, to, p); f.object.rotation.y = fromRy + (toRy - fromRy) * p; }, now());
    });
  }

  function apply(prev: Stack, next: Stack) {
    const pt = top(prev), nt = top(next);
    const prevFocus = pt.kind === "focus" ? reg.get(pt.id) : undefined, nextFocus = nt.kind === "focus" ? reg.get(nt.id) : undefined;
    const prevFan = prev.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    const nextFan = next.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    if (prevFocus && prevFocus !== nextFocus && prevFocus.paper) restCard(prevFocus);
    if (prevFocus && prevFocus !== nextFocus && !prevFocus.paper) liftTo(prevFocus, false);
    if (prevFan && prevFan.pile !== nextFan?.pile) fan(prevFan.pile, false);
    if (nextFan && nextFan.pile !== prevFan?.pile) fan(nextFan.pile, true);
    if (nextFocus) {
      if (nextFocus !== prevFocus) { if (nextFocus.paper) { liftTo(nextFocus, true); setHiRes(nextFocus, 0); } }
      else if (nt.kind === "focus" && nextFocus.paper) flipTo(nextFocus, nt.side);
    } else setHiRes(null, 0);
    if (nt.kind !== pt.kind || (nt.kind === "focus" && pt.kind === "focus" && nt.id !== pt.id) || (nt.kind === "fan")) moveCamera(shotFor(nt));
    ctx.kick();
  }

  return {
    dispatch(a: Action) { const next = reduce(stack, a, reg.items()); if (next !== stack) { const prev = stack; stack = next; apply(prev, next); } },
    stack: () => stack,
    /** Advance animations and place the camera (plus overview parallax). Returns true while anything is moving. */
    tick(t: number): boolean {
      const moving = animator.step(t);
      const par = top(stack).kind === "overview" ? ctx.parallax() : new THREE.Vector3();
      camera.position.copy(camPos).add(par); camera.lookAt(camTarget);
      return moving;
    },
    onResize() { moveCamera(shotFor(top(stack))); ctx.kick(); },          // refit the current shot to the new aspect
  };
}
```

- [ ] **Step 3: Picking, hover lift and label tag**

`desk/src/interaction/picking.ts`:
```ts
import * as THREE from "three";
import type { Animator } from "../anim/animator";
import { top, type Action, type Stack } from "../camera/director";
import type { Focusable, Registry } from "../scene/focusables";
import { isClick } from "./input";

const HOVER_LIFT = 0.003, HOVER_MS = 140;

interface Ctx { canvas: HTMLCanvasElement; camera: THREE.PerspectiveCamera; scene: THREE.Scene; reg: Registry; animator: Animator;
  dispatch: (a: Action) => void; stack: () => Stack; kick: () => void; motion: number; label: HTMLElement }

const NAMES: Record<string, string> = { cards: "In progress", stickies: "To do", calendar: "Calendar", notepad: "This week", cardPile: "More in progress", stickyPile: "More to do" };

export function createPicking(ctx: Ctx) {
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  let hovered: Focusable | undefined, down: { x: number; y: number; t: number } | null = null;
  const parallaxGoal = new THREE.Vector3(), parallax = new THREE.Vector3();

  const pick = (e: PointerEvent): Focusable | undefined => {
    const r = ctx.canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, ctx.camera);
    for (const hit of ray.intersectObjects(ctx.scene.children, true)) {
      const f = ctx.reg.ofObject(hit.object);
      if (!f) continue;
      const t = top(ctx.stack());
      if (f.item.pile && !(t.kind === "fan" || t.kind === "focus")) return ctx.reg.get(f.item.pile);   // closed pile: pick the pile
      return f;
    }
    return undefined;
  };

  const hoverLift = (f: Focusable, on: boolean) => {
    const t = top(ctx.stack());
    if (t.kind === "focus" && t.id === f.item.id) return;                        // the focused card is already lifted
    const target = f.object.parent ? f.object : f.object, from = target.position.y, to = f.home.position.y + (on ? HOVER_LIFT : 0);
    ctx.animator.play("hover:" + f.item.id, HOVER_MS * ctx.motion, p => { target.position.y = from + (to - from) * p; }, performance.now());
  };

  function setHover(f: Focusable | undefined, e?: PointerEvent) {
    if (f === hovered) { if (f && e) placeLabel(e); return; }
    if (hovered && hovered.item.group !== "cardPile" && hovered.item.group !== "stickyPile") hoverLift(hovered, false);
    hovered = f;
    if (f && f.item.group !== "cardPile" && f.item.group !== "stickyPile") hoverLift(f, true);
    ctx.canvas.style.cursor = f ? "pointer" : "default";
    if (f && e) { const vm = f.paper?.vm; ctx.label.textContent = vm ? `${NAMES[f.item.group]} · ${vm.title}` : NAMES[f.item.group] ?? f.item.id;
      ctx.label.style.opacity = "1"; placeLabel(e); } else ctx.label.style.opacity = "0";
    ctx.kick();
  }
  const placeLabel = (e: PointerEvent) => { ctx.label.style.transform = `translate(${e.clientX + 14}px, ${e.clientY + 14}px)`; };

  return {
    onPointerMove(e: PointerEvent) {
      const r = ctx.canvas.getBoundingClientRect();
      parallaxGoal.set(((e.clientX - r.left) / r.width - 0.5) * 0.03, -((e.clientY - r.top) / r.height - 0.5) * 0.015, 0);   // ±1.5 cm drift
      setHover(pick(e), e); ctx.kick();
    },
    onPointerDown(e: PointerEvent) { down = { x: e.clientX, y: e.clientY, t: performance.now() }; },
    onPointerUp(e: PointerEvent) {
      if (!down) return; const was = down; down = null;
      if (!isClick(was, { x: e.clientX, y: e.clientY, t: performance.now() })) return;     // a drag, not a click
      if (e.button === 2) { ctx.dispatch({ type: "back" }); return; }
      const f = pick(e), t = top(ctx.stack());
      if (!f) { ctx.dispatch({ type: "back" }); return; }                                   // empty desk = back
      if (t.kind === "focus" && t.id === f.item.id) ctx.dispatch({ type: "flip" });       // click the focused card = flip
      else ctx.dispatch({ type: "select", id: f.item.id });
    },
    onPointerLeave() { setHover(undefined); parallaxGoal.set(0, 0, 0); ctx.kick(); },
    /** Ease the overview parallax toward the pointer; true while still easing. */
    parallax(): THREE.Vector3 { parallax.lerp(parallaxGoal, 0.12 * (ctx.motion || 1)); return parallax; },
    parallaxBusy: () => parallax.distanceTo(parallaxGoal) > 1e-5,
  };
}
```

- [ ] **Step 4: Label element**

In `desk/index.html`, add inside `<style>`:
```css
  #tag { position: fixed; left: 0; top: 0; pointer-events: none; opacity: 0; transition: opacity .15s; max-width: 320px;
    background: #f3ecdd; color: #2d2b29; font: 15px 'Caveat', cursive; padding: 4px 10px 5px; border-radius: 2px;
    box-shadow: 0 2px 6px rgba(0,0,0,.25); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #desk { transition: opacity .15s; }
```
and before the scripts:
```html
<div id="tag"></div>
```

- [ ] **Step 5: Wire it up in `main.ts`**

Replace the `buildObjects(scene, model, m, MAT.t);` line and the `requestRender();` line after it with:
```ts
  const reg = buildObjects(scene, model, m, MAT.t);
  const animator = new Animator();
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const motion = () => motionFactor(reduceMotion.matches);
  const fade = () => { canvas.style.opacity = "0.25"; requestAnimationFrame(() => requestAnimationFrame(() => { canvas.style.opacity = "1"; })); };
  let picking: ReturnType<typeof createPicking>;
  const loop = createLoop(() => { focus.tick(performance.now()); composer.render(); }, () => animator.busy || picking.parallaxBusy());
  const focus = createFocus({ camera: createRendererResult.camera, reg, animator, kick: () => loop.kick(), get motion() { return motion(); }, fade,
    parallax: () => picking.parallax() } as Parameters<typeof createFocus>[0]);
  picking = createPicking({ canvas, camera: createRendererResult.camera, scene, reg, animator, dispatch: a => focus.dispatch(a), stack: focus.stack,
    kick: () => loop.kick(), get motion() { return motion(); }, label: document.getElementById("tag")! } as Parameters<typeof createPicking>[0]);
  canvas.addEventListener("pointermove", e => picking.onPointerMove(e));
  canvas.addEventListener("pointerdown", e => picking.onPointerDown(e));
  canvas.addEventListener("pointerup", e => picking.onPointerUp(e));
  canvas.addEventListener("pointerleave", () => picking.onPointerLeave());
  canvas.addEventListener("contextmenu", e => e.preventDefault());               // right-click = back (handled on pointerup)
  addEventListener("keydown", e => { if (e.metaKey || e.ctrlKey || e.altKey) return; const a = keyToAction(e.key);
    if (a) { e.preventDefault(); focus.dispatch(a); } });
  new ResizeObserver(() => focus.onResize()).observe(canvas);
  loop.kick();
```
Add the imports:
```ts
import { Animator } from "./anim/animator";
import { createFocus } from "./interaction/focus";
import { createPicking } from "./interaction/picking";
import { keyToAction, motionFactor } from "./interaction/input";
import { createLoop } from "./scene/loop";
```
Finally, extend the test handle to `(window as any).__desk = { scene, renderer, camera: createRendererResult.camera, requestRender, renders: () => renderCount, focus };`.

- [ ] **Step 6: Type-check, build, and check in the browser**

Run: `cd desk && npx tsc --noEmit && npx vitest run && npm run build && cd .. && python3 build.py`
Expected: tsc clean, `61 passed`, `desk.html` built.

Then, in the browser (Playwright over `python3 -m http.server`, and the user's Safari from `file://`), check:
1. **Idle:** 0 renders over 2 s. Moving the pointer lifts objects by about 3 mm and shows the tag with a hand cursor, then renders stop within about 0.5 s of the pointer stopping.
2. **Card:** `__desk.focus.dispatch({type:"select", id: <first card id>})` brings the card to about 70% of the view (the card width is 0.6–0.8 of the frame width in a screenshot), and its text is sharp.
3. **Flipping:** `Space` flips the card. A 2+ sided card shows side 2 right-way-up with its footer; a 1-sided card shows a blank back. Pressing `Space` until it returns to side 1 works.
4. **Navigation:** `←` / `→` move between cards, `Esc` goes back to the overview, `5` opens the calendar close-up and `6` the notepad.
5. **Rapid input:** select card A, then immediately card B, then `Esc` several times quickly. The camera never ends up anywhere but the overview, and no card is left lifted or turned over (check `rotation.x` is 0 and `position.y` equals home for every card).
6. **Resize:** focus a card, resize the window to 900×900, and the card still fills about 70%.
7. **Reduced motion:** with `prefers-reduced-motion: reduce` emulated (`page.emulateMedia({ reducedMotion: "reduce" })`), moves are instant with a brief fade.
8. **Piles:** with more than 6 in-progress items (simulate by adding test to-dos in a copy of the data), the pile fans open on click, a fanned card focuses, and `Esc` goes card → fan → overview.
9. **Flicker:** the flicker sweep from Plan 1 still passes, with paper areas under 2% on a 4 mm nudge.

Record each result in the ledger.

- [ ] **Step 7: Commit** (message shown to the user for approval first)

---

### Task 10: Docs

**Files:**
- Modify: `README.md` (the 3D desk section)

- [ ] **Step 1:** In the README's "3D desk" section, after the opening paragraph, add:
```markdown
**Using it:** hover to see what things are; click a card, sticky note, the calendar or the notepad to read it up close.
Click the card (or press `Space`) to turn it over; `←` `→` go to its neighbours; `Esc`, right-click or clicking the empty desk goes back.
Keys: `1` cards · `2` sticky notes · `5` calendar · `6` notepad · `0` overview. More than 6 cards (or 8 sticky notes) pile up; click the pile to fan it out.
Respects your system's "Reduce motion" setting.
```

- [ ] **Step 2:** Run the full suites: `.venv/bin/python -m pytest tests -q && (cd desk && npx vitest run)`. Expected: 39 and 61 passed.

- [ ] **Step 3: Commit** (message shown to the user for approval first)

---

# Revision 1 (2026-10-14): real pages, daily notepad

**Why:** after seeing Tasks 1–8, the user asked that *everything* follow real-life mechanics (spec §3a, added 2026-10-14):
- printed text never changes;
- more content means more physical paper, so a long task is a **clipped stack of single-sided cards** and a long to-do is a **pad of sticky notes**;
- turning a page moves a real sheet onto a read pile;
- the notepad becomes a **daily tally pad**: today on top, earlier days flipped over the top binding.

**What stands from the original tasks:**
- Tasks 1, 2 and 5 as built (animator, shots, two-plane paper card).
- Task 8's `Registry`, with a reshaped `Focusable`.
- Task 9's loop, picking, label tag and main wiring.
- Bug fixes found during Task 9's browser checks:
  - resize snaps the camera instead of animating it;
  - one `pose:<id>` animation channel per object;
  - rest resets state immediately.

**What this revision replaces:**
- Task 3's flip semantics become page turning.
- Task 4's `Space` mapping changes.
- Task 6's per-side footers become page numbers.
- Task 7 and Task 8's single-card objects become page stacks.
- Task 9's `focus.ts` is rewritten.

The executor continues from here (R1–R8). Ledger rulings from Tasks 1–9 carry over.

## Revision Review Focus (replaces the original list where they differ)

1. **Turning many pages quickly** (`Space` mashed on a 5-page stack, then `Esc` mid-turn) must end with every page back in the stack, face-up order restored, the clip in place, and no page left floating or face-down. Pinned in R1 (reducer) and R8 (browser).
2. **A one-page task** has nothing to turn, so `Space` does nothing: no motion, no blank flip. Pinned in R1.
3. **A stack near the desk's right edge** must get its read pile on the left, not off the desk. Pinned in R5.
4. **A day with no commits** shows a real page saying so ("a quiet day"), not a blank or broken page, and the 14 days are contiguous even with gaps in the data. Pinned in R4.
5. **Memory:** turning through a long stack must not keep a high-resolution texture per page. At most the top page is high resolution; pages that land face-down drop theirs. Pinned in R7 (code) and R8 (`renderer.info.memory.textures` stays bounded).

---

### R1: Director: pages and turning (replaces Task 3's flip)

**Files:** Modify `desk/src/camera/director.ts`, `desk/test/director.test.ts`

**Interfaces (replacing Task 3's):**
- `interface Item { id: string; group: Group; pages: number; turnable: boolean; pile?: PileId }`.
- `type Frame = { kind: "overview" } | { kind: "focus"; id: string; page: number } | { kind: "fan"; pile: PileId }`.
- `type Action = { type: "select"; id: string } | { type: "back" } | { type: "turn"; dir: 1 | -1 } | { type: "neighbor"; dir: 1 | -1 } | { type: "key"; key: "0" | "1" | "2" | "5" | "6" }`.
- **Turning forward:** `turn` with dir 1 goes to the next page; from the last page it goes back to page 0, which gathers the stack.
- **Turning back:** `turn` with dir −1 goes to the previous page and stays at 0.
- **Non-turnable items** (one page, calendar): `turn` does nothing.

- [ ] **Step 1: Rewrite the tests** in `desk/test/director.test.ts`. Keep the file's existing tests for select/back, switching, neighbours, piles, keys and the "mashing" invariant, with `sides`/`flippable` renamed to `pages`/`turnable`, `side` renamed to `page`, and `{ type: "flip" }` replaced by `{ type: "turn", dir: 1 }`. Replace the two flip tests with:
```ts
  test("turning forward walks the pages; past the last page the stack is gathered (back to page 1)", () => {
    const pages = [1, 2, 3, 4].map(n => top(run([{ type: "select", id: "card:b" }, ...Array(n).fill({ type: "turn", dir: 1 })])));
    expect(pages.map(f => (f as { page: number }).page)).toEqual([1, 2, 3, 0]);
  });
  test("turning back goes one page back and stops at the first page", () => {
    const s = run([{ type: "select", id: "card:b" }, { type: "turn", dir: 1 }, { type: "turn", dir: 1 }, { type: "turn", dir: -1 }]);
    expect((top(s) as { page: number }).page).toBe(1);
    expect(run([{ type: "turn", dir: -1 }, { type: "turn", dir: -1 }], s)).toEqual([...START, { kind: "focus", id: "card:b", page: 0 }]);
  });
  test("a one-page task and the calendar have nothing to turn (no state change at all)", () => {
    for (const id of ["card:a", "calendar"]) { const s = run([{ type: "select", id }]); expect(reduce(s, { type: "turn", dir: 1 }, items)).toBe(s); }
    expect(reduce(START, { type: "turn", dir: 1 }, items)).toBe(START);
  });
  test("the notepad turns through its 14 days", () => {
    const pad: Item[] = [{ id: "notepad", group: "notepad", pages: 14, turnable: true }];
    const s = run([{ type: "select", id: "notepad" }, ...Array(13).fill({ type: "turn", dir: 1 })], START, pad);
    expect((top(s) as { page: number }).page).toBe(13);
  });
```
The `items` fixture becomes:
```ts
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
```
In the neighbour test, the first line becomes `run([{ type: "select", id: "card:a" }, { type: "neighbor", dir: 1 }])` and the expected value is `{ kind: "focus", id: "card:b", page: 0 }`. A one-page card can't turn, so the old "flip then neighbour" step is gone. In the mashing test's action list, replace `{ type: "flip" }` with `{ type: "turn", dir: 1 }`.

- [ ] **Step 2: Run them to confirm they fail.** Run `cd desk && npx vitest run test/director.test.ts`. Expected: FAIL (type errors and wrong shapes: `page` is undefined).

- [ ] **Step 3: Implement.** In `desk/src/camera/director.ts`:
  - rename `sides` → `pages`, `flippable` → `turnable`, `side` → `page`;
  - change the `Action` union (replace `{ type: "flip" }` with `{ type: "turn"; dir: 1 | -1 }`);
  - replace the `case "flip"` block with:
```ts
    case "turn": {
      if (t.kind !== "focus") return s;
      const it = byId.get(t.id);
      if (!it?.turnable) return s;
      const page = a.dir === 1 ? (t.page < it.pages - 1 ? t.page + 1 : 0) : Math.max(0, t.page - 1);
      return page === t.page ? s : [...s.slice(0, -1), { ...t, page }];      // past the last page: gather (page 0)
    }
```
  In the `select` and `neighbor` cases, build frames with `page: 0`.

- [ ] **Step 4:** Run `cd desk && npx vitest run test/director.test.ts && npx tsc --noEmit`. Expected: `11 passed`. tsc errors are expected only in `focus.ts`, `picking.ts`, `paperObjects.ts` and `stationery.ts`; they're fixed in R6–R7.

### R2: Input: `Space` turns, `Shift`+`Space` turns back (replaces Task 4's flip)

**Files:** Modify `desk/src/interaction/input.ts`, `desk/test/input.test.ts`

- [ ] **Step 1: Test.** In `desk/test/input.test.ts`, replace `expect(keyToAction(" ")).toEqual({ type: "flip" });` with:
```ts
  expect(keyToAction(" ")).toEqual({ type: "turn", dir: 1 });
  expect(keyToAction(" ", true)).toEqual({ type: "turn", dir: -1 });
```
- [ ] **Step 2:** Run `cd desk && npx vitest run test/input.test.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** Change the signature to `export function keyToAction(key: string, shift = false): Action | null` and use `case " ": return { type: "turn", dir: shift ? -1 : 1 };`.
- [ ] **Step 4:** Run `cd desk && npx vitest run test/input.test.ts`. Expected: `3 passed`.

### R3: Page numbers and page rendering (replaces Task 6's side footers)

**Files:** Modify `desk/src/paper/layout.ts`, `desk/src/paper/cardTexture.ts`, `desk/test/layout.test.ts`

**Interfaces:**
- `pageFooter(index: number, total: number): string | null`, which returns `null` when `total <= 1` and otherwise `"${index+1}/${total}"`.
- `cardPages(c: CardVM, kind: PaperKind): Side[]`, renamed from `cardSides`.
- `renderPage(c, kind, pages, index, pxPerMm)`, renamed from `renderSide`, which uses `pageFooter`. Each card is single-sided: an index beyond the content draws plain paper.
- `sideFooter` is removed.

- [ ] **Step 1: Test.** In `desk/test/layout.test.ts`, replace the `sideFooter` test (and its import) with:
```ts
import { pageFooter } from "../src/paper/layout";
test("every page of a multi-page task is numbered; a one-page task isn't", () => {
  expect(pageFooter(0, 1)).toBeNull();
  expect([0, 1, 2].map(i => pageFooter(i, 3))).toEqual(["1/3", "2/3", "3/3"]);
});
```
- [ ] **Step 2:** Run `cd desk && npx vitest run test/layout.test.ts`. Expected: FAIL (`pageFooter is not a function`).
- [ ] **Step 3: Implement.** In `layout.ts`, replace the `sideFooter` function with:
```ts
/** Page number for page `index` (0-based) of a `total`-page task; one-page tasks carry no number. */
export const pageFooter = (index: number, total: number): string | null => (total <= 1 ? null : `${index + 1}/${total}`);
```
In `cardTexture.ts`:
  - rename `cardSides` → `cardPages` and `renderSide` → `renderPage`;
  - import and call `pageFooter` instead of `sideFooter`;
  - rename the `sides` parameter to `pages`.

  `renderPage` keeps its signature `(c, kind, pages, index, pxPerMm)`.
- [ ] **Step 4:** Run `cd desk && npx vitest run test/layout.test.ts`. Expected: `9 passed`.

### R4: Daily tallies and the tally page (notepad = today, spec §3a)

**Files:**
- Modify `desk/src/data/model.ts`.
- Create `desk/src/paper/tallyPage.ts`.
- Tests: `desk/test/model.test.ts` (append), `desk/test/tally.test.ts`.

**Interfaces:**
- `interface DayTally { ymd: string; label: string; commits: number; tasks: number; todosDone: number; first: string | null; last: string | null }`.
- `dailyTallies(data: DeskData, now: Date, days = 14): DayTally[]`:
  - newest first and contiguous: today, then yesterday, and so on, even when a day has no data;
  - `label` is `"Today"`, `"Yesterday"` or a date like `"Mon 6 Oct"`;
  - `first` and `last` are `"HH:MM"` (IST) of that day's earliest and latest commit.
- `DeskModel` gains `days: DayTally[]`, filled by `buildModel`.
- `tallyLines(d: DayTally): string[]` (pure). It returns the handwritten lines for a page: the label, the counts, and the first/last line or `"a quiet day"`.
- `renderTallyPage(d: DayTally, pxPerMm: number): HTMLCanvasElement` draws a 100×140 mm ruled page with the `tallyLines`.

- [ ] **Step 1: Tests.** Append to `desk/test/model.test.ts`:
```ts
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
```
Create `desk/test/tally.test.ts`:
```ts
import { expect, test } from "vitest";
import { tallyLines } from "../src/paper/tallyPage";

test("a working day lists counts and the first/last commit times", () => {
  expect(tallyLines({ ymd: "2026-10-13", label: "Today", commits: 12, tasks: 4, todosDone: 2, first: "09:12", last: "18:40" }))
    .toEqual(["Today", "commits  12", "tasks  4", "to-dos done  2", "09:12 → 18:40"]);
});
test("a day with nothing says so instead of showing an empty page", () => {
  expect(tallyLines({ ymd: "2026-10-11", label: "Sat 11 Oct", commits: 0, tasks: 0, todosDone: 0, first: null, last: null }))
    .toEqual(["Sat 11 Oct", "a quiet day"]);
});
```
- [ ] **Step 2:** Run `cd desk && npx vitest run test/model.test.ts test/tally.test.ts`. Expected: FAIL (missing exports).
- [ ] **Step 3: Implement.** In `model.ts`, add:
```ts
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
```
Add `days: DayTally[]` to `DeskModel` and `days: dailyTallies(data, now),` to the object `buildModel` returns.

  Create `desk/src/paper/tallyPage.ts`:
```ts
import type { DayTally } from "../data/model";
import { drawPaper, FONTS } from "./render";

const W = 100, H = 140, INK = "#2d2b29";
export function tallyLines(d: DayTally): string[] {
  if (!d.commits && !d.tasks && !d.todosDone) return [d.label, "a quiet day"];
  return [d.label, `commits  ${d.commits}`, `tasks  ${d.tasks}`, `to-dos done  ${d.todosDone}`, ...(d.first ? [`${d.first} → ${d.last}`] : [])];
}
/** A ruled pad page, handwritten in near-black ink; the date sits small in the corner. */
export function renderTallyPage(d: DayTally, px: number): HTMLCanvasElement {
  const c = document.createElement("canvas"); c.width = W * px; c.height = H * px; const g = c.getContext("2d")!;
  drawPaper(g, c.width, c.height, "#f6efe0", "pad:" + d.ymd);
  g.strokeStyle = "rgba(110,140,190,.45)"; g.lineWidth = Math.max(1, px * 0.15);
  for (let y = 24; y < H - 8; y += 9) { g.beginPath(); g.moveTo(6 * px, y * px); g.lineTo((W - 6) * px, y * px); g.stroke(); }
  g.fillStyle = INK; g.font = `${7 * px}px ${FONTS.hand}`;
  tallyLines(d).forEach((line, i) => g.fillText(line, 8 * px, (i === 0 ? 18 : 22 + i * 9) * px));
  g.globalAlpha = 0.6; g.font = `${3 * px}px ${FONTS.typed}`; g.textAlign = "right"; g.fillText(d.ymd, (W - 6) * px, (H - 5) * px);
  return c;
}
```
- [ ] **Step 4:** Run `cd desk && npx vitest run test/model.test.ts test/tally.test.ts`. Expected: `12 passed` (10 model + 2 tally).

### R5: Page stacks, read piles and pad flips (pure placement)

**Files:** Modify `desk/src/objects/slots.ts`, `desk/test/objects.test.ts`

**Interfaces:**
- `pageStack(n: number): { y: number; dx: number; dz: number; rotY: number }[]`. Index 0 is the **top** page. `y` is each page's bottom relative to the stack's base, so the bottom page sits at y = 0 and the pages above are `PAPER_T + MIN_GAP` apart. `dx` and `dz` jitter by up to ±1.2 mm and `rotY` by up to ±0.012 rad, seeded so the result is deterministic.
- `readPileX(stackWorldX: number, w: number): number` gives the local x offset of the read pile: `+(w + 0.025)`, or `−(w + 0.025)` if the right-hand pile would pass x = 0.78.
- `readPileY(k: number): number` is the bottom of the k-th read page, `stackY(0, k, PAPER_T)`.
- `padFlipAngle(k: number, hingeY: number, d: number): number` is the x rotation of the k-th flipped pad page about the top binding. Its far edge rests at height `MIN_GAP + k·(PAPER_T + MIN_GAP)`: the first on the desk, each later one on the one before.

- [ ] **Step 1: Tests** (append to `desk/test/objects.test.ts`):
```ts
import { padFlipAngle, pageStack, readPileX, readPileY } from "../src/objects/slots";

test("page stacks: top page is index 0, every page clears the one below, bottom page at the base", () => {
  const s = pageStack(5);
  expect(s[4].y).toBe(0);
  for (let i = 0; i < 4; i++) expect(s[i].y - s[i + 1].y).toBeCloseTo(PAPER_T + MIN_GAP, 12);
  for (const p of s) { expect(Math.abs(p.dx)).toBeLessThanOrEqual(0.0012); expect(Math.abs(p.rotY)).toBeLessThanOrEqual(0.012); }
  expect(pageStack(5)).toEqual(s);                                                      // deterministic
});
test("read pile goes beside the stack, on the left when the right side would leave the desk", () => {
  expect(readPileX(0, CARD_SIZE.w)).toBeCloseTo(CARD_SIZE.w + 0.025, 12);
  expect(readPileX(0.6, CARD_SIZE.w)).toBeCloseTo(-(CARD_SIZE.w + 0.025), 12);
  expect(readPileY(2) - readPileY(1)).toBeCloseTo(PAPER_T + MIN_GAP, 12);
});
test("flipped pad pages slope over the binding with their far edge resting on the desk / previous page", () => {
  const h = 0.008, d = NOTEPAD.d;
  for (let k = 0; k < 14; k++) {
    const a = padFlipAngle(k, h, d), farY = h - d * Math.sin(a);                          // rotation about x: local (0,0,d) -> y = -d·sin(a)
    expect(a).toBeLessThan(-Math.PI); expect(a).toBeGreaterThan(-1.5 * Math.PI);
    expect(farY).toBeCloseTo(MIN_GAP + k * (PAPER_T + MIN_GAP), 9);
  }
});
```
- [ ] **Step 2:** Run `cd desk && npx vitest run test/objects.test.ts`. Expected: FAIL (`pageStack is not a function`).
- [ ] **Step 3: Implement** (append to `slots.ts`):
```ts

/** A clipped stack of single-sided pages; index 0 is the top page. y = page bottom above the stack base. */
export function pageStack(n: number) {
  const r = seededRandom("pages:" + n);
  return [...Array(n)].map((_, i) => ({ y: stackY(0, n - 1 - i, PAPER_T), dx: (r() - 0.5) * 0.0024, dz: (r() - 0.5) * 0.0024, rotY: (r() - 0.5) * 0.024 }));
}
/** Read pages go face-down beside the stack; on the left if the right side would run off the desk. */
export const readPileX = (stackWorldX: number, w: number) => (stackWorldX + w * 1.5 + 0.025 > 0.78 ? -(w + 0.025) : w + 0.025);
export const readPileY = (k: number) => stackY(0, k, PAPER_T);
/** x-rotation of the k-th page flipped over a top binding at hingeY: its far edge rests on the desk or the previous flipped page. */
export function padFlipAngle(k: number, hingeY: number, d: number) {
  const rest = MIN_GAP + k * (PAPER_T + MIN_GAP);
  return -(Math.PI + Math.asin(Math.min(1, Math.max(0, (hingeY - rest) / d))));
}
```
Add `NOTEPAD` to the test file's import from `../src/scene/layout`.
- [ ] **Step 4:** Run `cd desk && npx vitest run test/objects.test.ts`. Expected: `15 passed`.

### R6: Build stacks, sticky pads and the daily pad as focusables

**Files:**
- Modify `desk/src/scene/focusables.ts`, `desk/test/focusables.test.ts`.
- Modify `desk/src/objects/paperObjects.ts` (replace `paperItem`, `addCards` and `addStickies`).
- Modify `desk/src/objects/stationery.ts` (replace `addNotepad`).

**Interfaces:**
```ts
export interface Pages {
  count: number; style: "stack" | "pad";
  meshes: THREE.Object3D[];                                    // index 0 = top page; each contains a "front" plane
  homes: { position: THREE.Vector3; rotation: THREE.Euler }[];
  size: { w: number; d: number }; hingeY: number;              // hingeY: pads only
  low: THREE.Texture;                                          // top page at overview resolution
  base: number;                                                // the paper colour (cream card, yellow sticky, pad cream)
  render(i: number, pxPerMm: number): HTMLCanvasElement;
}
export interface Focusable { item: Item; object: THREE.Object3D; size: { w: number; h: number }; normal: V3; label: string;
  pages?: Pages; home: { position: THREE.Vector3; rotation: THREE.Euler } }
```

- [ ] **Step 1: Test.** In `desk/test/focusables.test.ts`:
  - add `label: "x"` to both `r.add({...})` objects;
  - change `sides`/`flippable` to `pages`/`turnable`.

  Then run `cd desk && npx vitest run test/focusables.test.ts`. Expected: FAIL in tsc only (vitest strips types, so it passes). Treat `npx tsc --noEmit` as this test's RED, then GREEN after Step 2.
- [ ] **Step 2: Implement the registry types.** In `focusables.ts`:
  - replace the `paper?` field and its `CardVM`/`PaperKind`/`Side` imports with the `Pages` interface above;
  - add `label: string` to `Focusable`.
- [ ] **Step 3: Page stacks for cards and sticky pads.** In `paperObjects.ts`, replace `paperItem`, `addCards` and `addStickies` with:
```ts
const LOW_PX = 6;
const BASE = { card: 0xf1ebde, sticky: 0xf4d675 } as const;
const canvasTexture = (c: HTMLCanvasElement) => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

/** A small steel paper clip over the stack's top-left corner (spec §3a: clipped stack). */
function paperClip(size: { w: number; d: number }, y: number) {
  const x0 = -size.w / 2 + 0.014, z0 = -size.d / 2 - 0.004, l = 0.03, a = 0.005, b = 0.0032;
  const pts = [[x0 - a, z0 + l], [x0 - a, z0], [x0 + a, z0], [x0 + a, z0 + l * 0.85], [x0 - b, z0 + l * 0.85], [x0 - b, z0 + 0.004], [x0 + b, z0 + 0.004], [x0 + b, z0 + l * 0.6]]
    .map(([x, z]) => new THREE.Vector3(x, y, z));
  const clip = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.1), 64, 0.0006, 8),
    new THREE.MeshPhysicalMaterial({ color: 0xb8bcc2, metalness: 1, roughness: 0.25 }));
  clip.name = "clip"; clip.castShadow = true; return clip;
}

/** A task as a clipped stack of single-sided cards (or a pad of sticky notes): one physical page per page of text. */
function pageStackItem(m: M, vm: CardVM, kind: PaperKind, id: string, group: "cards" | "stickies", pile?: "cardPile" | "stickyPile") {
  const content = cardPages(vm, kind), n = Math.max(1, content.length);
  const size = { w: PAPER[kind].wMm / 1000, d: PAPER[kind].hMm / 1000 };
  const low = canvasTexture(renderPage(vm, kind, content, 0, LOW_PX));
  const obj = new THREE.Group(); obj.name = id;
  const slots = pageStack(n), meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  slots.forEach((s, i) => {
    const page = makePaperCard(size.w, size.d, m.paper(i === 0 ? low : undefined, BASE[kind]), m.paper(undefined, BASE[kind]), m.paper(undefined, BASE[kind]));
    page.name = "page" + i; page.position.set(s.dx, s.y + PAPER_T / 2, s.dz); page.rotation.y = s.rotY;
    obj.add(page); meshes.push(page); homes.push({ position: page.position.clone(), rotation: page.rotation.clone() });
  });
  if (kind === "card" && n > 1) obj.add(paperClip(size, slots[0].y + PAPER_T + MIN_GAP));
  const focusable = { item: { id, group, pages: n, turnable: n > 1, pile }, object: obj, size: { w: size.w, h: size.d }, normal: FLAT_NORMAL, label: vm.title,
    pages: { count: n, style: "stack" as const, meshes, homes, size, hingeY: 0, low, base: BASE[kind], render: (i: number, px: number) => renderPage(vm, kind, content, i, px) },
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } };
  return { obj, focusable };
}
const rest = (f: { object: THREE.Object3D; home: { position: THREE.Vector3; rotation: THREE.Euler } }) => {
  f.home.position.copy(f.object.position); f.home.rotation.copy(f.object.rotation); };

export function addCards(scene: THREE.Scene, model: DeskModel, m: M, matTop: number, reg: Registry) {
  cardSlots(model.cards.length).forEach((s, i) => {
    const { obj, focusable } = pageStackItem(m, model.cards[i], "card", "card:" + model.cards[i].id, "cards");
    obj.position.set(s.x, restOn(matTop), s.z); obj.rotation.y = s.rotY; scene.add(obj); rest(focusable); reg.add(focusable);
  });
  if (model.cardOverflow.length) {
    const pile = new THREE.Group(); pile.name = "cardPile"; scene.add(pile);
    reg.add({ item: { id: "cardPile", group: "cardPile", pages: 1, turnable: false }, object: pile, size: { w: 0.33, h: 0.42 }, normal: FLAT_NORMAL,
      label: `${model.cardOverflow.length} more`, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    let base = restOn(MAT.t);                                                // each overflow stack rests on the one below
    model.cardOverflow.forEach(vm => {
      const { obj, focusable } = pageStackItem(m, vm, "card", "card:" + vm.id, "cards", "cardPile");
      obj.position.set(CARD_PILE.x, base, CARD_PILE.z); obj.rotation.y = CARD_PILE.rotY; pile.add(obj); rest(focusable); reg.add(focusable);
      base += pageStack(focusable.item.pages)[0].y + PAPER_T + MIN_GAP;
    });
  }
  if (!model.cards.length && !model.stickies.length) {   // spec §8: an empty desk gets one note
    const note: CardVM = { id: "empty", title: "Nothing on the go", where: "", ink: { hex: "#2d2b29", name: "", variant: 0 }, notes: [], commits: [], started: null };
    const { texture } = textureFor(note, "sticky", 76, 76, "#f4d675");
    const s = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006); s.position.set(-0.05, s.position.y, 0.12); scene.add(s);
  }
}

export function addStickies(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const { singles, pile } = stickyLayout(model.stickies.length), slots = stickySlots(8);
  model.stickies.slice(0, singles).forEach((vm, i) => {
    const { obj, focusable } = pageStackItem(m, vm, "sticky", "sticky:" + vm.id, "stickies");
    obj.position.set(slots[i].x, restOn(0), slots[i].z); obj.rotation.y = slots[i].rotY; scene.add(obj); rest(focusable); reg.add(focusable);
  });
  if (pile) {
    const group = new THREE.Group(); group.name = "stickyPile"; scene.add(group);
    reg.add({ item: { id: "stickyPile", group: "stickyPile", pages: 1, turnable: false }, object: group, size: { w: 0.33, h: 0.42 }, normal: FLAT_NORMAL,
      label: `${pile} more`, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    let base = restOn(0);
    model.stickies.slice(singles).forEach((vm, i) => {
      const { obj, focusable } = pageStackItem(m, vm, "sticky", "sticky:" + vm.id, "stickies", "stickyPile");
      obj.position.set(slots[7].x, base, slots[7].z); obj.rotation.y = slots[7].rotY + i * 0.04; group.add(obj); rest(focusable); reg.add(focusable);
      base += pageStack(focusable.item.pages)[0].y + PAPER_T + MIN_GAP;
    });
  }
}
```
Imports in `paperObjects.ts`:
  - `cardPages`, `PAPER`, `renderPage` and `PaperKind` from `../paper/cardTexture`;
  - `pageStack`, `stickyLayout` and `cardSlots`/`stickySlots` (already there) from `./slots`;
  - `MIN_GAP` added to the `../scene/layout` import;
  - drop `pileSlots` (no longer used; the overflow stacks rest on each other).
- [ ] **Step 4: The daily pad.** In `stationery.ts`, replace `addNotepad` with:
```ts
export function addNotepad(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const pad = new THREE.Group(); pad.name = "notepad";
  const size = { w: NOTEPAD.w, d: NOTEPAD.d }, blankSheets = 10, n = model.days.length;
  const block = stackBlock(m, size.w, size.d, stackBlockHeight(blankSheets), blankSheets);            // unused pages under the day pages
  block.position.y = restOn(0) + stackBlockHeight(blankSheets) / 2; pad.add(block);
  const base = restOn(0) + stackBlockHeight(blankSheets) + MIN_GAP, slots = pageStack(n);
  const hingeY = base + slots[0].y + PAPER_T;
  const low = (() => { const t = new THREE.CanvasTexture(renderTallyPage(model.days[0], 6)); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; })();
  const meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  slots.forEach((s, i) => {                                       // each day page hinges on the top binding
    const pivot = new THREE.Group(); pivot.name = "page" + i; pivot.position.set(0, base + s.y + PAPER_T / 2, -size.d / 2);
    const sheet = makePaperCard(size.w, size.d, m.paper(i === 0 ? low : undefined, 0xf6efe0), m.paper(undefined, 0xf6efe0), m.paper(undefined, 0xf6efe0));
    sheet.position.z = size.d / 2; pivot.add(sheet); pad.add(pivot); meshes.push(pivot); homes.push({ position: pivot.position.clone(), rotation: pivot.rotation.clone() });
  });
  const binding = new THREE.Mesh(new THREE.BoxGeometry(size.w + 0.002, 0.004, 0.012), new THREE.MeshPhysicalMaterial({ color: 0x3a2a20, roughness: 0.6 }));
  binding.position.set(0, hingeY + MIN_GAP + 0.002, -size.d / 2 + 0.006); binding.castShadow = true; pad.add(binding);
  pad.position.set(NOTEPAD.x, 0, NOTEPAD.z); pad.rotation.y = -0.35; scene.add(pad);
  reg.add({ item: { id: "notepad", group: "notepad", pages: n, turnable: n > 1 }, object: pad, size: { w: size.w, h: size.d }, normal: FLAT_NORMAL,
    label: "Today's tally", pages: { count: n, style: "pad", meshes, homes, size, hingeY, low, base: 0xf6efe0, render: (i, px) => renderTallyPage(model.days[i], px) },
    home: { position: pad.position.clone(), rotation: pad.rotation.clone() } });
}
```
Imports in `stationery.ts`: `renderTallyPage` from `../paper/tallyPage`; `makePaperCard` from `./paperCard`; `pageStack` from `./slots`; `restOn` and `MIN_GAP` from `../scene/layout`. Remove the now-unused `notepadSheets` import and its old canvas code. The calendar's `reg.add` gains `label: "Calendar"` and `pages: 1, turnable: false`.
- [ ] **Step 5:** Run `cd desk && npx tsc --noEmit`. Expected: errors only in `focus.ts`/`picking.ts`/`main.ts` (R7). Then run `npx vitest run`. Expected: all pass.

### R7: Focus controller with real page turning (replaces Task 9's `focus.ts`); picking and wiring updates

**Files:** Replace `desk/src/interaction/focus.ts`; modify `desk/src/interaction/picking.ts`, `desk/src/main.ts`

- [ ] **Step 1: Replace `desk/src/interaction/focus.ts`:**
```ts
import * as THREE from "three";
import { Animator } from "../anim/animator";
import { reduce, START, top, type Action, type Frame, type Stack } from "../camera/director";
import { FLAT_NORMAL, focusShot, type Shot, type V3 } from "../camera/shots";
import { fanSlots, padFlipAngle, readPileX, readPileY } from "../objects/slots";
import { CAMERA, OVERVIEW } from "../scene/depth";
import type { Focusable, Registry } from "../scene/focusables";

// Animation channels: "camera"; "pose:<id>" lifts/lowers a whole object (one channel, so a stale move never finishes
// after a newer one); "page:<id>:<i>" moves one physical page. Hover has its own short channel in picking.ts.
const HI_PX = 24, LOW_PX = 6, LIFT = 0.015, CAM_MS = 750, LIFT_MS = 400, TURN_MS = 560, STAGGER = 110, FAN_MS = 600;
type Quality = "hi" | "low" | "none";

interface Ctx { camera: THREE.PerspectiveCamera; reg: Registry; animator: Animator; kick: () => void; motion: number;
  fade: () => void; parallax: () => THREE.Vector3 }

export function createFocus(ctx: Ctx) {
  const { camera, reg, animator } = ctx;
  let stack: Stack = START;
  const camPos = new THREE.Vector3(...OVERVIEW.position), camTarget = new THREE.Vector3(...OVERVIEW.target);
  const shown = new Map<string, number>();                         // page currently on top of each object
  const textures = new Map<THREE.Object3D, THREE.Texture>();       // page -> texture we created for it (disposed on change)
  const now = () => performance.now();
  const ms = (d: number) => d * ctx.motion;

  /** Put page i's printed face on at the given quality. Text never changes: it is the same page, re-rendered sharper or blurrier. */
  function setFront(f: Focusable, i: number, q: Quality) {
    const pages = f.pages!, page = pages.meshes[i], mesh = page.getObjectByName("front") as THREE.Mesh;
    const old = textures.get(page); if (old) { old.dispose(); textures.delete(page); }
    const mat = (mesh.material as THREE.MeshPhysicalMaterial).clone(); (mesh.material as THREE.Material).dispose();
    if (q === "none") mat.map = null;
    else if (q === "low" && i === 0) mat.map = pages.low;
    else { const t = new THREE.CanvasTexture(pages.render(i, q === "hi" ? HI_PX : LOW_PX)); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = q === "hi" ? 16 : 8;
      textures.set(page, t); mat.map = t; }
    mat.color.set(mat.map ? 0xffffff : pages.base);             // a blank front keeps the paper's own colour
    mat.needsUpdate = true; mesh.material = mat;
  }

  function shotFor(frame: Frame): Shot {
    if (frame.kind === "overview") return { position: [...OVERVIEW.position], target: [...OVERVIEW.target] };
    if (frame.kind === "fan") { const f = reg.get(frame.pile)!; const c = f.home.position;
      return focusShot([c.x, c.y + 0.02, c.z], FLAT_NORMAL, f.size, CAMERA.fov, camera.aspect, 0.9); }
    const f = reg.get(frame.id)!; const c = f.object.getWorldPosition(new THREE.Vector3());
    const centre: V3 = [c.x, c.y + (f.pages?.style === "stack" ? LIFT : 0), c.z];
    return focusShot(centre, f.normal, f.size, CAMERA.fov, camera.aspect);
  }

  function moveCamera(shot: Shot) {
    const fromP = camPos.clone(), fromT = camTarget.clone(), toP = new THREE.Vector3(...shot.position), toT = new THREE.Vector3(...shot.target);
    const arc = fromP.distanceTo(toP) * 0.12;
    if (ctx.motion === 0) ctx.fade();
    animator.play("camera", ms(CAM_MS), p => { camPos.lerpVectors(fromP, toP, p); camPos.y += Math.sin(p * Math.PI) * arc; camTarget.lerpVectors(fromT, toT, p); }, now());
  }

  /** Lift a stack off the mat while it is being read (pads stay put: you read a pad where it lies). */
  function setLift(f: Focusable, up: boolean) {
    if (f.pages?.style !== "stack") return;
    const from = f.object.position.y, to = f.home.position.y + (up ? LIFT : 0);
    animator.play("pose:" + f.item.id, ms(LIFT_MS), p => { f.object.position.y = from + (to - from) * p; }, now());
  }

  /** Page i leaves the top: onto the read pile face-down (stack) or over the binding (pad). */
  function turnAway(f: Focusable, i: number, delay: number) {
    const pages = f.pages!, page = pages.meshes[i], fromP = page.position.clone(), fromR = page.rotation.clone();
    const done = () => setFront(f, i, "none");                    // face-down now: drop its texture (memory stays bounded)
    if (pages.style === "stack") {
      const side = readPileX(f.object.getWorldPosition(new THREE.Vector3()).x, pages.size.w);
      const toP = new THREE.Vector3(side, readPileY(i) + 0.0003, pages.homes[i].position.z), toRz = side > 0 ? -Math.PI : Math.PI;
      animator.play(`page:${f.item.id}:${i}`, ms(TURN_MS), p => {
        page.position.lerpVectors(fromP, toP, p); page.position.y += Math.sin(p * Math.PI) * 0.04; page.rotation.z = fromR.z + (toRz - fromR.z) * p;
      }, now() + ms(delay), { done });
    } else {
      const toA = padFlipAngle(i, pages.hingeY, pages.size.d);
      animator.play(`page:${f.item.id}:${i}`, ms(TURN_MS), p => { page.rotation.x = fromR.x + (toA - fromR.x) * p; }, now() + ms(delay), { done });
    }
  }

  /** Page i comes back on top, re-rendered at quality q. */
  function turnBack(f: Focusable, i: number, delay: number, q: Quality) {
    const pages = f.pages!, page = pages.meshes[i], fromP = page.position.clone(), fromR = page.rotation.clone(), home = pages.homes[i];
    setFront(f, i, q);
    animator.play(`page:${f.item.id}:${i}`, ms(TURN_MS), p => {
      page.position.lerpVectors(fromP, home.position, p); if (pages.style === "stack") page.position.y += Math.sin(p * Math.PI) * 0.04;
      page.rotation.set(fromR.x + (home.rotation.x - fromR.x) * p, fromR.y + (home.rotation.y - fromR.y) * p, fromR.z + (home.rotation.z - fromR.z) * p);
    }, now() + ms(delay));
  }

  /** Move from the page currently on top to `target`, one physical page at a time. */
  function goToPage(f: Focusable, target: number, q: Quality) {
    const s = shown.get(f.item.id) ?? 0;
    if (target > s) { for (let i = s; i < target; i++) turnAway(f, i, (i - s) * STAGGER); setFront(f, target, q); }
    else if (target < s) { for (let i = s - 1; i >= target; i--) turnBack(f, i, (s - 1 - i) * STAGGER, i === target ? q : "low"); }
    else setFront(f, target, q);
    shown.set(f.item.id, target);
  }

  function fan(pile: "cardPile" | "stickyPile", open: boolean) {
    const members = reg.all().filter(f => f.item.pile === pile);
    const slots = fanSlots(members.length, members[0] ? { w: members[0].size.w, d: members[0].size.h } : { w: 0.1, d: 0.1 });
    members.forEach((f, i) => {
      const parent = f.object.parent!, from = f.object.position.clone(), fromRy = f.object.rotation.y;
      const to = open ? parent.worldToLocal(new THREE.Vector3(slots[i].x, slots[i].y, slots[i].z)) : f.home.position.clone();
      const toRy = open ? slots[i].rotY : f.home.rotation.y;
      animator.play("pose:" + f.item.id, ms(FAN_MS + i * 25), p => { f.object.position.lerpVectors(from, to, p); f.object.rotation.y = fromRy + (toRy - fromRy) * p; }, now());
    });
  }

  function apply(prev: Stack, next: Stack) {
    const pt = top(prev), nt = top(next);
    const prevF = pt.kind === "focus" ? reg.get(pt.id) : undefined, nextF = nt.kind === "focus" ? reg.get(nt.id) : undefined;
    const prevFan = prev.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    const nextFan = next.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    if (prevF && prevF !== nextF && prevF.pages) { goToPage(prevF, 0, "low"); setLift(prevF, false); }   // gather and put it down
    if (prevFan && prevFan.pile !== nextFan?.pile) fan(prevFan.pile, false);
    if (nextFan && nextFan.pile !== prevFan?.pile) fan(nextFan.pile, true);
    if (nextF?.pages && nt.kind === "focus") {
      if (nextF !== prevF) { setLift(nextF, true); goToPage(nextF, 0, "hi"); }
      else goToPage(nextF, nt.page, "hi");
    }
    if (nt.kind !== pt.kind || (nt.kind === "focus" && pt.kind === "focus" && nt.id !== pt.id) || nt.kind === "fan") moveCamera(shotFor(nt));
    ctx.kick();
  }

  return {
    dispatch(a: Action) { const next = reduce(stack, a, reg.items()); if (next !== stack) { const prev = stack; stack = next; apply(prev, next); } },
    stack: () => stack,
    tick(t: number): boolean {
      const moving = animator.step(t);
      const par = top(stack).kind === "overview" ? ctx.parallax() : new THREE.Vector3();
      camera.position.copy(camPos).add(par); camera.lookAt(camTarget);
      return moving;
    },
    onResize() {                                   // refit the current shot to the new aspect: snap, don't animate
      const shot = shotFor(top(stack)); animator.cancel("camera");
      camPos.set(...shot.position); camTarget.set(...shot.target); ctx.kick();
    },
  };
}
```
`setFront` keeps blank fronts in the paper's own colour via `pages.base` (R6).

- [ ] **Step 2: Picking.** In `desk/src/interaction/picking.ts`:
  - the label text becomes `` `${NAMES[f.item.group]} · ${f.label}` `` for cards and stickies, and `f.label` otherwise;
  - clicking the focused object dispatches `{ type: "turn", dir: 1 }` instead of `{ type: "flip" }`;
  - add `notepad: "Today's tally"` to `NAMES`.
- [ ] **Step 3: Main.** In `desk/src/main.ts`, change `keyToAction(e.key)` to `keyToAction(e.key, e.shiftKey)`.
- [ ] **Step 4:** Run `cd desk && npx tsc --noEmit && npx vitest run && npm run build && cd .. && python3 build.py`. Expected: tsc clean, all tests pass, desk built.

### R8: Browser verification (replaces Task 9 Step 6) and docs (replaces Task 10's text)

- [ ] **Step 1: Browser checks** (Playwright over the local server, plus a final look in the user's Safari from `file://`). Record each result in the ledger.
  1. **Overview:** stacks are visibly thicker for multi-page tasks, and multi-page cards have a clip. The notepad shows today's page with a binding at the top. Idle renders are 0.
  2. **Focus and turning:** focusing a 2+ page task lifts the stack and the top card fills about 70% of the view.
     - `Space` moves the top card onto the read pile face-down, and the next card is readable with "2/n".
     - `Shift`+`Space` brings it back.
     - `Space` past the last page gathers the stack.
     - A one-page task doesn't move on `Space`.
  3. **Notepad:** `6` shows today's page. `Space` flips pages over the binding to earlier days (labels Yesterday, then dates), and a quiet day says "a quiet day".
  4. **Rapid input:** on a 3+ page stack, `Space` ×5 quickly, then `Esc` mid-turn. After 2 s:
     - every page of every stack is back at its home position and rotation (compare each page's `position`/`rotation` to `pages.homes`);
     - every stack is at its home height;
     - the camera is at the overview;
     - the animator is idle.
  5. **Memory:** `__desk.renderer.info.memory.textures` before focusing, after turning through every page of the longest stack, and after `Esc`. It must return to within 2 of the starting value.
  6. **Neighbours and keys:** `←` `→` between tasks, and `1` `2` `5` `6` `0`.
  7. **Resize while focused** snaps and still fits. **Reduced motion:** instant changes with a fade.
  8. **Flicker sweep** (Plan 1 method): paper areas under 2% on a 4 mm nudge.
- [ ] **Step 2: Docs.** In the README's "3D desk" section, after the opening paragraph, add:
```markdown
**Using it:** hover to see what things are; click a task, sticky note, the calendar or the notepad to bring it up close.
Longer tasks are clipped stacks of cards (one page each): `Space` or a click turns the top card onto the read pile, `Shift`+`Space` turns one back, and turning past the last page gathers the stack. `←` `→` go to the neighbouring task; `Esc`, right-click or clicking the empty desk puts things back.
The notepad is a daily tally pad: today on top; `Space` flips back through the last 14 days.
Keys: `1` tasks · `2` sticky notes · `5` calendar · `6` notepad · `0` overview. More than 6 tasks (or 8 sticky notes) pile up; click the pile to fan it out. Respects "Reduce motion".
```
- [ ] **Step 3:** Run `.venv/bin/python -m pytest tests -q && (cd desk && npx vitest run)`. Expected: 39 and all desk tests pass.


---

# Revision 2 (2026-10-14): handheld reading (user chose option A after the final review)

**Design:**
- **Task stacks** are picked up to a held pose 10 cm above the mat centre. The clip is left on the mat and re-clipped on return.
- **Thumbing:** a turn moves the top card out toward you (fully clear of the stack), down, and under. The others shift up one pitch while it's clear. Turning back is the reverse; one turn past the last card restores the order; leaving takes the shorter way round to page 1, then puts the stack down.
- **Sticky pads** are held the same way, and notes lift over the glued top edge.
- **The notepad and calendar** stay on the desk.
- **Hover and focus** share the `pose:<id>` channel. Every focusable has a rest pose (updated by fanning), and leaving always animates back to it.
- **Textures** go through a ledger, so each page has at most one texture and quality is decided by a pure rule: in focus, only the top page is hi-res and the rest have none; in the overview, page 0 is low and the rest have none.

**Review findings → fix → test:**

| Finding | Fix | Test |
|---|---|---|
| 1. Texture leak | `TextureLedger` + `pageQualities` | `textures.test.ts` |
| 2. Hover lift stuck | Hover on the pose channel; leave → rest pose | Browser |
| 3. Edge sinks through the stack | Thumb path stays fully clear of the stack footprint while above or below it | `thumbPath` test |
| 4. Read pile over the neighbour | Removed (handheld) | — |
| 5. Fanned members' home | Rest pose updated by the fan; lift and shot relative to it | Browser |
| 6. Pad flips cross | Each page flips about its own hinge; far edges descend so no two flipped pages intersect | `padFlipAngle` test |
| 7. Clip never moves | Detach and re-clip | Browser |
| 8. Resize double-LIFT | Shot from held/rest pose, not current y | — |
| 10. Click-through | `firstFocusable`: the nearest hit decides | `firstFocusable` test |

Minors 9, 11, 12 and 14 are deferred and listed in the final report; 13 is gone with the read pile.
