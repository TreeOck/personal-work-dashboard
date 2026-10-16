import { MIN_GAP, PAPER_T } from "../scene/layout";

const TILT = 0.3, OPENING = 0.6, BOARD_T = 0.002, HOLE = 0.005;
/** Angle of a page swung over the rings at progress p: all the way round to the back, `opening` short of a full turn. */
export const ringFlip = (p: number, opening = OPENING) => -p * (2 * Math.PI - opening);

/** A wire-bound tent calendar in the frame of its rings: origin on the ring axis, y the front page normal, z down the
 *  front. Pages and both boards hang from the rings; a page flipped over swings round the top and hangs outside the stand.
 *  e(k) is page k's offset from the axis on the front (page 0 on top); eBack(k) once flipped, where later pages hang further
 *  out. A page moves round the coil from one to the other while it points up, clear of both legs (offset(k, p)). */
export function tentLayout(d: number, n: number) {
  // Coil order at the top, front to back: page 0 … page n-1, front board, stand, then flipped pages (page 0 first, each
  // later one further out). Every page keeps a slot on both sides, so the axis sits mid-way through 2n pages + 2 boards.
  const q = PAPER_T + MIN_GAP, T = 2 * n * q + 2 * (BOARD_T + MIN_GAP);
  const e = (k: number) => T / 2 - q / 2 - k * q;
  const front = T / 2 - n * q - BOARD_T / 2 - MIN_GAP / 2, back = front - BOARD_T - MIN_GAP;
  const eBack = (k: number) => back - BOARD_T / 2 - q / 2 - k * q;                     // outside the stand: smaller e is further out
  const board = { front, back, frontLength: d - HOLE, backLength: 0, t: BOARD_T };
  const offset = (k: number, p: number) => { const x = Math.min(1, Math.max(0, (p - 0.3) / 0.4)); return e(k) + (eBack(k) - e(k)) * x * x * (3 - 2 * x); };
  const ring = T / 2 + 0.004;                                                          // the coil hides where everything meets
  const rotX = Math.PI / 2 - TILT;
  const at = (eo: number, a: number, s: number) => ({ z: s * Math.cos(a) + eo * Math.sin(a), y: -s * Math.sin(a) + eo * Math.cos(a) });
  const wy = (p: { z: number; y: number }) => p.y * Math.cos(rotX) - p.z * Math.sin(rotX);   // world height above the axis
  const originY = MIN_GAP - wy(at(board.front, 0, board.frontLength));    // front board's bottom edge on the desk
  const leg = -(2 * Math.PI - OPENING), b0 = wy(at(board.back, leg, 0)), b1 = wy(at(board.back, leg, 1));
  board.backLength = (MIN_GAP - originY - b0) / (b1 - b0);
  return { rotX, opening: OPENING, hole: HOLE, e, eBack, offset, board, ring, originY };
}
