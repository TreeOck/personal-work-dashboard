import { describe, expect, test } from "vitest";
import { padFlip, padRoot, pageQuality, stepsTo, TextureLedger, thumbPose } from "../src/interaction/reading";
import { CARD_SIZE, MIN_GAP, NOTEPAD, PAPER_T, STICKY_SIZE } from "../src/scene/layout";

const q = PAPER_T + MIN_GAP, ps = [...Array(101)].map((_, i) => i / 100);

describe("thumbing a held stack (top card out toward you, down, and tucked under)", () => {
  const d = CARD_SIZE.d;
  const overlaps = (a: { y: number; z: number }, b: { y: number; z: number }) =>
    Math.abs(a.z - b.z) < d && Math.abs(a.y - b.y) < PAPER_T;                         // two flat cards of the same size share volume
  for (const n of [2, 3, 7]) for (const dir of [1, -1] as const) {
    test(`n=${n} dir=${dir}: the moving card never passes through another card`, () => {
      for (const p of ps) {
        const { cards, mover } = thumbPose(n, dir, p, d);
        cards.forEach((c, j) => { if (j !== mover) for (const o of cards.filter((_, i) => i !== mover && i !== j)) expect(overlaps(c, o)).toBe(false); });
        cards.forEach((c, j) => { if (j !== mover) expect(overlaps(cards[mover], c), `p=${p} vs slot ${j}`).toBe(false); });
      }
    });
    test(`n=${n} dir=${dir}: starts and ends exactly on the slots, one card rotated round`, () => {
      const slotY = (j: number) => (n - 1 - j) * q + PAPER_T / 2;
      const a = thumbPose(n, dir, 0, d), b = thumbPose(n, dir, 1, d);
      a.cards.forEach((c, j) => { expect(c.y).toBeCloseTo(slotY(j), 12); expect(c.z).toBe(0); });
      const to = (j: number) => (dir === 1 ? (j + n - 1) % n : (j + 1) % n);           // where the card that started in slot j ends
      b.cards.forEach((c, j) => { expect(c.y).toBeCloseTo(slotY(to(j)), 12); expect(c.z).toBeCloseTo(0, 12); });
      expect(a.mover).toBe(dir === 1 ? 0 : n - 1);
      expect(a.body).toEqual({ base: 0, h: n * PAPER_T + (n - 1) * MIN_GAP });
    });
  }
  test("the body hugs the cards still in the stack while one is out", () => {
    const { cards, mover, body } = thumbPose(4, 1, 0.5, d), rest = cards.filter((_, i) => i !== mover);
    expect(body.base).toBeCloseTo(Math.min(...rest.map(c => c.y)) - PAPER_T / 2, 12);
    expect(body.base + body.h).toBeCloseTo(Math.max(...rest.map(c => c.y)) + PAPER_T / 2, 12);
  });
});

// segment of a page hinged at (z=0, y) rotated by a about x: local (0,0,s) -> (z = s·cos a, y = Y - s·sin a)
const seg = (Y: number, a: number, L: number) => [{ z: 0, y: Y }, { z: L * Math.cos(a), y: Y - L * Math.sin(a) }];
type P = { z: number; y: number };
const cross = (o: P, a: P, b: P) => (a.z - o.z) * (b.y - o.y) - (a.y - o.y) * (b.z - o.z);
const properly = ([a, b]: P[], [c, e]: P[]) => cross(a, b, c) * cross(a, b, e) < 0 && cross(c, e, a) * cross(c, e, b) < 0;
const inBox = (s: P[], box: { z0: number; z1: number; top: number }) => [...Array(201)].some((_, i) => {
  const t = i / 200, z = s[0].z + (s[1].z - s[0].z) * t, y = s[0].y + (s[1].y - s[0].y) * t;
  return z > box.z0 && z < box.z1 && y - PAPER_T / 2 < box.top; });

