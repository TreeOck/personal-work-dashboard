import { expect, test } from "vitest";
import { calendarFace } from "../src/paper/calendarPage";
import { tentLayout } from "../src/objects/calendarTent";
import { ringFlip } from "../src/objects/calendarTent";
import { CALENDAR, MIN_GAP } from "../src/scene/layout";

const day = (ymd: string, commits: number) => ({ ymd, label: "", commits, tasks: 0, todosDone: 0, first: null, last: null });

test("a calendar page shows the month, the date, the weekday and that day's commits in a small hand", () => {
  expect(calendarFace(day("2026-10-16", 3))).toEqual({ month: "OCTOBER", day: 16, weekday: "Friday", tally: "3 commits" });
  expect(calendarFace(day("2026-10-13", 1)).tally).toBe("1 commit");
  expect(calendarFace(day("2026-11-01", 0))).toEqual({ month: "NOVEMBER", day: 1, weekday: "Sunday", tally: "no commits" });
});

// A wire-bound tent: every page and both boards hang from the ring axis C (local origin); y is the front page normal.
// A line at offset e from C, rotated by angle a: points (z, y) = (s·cos a + e·sin a, -s·sin a + e·cos a).
const line = (e: number, a: number, s0: number, s1: number) => [s0, s1].map(s => ({ z: s * Math.cos(a) + e * Math.sin(a), y: -s * Math.sin(a) + e * Math.cos(a) }));
type P = { z: number; y: number };
const cross = (o: P, a: P, b: P) => (a.z - o.z) * (b.y - o.y) - (a.y - o.y) * (b.z - o.z);
function meet([a, b]: P[], [c, e]: P[]): P | null {                       // proper intersection point, if any
  const d1 = cross(a, b, c), d2 = cross(a, b, e), d3 = cross(c, e, a), d4 = cross(c, e, b);
  if (!(d1 * d2 < 0 && d3 * d4 < 0)) return null;
  const t = d3 / (d3 - d4); return { z: a.z + (b.z - a.z) * t, y: a.y + (b.y - a.y) * t };
}
const n = 7, t = tentLayout(CALENDAR.h, n);       // a week: the coil has to wrap every page twice over
const page = (k: number, p: number) => line(t.offset(k, p), ringFlip(p, t.opening), -t.hole, CALENDAR.h - t.hole);
const front = line(t.board.front, 0, -t.hole, t.board.frontLength), stand = line(t.board.back, -(2 * Math.PI - t.opening), -t.hole, t.board.backLength);
const world = (q: P) => t.originY + q.y * Math.cos(t.rotX) - q.z * Math.sin(t.rotX);

test("the tent stands on the desk: both boards touch it and no page, flipped or not, goes through it", () => {
  expect(world(front[1])).toBeCloseTo(MIN_GAP, 6);
  expect(world(stand[1])).toBeCloseTo(MIN_GAP, 6);
  for (let k = 0; k < n; k++) for (const p of [0, 1]) expect(world(page(k, p)[1]), `page ${k} p=${p}`).toBeGreaterThan(MIN_GAP);
});
test("pages and boards only ever meet inside the wire rings, never out on the paper", () => {
  for (const k of [0, 1, 3, 6]) for (let i = 0; i <= 100; i++) {
    const p = i / 100, s = page(k, p), others = [front, stand, ...[...Array(n).keys()].filter(j => j !== k).map(j => page(j, j < k ? 1 : 0))];
    for (const o of others) { const m = meet(s, o); if (m) expect(Math.hypot(m.z, m.y), `k=${k} p=${p} other=${others.indexOf(o)} m=${m.z.toFixed(4)},${m.y.toFixed(4)}`).toBeLessThan(t.ring); }
  }
});
test("flipped pages hang outside the stand, each one further out than the one before", () => {
  const m = meet(front, stand); if (m) expect(Math.hypot(m.z, m.y)).toBeLessThan(t.ring);   // the legs only meet at the coil
  expect(t.ring).toBeLessThan(0.0135);                                                         // a desk-calendar-sized coil
  for (let k = 1; k < n; k++) expect(t.eBack(k)).toBeLessThan(t.eBack(k - 1));   // on the back, smaller e is further out
  expect(t.board.back).toBeGreaterThan(t.eBack(0));
  expect(t.board.front).toBeLessThan(t.e(n - 1));
});
