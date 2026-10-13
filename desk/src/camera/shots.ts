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