describe("pad pages flipped over the top binding", () => {
  const n = 14, L = NOTEPAD.d, home = (k: number) => 0.004 + (n - 1 - k) * q + PAPER_T / 2;
  const bindTop = home(0) + PAPER_T / 2 + 0.003, gap = MIN_GAP, D = 0.012;
  const far0 = MIN_GAP + PAPER_T / 2, root0 = padRoot(bindTop, D + gap, far0, L);
  const o = { home, root0, far0, q, L };
  const binding = { z0: -(D + gap), z1: -gap, top: bindTop };
  const at = (k: number, p: number) => { const f = padFlip(k, p, o); return seg(f.y, f.angle, L); };
  test("flipped, each page lies behind the binding, clears it, and the far edge rests on the desk / the page before", () => {
    for (let k = 0; k < n; k++) {
      const s = at(k, 1);
      expect(s[1].z).toBeLessThan(-(D + gap));
      expect(s[1].y).toBeCloseTo(far0 + k * q, 9);
      expect(inBox(s, binding)).toBe(false);
      for (let j = 0; j < k; j++) expect(properly(s, at(j, 1))).toBe(false);
    }
  });
  test("while flipping, a page never crosses the flipped pages, the pages under it, or the binding", () => {
    for (const k of [0, 1, 6, 13]) for (const p of ps) {
      const s = at(k, p);
      expect(inBox(s, binding), `k=${k} p=${p}`).toBe(false);
      for (let j = 0; j < n; j++) if (j !== k) expect(properly(s, at(j, j < k ? 1 : 0)), `k=${k} p=${p} j=${j}`).toBe(false);
    }
  });
  test("a held sticky pad (no binding, nothing under it): flipped notes hang back at the same slope, never crossing", () => {
    const m = 5, Ls = STICKY_SIZE.d, h = (k: number) => (m - 1 - k) * q + PAPER_T / 2, r0 = h(0) + q;
    const so = { home: h, root0: r0, far0: r0 - Ls * Math.sin(0.3), q, L: Ls };
    const sAt = (k: number, p: number) => { const f = padFlip(k, p, so); return seg(f.y, f.angle, Ls); };
    for (let k = 0; k < m; k++) for (const p of ps) for (let j = 0; j < m; j++)
      if (j !== k) expect(properly(sAt(k, p), sAt(j, j < k ? 1 : 0)), `k=${k} p=${p} j=${j}`).toBe(false);
  });
});

describe("textures: one sharp page at a time, nothing left behind", () => {
  test("in focus only the page on top is sharp; on the desk only the top page has its small texture", () => {
    expect([0, 1, 2].map(i => pageQuality(i, 1, true))).toEqual(["none", "hi", "none"]);
    expect([0, 1, 2].map(i => pageQuality(i, 0, false))).toEqual(["low", "none", "none"]);
  });
  test("the ledger disposes what it replaces and everything on clear", () => {
    const made: { disposed: boolean; dispose(): void }[] = [], tex = () => { const t = { disposed: false, dispose() { t.disposed = true; } }; made.push(t); return t; };
    const l = new TextureLedger<(typeof made)[number]>();
    l.set(0, tex()); l.set(0, tex()); l.set(2, tex());
    expect(made.map(t => t.disposed)).toEqual([true, false, false]); expect(l.size).toBe(2);
    l.set(2, null); expect(made[2].disposed).toBe(true); expect(l.size).toBe(1);
    l.clear(); expect(made.every(t => t.disposed)).toBe(true); expect(l.size).toBe(0);
  });
});

describe("steps between pages", () => {
  test("a cyclic stack follows the direction pressed, even when both ways are one step (n=2)", () => {
    expect(stepsTo(1, 0, 2, 1, true)).toEqual({ steps: 1, dir: 1 });
    expect(stepsTo(1, 0, 2, -1, true)).toEqual({ steps: 1, dir: -1 });
    expect(stepsTo(0, 4, 5, -1, true)).toEqual({ steps: 1, dir: -1 });
  });
  test("putting a stack down goes the shorter way round to page 1 (ties go forward)", () => {
    expect(stepsTo(4, 0, 5, undefined, true)).toEqual({ steps: 1, dir: 1 });
    expect(stepsTo(1, 0, 5, undefined, true)).toEqual({ steps: 1, dir: -1 });
    expect(stepsTo(2, 0, 4, undefined, true)).toEqual({ steps: 2, dir: 1 });
    expect(stepsTo(3, 3, 5, undefined, true)).toEqual({ steps: 0, dir: 1 });
  });
  test("a pad just flips toward the target", () => {
    expect(stepsTo(0, 3, 14, 1, false)).toEqual({ steps: 3, dir: 1 });
    expect(stepsTo(13, 0, 14, 1, false)).toEqual({ steps: 13, dir: -1 });
  });
});

import { hiPxPerMm, neighbours } from "../src/interaction/reading";
describe("texture resolution follows the screen, not a fixed 24 px/mm", () => {
  test("a big page gets fewer pixels per mm than a small card, within 6..24", () => {
    expect(hiPxPerMm(1358, 0.3)).toBe(8);                      // binder leaf on a 1440p canvas: 2376 px tall, ~2.5x what shows
    expect(hiPxPerMm(1358, 0.148)).toBe(15);                   // index card
    expect(hiPxPerMm(2716, 0.148)).toBe(24);                   // retina: capped
    expect(hiPxPerMm(300, 0.3)).toBe(6);                       // tiny window: floor
  });
  test("while reading, the pages either side are made ready too (thumbed stacks wrap round)", () => {
    expect(neighbours(0, 5, true)).toEqual([4, 1]);
    expect(neighbours(0, 5, false)).toEqual([1]);
    expect(neighbours(4, 5, false)).toEqual([3]);
    expect(neighbours(0, 1, true)).toEqual([]);
  });
});
