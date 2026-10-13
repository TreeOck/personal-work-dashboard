// The physical rules of reading something you hold or that lies on the desk. Pure maths, so it is tested exactly.
import { MIN_GAP, PAPER_T } from "../scene/layout";
import { stackBlockHeight } from "../objects/slots";

const Q = PAPER_T + MIN_GAP;                                      // centre-to-centre pitch of stacked sheets
const smooth = (t: number) => { const x = Math.min(1, Math.max(0, t)); return x * x * (3 - 2 * x); };

/** One thumb of a held stack, as a pose for every card at progress p (cards indexed by the slot they started in, 0 = top).
 *  dir 1: the top card slides out toward you until fully clear, drops below the stack while the others close up, and slides
 *  in underneath. dir -1 is exactly that played backwards: the bottom card comes out, rises, and slides in on top. */
export function thumbPose(n: number, dir: 1 | -1, p: number, d: number) {
  const slotY = (j: number) => (n - 1 - j) * Q + PAPER_T / 2, clear = d + 0.01;
  const t = dir === 1 ? p : 1 - p;                                // the forward path at time t
  const out = smooth(t * 3), down = smooth(t * 3 - 1), back = smooth(t * 3 - 2);
  const moverF = { y: slotY(0) + (slotY(n - 1) - slotY(0)) * down, z: clear * (out - back) };
  const shift = down * Q;                                         // the others close up while the card is clear of them
  const cards = [...Array(n)].map((_, j) => {
    if (dir === 1) return j === 0 ? moverF : { y: slotY(j) + shift, z: 0 };
    return j === n - 1 ? moverF : { y: slotY(j + 1) + shift, z: 0 };   // backwards: slot j holds the forward card from j + 1
  });
  const whole = p <= 0 || p >= 1;
  return { cards, mover: dir === 1 ? 0 : n - 1,
    body: whole ? { base: 0, h: stackBlockHeight(n) } : { base: dir === 1 ? shift : Q - shift, h: stackBlockHeight(n - 1) } };
}

/** Lowest root height (page centre-line) at which a flipped page clears a binding block `depth` deep behind the hinge whose
 *  top is at `top`, given where its far edge lands and its length. */
export function padRoot(top: number, depth: number, far: number, L: number) {
  let root = top + MIN_GAP + PAPER_T / 2;
  const yAt = (r: number) => { const b = Math.asin(Math.min(1, (r - far) / L)); return r - depth * Math.tan(b); };
  while (yAt(root) - PAPER_T / 2 < top + MIN_GAP) root += 0.0001;
  return root;
}

/** Page k of a top-bound pad flipped over its binding, at progress p. Flipped pages lie parallel, each one pitch above the
 *  one flipped before it: the root rides up over the binding (root0 + k·q) while the page is still in front of the hinge,
 *  and the far edge lands at far0 + k·q (the desk, or for a pad held in the hand, a fixed droop). */
export function padFlip(k: number, p: number, o: { home: (k: number) => number; root0: number; far0: number; q: number; L: number }) {
  const root = o.root0 + k * o.q, far = o.far0 + k * o.q, home = o.home(k);
  const final = -(Math.PI + Math.asin(Math.min(1, Math.max(-1, (root - far) / o.L))));
  return { y: home + (root - home) * smooth(p / 0.35), angle: final * p };
}

export type Quality = "hi" | "low" | "none";
/** Only the page on top has a printed face: sharp while it is being read, small on the desk. The rest carry no texture. */
export const pageQuality = (i: number, top: number, focused: boolean): Quality => (i !== top ? "none" : focused ? "hi" : "low");

/** Textures we created, one per page at most; replacing or clearing disposes them. Shared textures never go in here. */
export class TextureLedger<T extends { dispose(): void }> {
  private live = new Map<number, T>();
  set(i: number, t: T | null) { this.live.get(i)?.dispose(); if (t) this.live.set(i, t); else this.live.delete(i); }
  clear() { for (const t of this.live.values()) t.dispose(); this.live.clear(); }
  get size() { return this.live.size; }
}

/** How many single moves get from page `from` to `to`, and which way. A cyclic stack goes the way pressed, or with no
 *  direction (putting it down) the shorter way round, ties forward. A pad just flips toward the target. */
export function stepsTo(from: number, to: number, n: number, dir: 1 | -1 | undefined, cyclic: boolean): { steps: number; dir: 1 | -1 } {
  if (!cyclic) return { steps: Math.abs(to - from), dir: to < from ? -1 : 1 };
  const fwd = (((to - from) % n) + n) % n, bwd = (n - fwd) % n;
  if (dir) return { steps: dir === 1 ? fwd : bwd, dir };
  return bwd < fwd ? { steps: bwd, dir: -1 } : { steps: fwd, dir: 1 };
}
