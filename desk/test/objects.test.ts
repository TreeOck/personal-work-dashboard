import { expect, test } from "vitest";
import { binderBases, cardSlots, notepadSheets, penSlots, stackBlockHeight, stickySlots, trayParts, trayStack } from "../src/objects/slots";
import { BINDER, CALENDAR, CARD_SIZE, CUP, MAT, MIN_GAP, NOTEPAD, PAPER_T, STICKY_SIZE, TRAY } from "../src/scene/layout";

test("up to 6 card slots, all fully on the leather mat, not overlapping", () => {
  const s = cardSlots(6);
  for (const p of s) {
    expect(Math.abs(p.x - MAT.x) + CARD_SIZE.w / 2).toBeLessThanOrEqual(MAT.w / 2);
    expect(Math.abs(p.z - MAT.z) + CARD_SIZE.d / 2).toBeLessThanOrEqual(MAT.d / 2);
  }
  for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++)
    expect(Math.abs(s[i].x - s[j].x) >= CARD_SIZE.w * 0.95 || Math.abs(s[i].z - s[j].z) >= CARD_SIZE.d * 0.95).toBe(true);
});
test("sticky slots don't overlap", () => {
  const s = stickySlots(8);
  for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++)
    expect(Math.abs(s[i].x - s[j].x) >= STICKY_SIZE.w || Math.abs(s[i].z - s[j].z) >= STICKY_SIZE.d).toBe(true);
});
test("tray stack: every sheet clears the one below by ≥ MIN_GAP; empty tray = no sheets", () => {
  expect(trayStack(0)).toEqual([]);
  const s = trayStack(25);
  for (let i = 1; i < s.length; i++) expect(s[i].y - s[i - 1].y).toBeGreaterThanOrEqual(PAPER_T + MIN_GAP - 1e-12);
});

// Task 7 ruling: the mockup flickered where something rested at exactly a surface's height.
test("nothing rests exactly on the surface below it", () => {
  expect(trayStack(1)[0].y).toBeCloseTo(TRAY.wall + MIN_GAP, 12);          // first sheet vs tray floor top
  expect(notepadSheets(12)[0]).toBeCloseTo(MIN_GAP, 12);                   // pad bottom vs desk top (y = 0)
  const b = binderBases(3);
  expect(b[0]).toBeCloseTo(MIN_GAP, 12);                                   // bottom binder vs desk
  for (let i = 1; i < b.length; i++) expect(b[i] - (b[i - 1] + BINDER.h)).toBeGreaterThanOrEqual(MIN_GAP - 1e-12);
});

// Task 10 finding: the notepad's spot was under the done tray, so it never showed.
test("desk objects don't share floor space (axis-aligned footprints, small rotations ignored)", () => {
  const fp = (x: number, z: number, w: number, d: number) => ({ x0: x - w / 2, x1: x + w / 2, z0: z - d / 2, z1: z + d / 2 });
  const items = {
    mat: fp(MAT.x, MAT.z, MAT.w, MAT.d), tray: fp(TRAY.x, TRAY.z, TRAY.w, TRAY.d), notepad: fp(NOTEPAD.x, NOTEPAD.z, NOTEPAD.w, NOTEPAD.d),
    binders: fp(BINDER.x, BINDER.z, BINDER.w, BINDER.d), calendar: fp(CALENDAR.x, CALENDAR.z, CALENDAR.w, CALENDAR.d),
  };
  const names = Object.keys(items) as (keyof typeof items)[];
  for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) {
    const a = items[names[i]], b = items[names[j]];
    const overlap = a.x0 < b.x1 && b.x0 < a.x1 && a.z0 < b.z1 && b.z0 < a.z1;
    expect(overlap, `${names[i]} overlaps ${names[j]}`).toBe(false);
  }
});

// Task 10 finding: 0.3 mm sheets drawn individually alias into a shimmering comb at overview distance.
// Stacks render as one block whose height still equals the sheets it stands for.
test("a stack block is exactly as tall as the sheets it replaces", () => {
  expect(stackBlockHeight(0)).toBe(0);
  const s = trayStack(23);
  expect(stackBlockHeight(23)).toBeCloseTo(s[22].y + PAPER_T - s[0].y, 12);
});

