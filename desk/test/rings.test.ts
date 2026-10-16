import { expect, test } from "vitest";
import { ringBook } from "../src/objects/rings";
import { MIN_GAP } from "../src/scene/layout";

// An open ring binder lying flat, 45 leaves: the hole of every page stays on the ring while it turns, and a page never
// crosses another out on the paper (only inside the ring, where the wire is).
const n = 45, R = 0.02, q = 0.0001 + 0.00015, base = 0.003 + MIN_GAP;
const b = ringBook({ R, hole: 0.006, L: 0.21, n, q, t: 0.0001, base });
type P = { z: number; y: number };
const cross = (o: P, a: P, c: P) => (a.z - o.z) * (c.y - o.y) - (a.y - o.y) * (c.z - o.z);
function meet([a, c]: P[], [d, e]: P[]): P | null {
  const d1 = cross(a, c, d), d2 = cross(a, c, e), d3 = cross(d, e, a), d4 = cross(d, e, c);
  if (!(d1 * d2 < 0 && d3 * d4 < 0)) return null;
  const t = d3 / (d3 - d4); return { z: a.z + (c.z - a.z) * t, y: a.y + (c.y - a.y) * t };
}
const ps = [...Array(101)].map((_, i) => i / 100);

test("both stacks lie flat on their covers, one pitch apart, inside the ring", () => {
  expect(b.segment(n - 1, 0)[0].y).toBeCloseTo(-R + base + 0.0001 / 2, 12);           // the right stack's bottom page on its cover
  expect(b.segment(0, 1)[0].y).toBeCloseTo(-R + base + 0.0001 / 2, 12);               // the first page turned lies on the other
  for (let k = 0; k < n; k++) {
    const r = b.segment(k, 0), l = b.segment(k, 1);
    expect(r[0].y).toBeCloseTo(r[1].y, 12); expect(l[0].y).toBeCloseTo(l[1].y, 12);
    expect(r[1].z).toBeGreaterThan(0); expect(l[1].z).toBeLessThan(0);                  // right stack right, left stack left
    expect(r[0].y - 0.0001 / 2).toBeGreaterThan(-R + base - 1e-12);
    expect(l[0].y - 0.0001 / 2).toBeGreaterThan(-R + base - 1e-12);                      // above the covers
    if (k) { expect(b.segment(k - 1, 0)[0].y - r[0].y).toBeCloseTo(q, 12); expect(l[0].y - b.segment(k - 1, 1)[0].y).toBeCloseTo(q, 12); }
  }
});
test("a page's hole stays on the ring all the way round", () => {
  for (const k of [0, 22, 44]) for (const p of ps) { const h = b.hole(k, p); expect(Math.hypot(h.z, h.y)).toBeCloseTo(R, 9); }
});
test("turning a page never crosses another page out on the paper", () => {
  for (const k of [0, 1, 22, 44]) for (const p of ps) {
    const s = b.segment(k, p);
    for (let j = 0; j < n; j++) if (j !== k) { const m = meet(s, b.segment(j, j < k ? 1 : 0)); if (m) expect(Math.hypot(m.z, m.y), `k=${k} p=${p} j=${j}`).toBeLessThan(R); }
  }
});
test("a block of pages turned together never crosses itself", () => {
  for (const p of ps) for (let k = 1; k < 10; k++) expect(meet(b.segment(k - 1, p), b.segment(k, p))).toBeNull();
});
