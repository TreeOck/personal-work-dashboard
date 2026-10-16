// Sheets on the rings of an open binder lying flat. Frame: origin on the ring axis, y up; a page at angle 0 runs along +z
// (the right-hand stack) and turns over the top to angle -π (the left-hand stack). Page k's line passes e from the axis, and
// its punched hole sits on the ring wire, so while it turns the hole slides round the ring like real paper.
type P = { z: number; y: number };
const smooth = (t: number) => { const x = Math.min(1, Math.max(0, t)); return x * x * (3 - 2 * x); };

export function ringBook(o: { R: number; hole: number; L: number; n: number; q: number; t: number; base: number }) {
  const right = (k: number) => -o.R + o.base + (o.n - 1 - k) * o.q + o.t / 2;   // page 0 on top of the right stack
  const left = (k: number) => -o.R + o.base + k * o.q + o.t / 2;                 // page 0 at the bottom of the left stack
  const e = (k: number, p: number) => right(k) + (-left(k) - right(k)) * smooth((p - 0.3) / 0.4);   // moves round while upright
  const angle = (p: number) => -Math.PI * p;
  const at = (s: number, ee: number, a: number): P => ({ z: s * Math.cos(a) + ee * Math.sin(a), y: -s * Math.sin(a) + ee * Math.cos(a) });
  const sh = (ee: number) => Math.sqrt(Math.max(0, o.R * o.R - ee * ee));        // where along the page line the ring meets it
  /** What a page mesh needs: rotation about the axis, its line's offset, and where its inner edge starts along it. */
  const pose = (k: number, p: number) => { const ee = e(k, p); return { angle: angle(p), e: ee, s0: sh(ee) - o.hole }; };
  return {
    pose,
    hole: (k: number, p: number) => { const x = pose(k, p); return at(x.s0 + o.hole, x.e, x.angle); },
    segment: (k: number, p: number) => { const x = pose(k, p); return [at(x.s0, x.e, x.angle), at(x.s0 + o.L, x.e, x.angle)]; },
  };
}