// Review I2/I3/M1: stickies 5-8 slid into the tray; overflow pens floated and crossed sticky #1;
// tray floor and walls shared their front face (z-fighting).
const PEN_R = 0.0055, PEN_LEN = 0.14;
type FP = { x0: number; x1: number; z0: number; z1: number; name: string };
const box = (name: string, x: number, z: number, w: number, d: number): FP => ({ name, x0: x - w / 2, x1: x + w / 2, z0: z - d / 2, z1: z + d / 2 });
const hit = (a: FP, b: FP) => a.x0 < b.x1 && b.x0 < a.x1 && a.z0 < b.z1 && b.z0 < a.z1;

test("all 8 sticky slots, the cup and up to 8 lying pens stay clear of each other and of the mat, tray and calendar", () => {
  const fixed = [box("mat", MAT.x, MAT.z, MAT.w, MAT.d), box("tray", TRAY.x, TRAY.z, TRAY.w + 0.04, TRAY.d + 0.04),   // +4 cm: tray is rotated
    box("calendar", CALENDAR.x, CALENDAR.z, CALENDAR.w, CALENDAR.d), box("cup", CUP.x, CUP.z, CUP.r * 2, CUP.r * 2),
    box("binders", BINDER.x, BINDER.z, BINDER.w + 0.06, BINDER.d + 0.06), box("notepad", NOTEPAD.x, NOTEPAD.z, NOTEPAD.w, NOTEPAD.d)];
  const stickies = stickySlots(8).map((s, i) => box("sticky" + i, s.x, s.z, STICKY_SIZE.w + 0.01, STICKY_SIZE.d + 0.01));
  const pens = penSlots(15).lying.map((p, i) => box("pen" + i, p.x, p.z, PEN_LEN, PEN_R * 2));
  const all = [...fixed, ...stickies, ...pens];
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
    if (i < fixed.length && j < fixed.length) continue;                 // fixed layout covered by the test above
    expect(hit(all[i], all[j]), `${all[i].name} overlaps ${all[j].name}`).toBe(false);
  }
  for (const f of [...stickies, ...pens]) { expect(f.x0).toBeGreaterThan(-0.8); expect(f.x1).toBeLessThan(0.8); expect(f.z0).toBeGreaterThan(-0.4); expect(f.z1).toBeLessThan(0.4); }
});

test("lying pens rest on the desk; pens in the cup never intersect each other", () => {
  for (const n of [7, 8, 12, 15, 20]) {
    const s = penSlots(n);
    expect(s.inCup.length + s.lying.length).toBe(n);
    for (const p of s.lying) expect(p.y - PEN_R).toBeCloseTo(MIN_GAP, 12);
    for (let i = 0; i < s.inCup.length; i++) for (let j = i + 1; j < s.inCup.length; j++)
      expect(Math.hypot(s.inCup[i].x - s.inCup[j].x, s.inCup[i].z - s.inCup[j].z)).toBeGreaterThanOrEqual(PEN_R * 2);
    for (const p of s.inCup) expect(Math.hypot(p.x - CUP.x, p.z - CUP.z) + PEN_R).toBeLessThanOrEqual(CUP.r);
  }
});

test("tray floor never shares a face with the walls", () => {
  const p = trayParts();
  expect(p.floor.d).toBeLessThan(TRAY.d);
  expect(p.floor.w).toBeLessThanOrEqual(TRAY.w - 2 * TRAY.wall + 1e-12);
});

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

import { pageStack } from "../src/objects/slots";

test("page stacks: top page is index 0, every page clears the one below, bottom page at the base", () => {
  const s = pageStack(5);
  expect(s[4].y).toBe(0);
  for (let i = 0; i < 4; i++) expect(s[i].y - s[i + 1].y).toBeCloseTo(PAPER_T + MIN_GAP, 12);
  for (const p of s) { expect(Math.abs(p.dx)).toBeLessThanOrEqual(0.0012); expect(Math.abs(p.rotY)).toBeLessThanOrEqual(0.012); }
  expect(pageStack(5)).toEqual(s);                                                      // deterministic
});
// R8 finding: the 0.6 mm anti-flicker gaps showed as white saw-teeth along a pad's edge. Stacks get one solid body whose
// height always equals the pages still in the stack (it shrinks as pages are turned away).
import { stackBodyHeight } from "../src/objects/slots";
test("a stack's body is exactly as tall as the pages still in it", () => {
  expect(stackBodyHeight(0)).toBe(0);
  expect(stackBodyHeight(1)).toBeCloseTo(PAPER_T, 12);
  for (const n of [2, 5, 14]) expect(stackBodyHeight(n)).toBeCloseTo(pageStack(n)[0].y + PAPER_T, 12);
});
