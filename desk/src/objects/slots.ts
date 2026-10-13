import { BINDER, CARD_SIZE, CUP, MAT, MIN_GAP, PAPER_T, STICKY_AREA, STICKY_SIZE, TRAY, restOn, stackY } from "../scene/layout";
import { seededRandom } from "../paper/layout";

export function cardSlots(n: number) {
  const cols = 3, gapX = 0.022, gapZ = 0.03, r = seededRandom("cards");
  const x0 = MAT.x - (cols - 1) / 2 * (CARD_SIZE.w + gapX), z0 = MAT.z - (CARD_SIZE.d + gapZ) / 2;
  return [...Array(Math.min(n, 6))].map((_, i) => ({ x: x0 + (i % cols) * (CARD_SIZE.w + gapX), z: z0 + Math.floor(i / cols) * (CARD_SIZE.d + gapZ),
    rotY: (r() - 0.5) * 0.05 }));
}
export function stickySlots(n: number) {
  const r = seededRandom("stickies"), gap = 0.012;
  return [...Array(Math.min(n, 8))].map((_, i) => ({ x: STICKY_AREA.x + (i % STICKY_AREA.cols - 1.5) * (STICKY_SIZE.w + gap),
    z: STICKY_AREA.z - Math.floor(i / STICKY_AREA.cols) * (STICKY_SIZE.d + gap), rotY: (r() - 0.5) * 0.12 }));
}
export function trayStack(n: number) {
  const r = seededRandom("tray"), floor = restOn(TRAY.wall);   // never coplanar with the tray floor
  return [...Array(n)].map((_, i) => ({ y: stackY(floor, i, PAPER_T), jitterX: (r() - 0.5) * 0.006, jitterZ: (r() - 0.5) * 0.006, rotY: (r() - 0.5) * 0.03 }));
}
/** Bottom y of each notepad sheet, starting just above the desk. */
export const notepadSheets = (n: number) => [...Array(n)].map((_, i) => stackY(restOn(0), i, PAPER_T));
/** Bottom y of each stacked binder, starting just above the desk. */
export const binderBases = (n: number) => [...Array(n)].map((_, i) => restOn(0) + i * (BINDER.h + MIN_GAP));
/** Height of n stacked sheets (n thicknesses + the gaps between them). */
export const stackBlockHeight = (n: number) => (n ? n * PAPER_T + (n - 1) * MIN_GAP : 0);

export const PEN = { r: 0.0055, len: 0.14 } as const;
const LYING = { x: [0.07, -0.09], z0: -0.115, pitch: 0.016, perRow: 4 } as const;   // two rows between calendar and cup
/** Up to 7 pens stand in the cup; the next 8 lie on the desk; any beyond that go back in the cup on an inner ring. */
export function penSlots(n: number) {
  const lyingCount = Math.min(Math.max(n - 7, 0), LYING.perRow * 2);
  const lying = [...Array(lyingCount)].map((_, k) => ({ x: LYING.x[Math.floor(k / LYING.perRow)], y: restOn(0) + PEN.r,
    z: LYING.z0 + (k % LYING.perRow) * LYING.pitch, rotY: 0 }));
  const cupCount = n - lyingCount, outer = Math.min(cupCount, 7), inner = cupCount - outer;
  const ring = (count: number, radius: number, phase: number) => [...Array(count)].map((_, i) => {
    const a = phase + (2 * Math.PI * i) / count;
    return { x: CUP.x + Math.cos(a) * radius, z: CUP.z + Math.sin(a) * radius, angle: a }; });
  // inner ring radius from its count so neighbours clear one pen diameter (chord = 2r·sin(π/k))
  const innerR = inner > 1 ? Math.max(0.0095, (PEN.r + 0.0003) / Math.sin(Math.PI / inner)) : 0;
  return { inCup: [...ring(outer, outer > 1 ? 0.022 : 0, 0), ...ring(inner, innerR, 0.3)], lying };
}
/** Tray parts (metres, tray-local): the floor sits between the walls, so no faces are shared. */
export function trayParts() {
  const inner = TRAY.w - 2 * TRAY.wall;
  return { floor: { w: inner, d: TRAY.d - 2 * TRAY.wall, h: TRAY.wall }, side: { w: TRAY.wall, d: TRAY.d, h: TRAY.h },
    back: { w: inner, d: TRAY.wall, h: TRAY.h * 0.6 } };
}


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

/** A clipped stack of single-sided pages; index 0 is the top page. y = page bottom above the stack base. */
export function pageStack(n: number) {
  const r = seededRandom("pages:" + n);
  return [...Array(n)].map((_, i) => ({ y: stackY(0, n - 1 - i, PAPER_T), dx: (r() - 0.5) * 0.001, dz: (r() - 0.5) * 0.001, rotY: (r() - 0.5) * 0.008 }));   // clipped stacks are neat
}
/** Height of the solid body drawn around the pages still in a stack (it shrinks as pages are turned away). */
export const stackBodyHeight = (remaining: number) => (remaining > 0 ? stackBlockHeight(remaining) : 0);
