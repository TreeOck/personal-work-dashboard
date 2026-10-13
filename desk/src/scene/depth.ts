export const CAMERA = { near: 0.05, far: 4, fov: 32 } as const;
export const MIN_GAP = 0.0006;      // metres between any stacked/overlapping surfaces
export const PAPER_T = 0.0003;      // sheet thickness
export const OVERVIEW = { position: [0.0, 0.95, 1.4] as [number, number, number], target: [0.0, 0, -0.05] as [number, number, number] };   // whole 1.6 m desk in a 16:9 view

export function depthResolutionAt(distance: number, near: number, far: number, bits = 24): number {
  return (distance * distance * (far - near)) / (far * near * 2 ** bits);
}
export const stackY = (base: number, index: number, thickness: number) => base + index * (thickness + MIN_GAP);
/** Height for the underside of anything resting on a surface: never exactly coplanar (that is what flickered in the mockup). */
export const restOn = (surfaceY: number) => surfaceY + MIN_GAP;
