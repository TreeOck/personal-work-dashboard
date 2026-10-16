import type * as THREE from "three";

const shown = (o: THREE.Object3D | null): boolean => { for (let n = o; n; n = n.parent) if (!n.visible) return false; return true; };

/** The nearest hit that you can actually see decides what a click means (three's raycaster also hits hidden things).
 *  A lamp or tray in front of a card is the answer, even though it is not focusable. */
export function firstFocusable<F>(hits: THREE.Intersection[], resolve: (o: THREE.Object3D) => F | undefined): F | undefined {
  const h = firstVisible(hits); return h ? resolve(h.object) : undefined;
}
/** The nearest hit you can see (its point says where on the object you clicked). */
export function firstVisible(hits: THREE.Intersection[]): THREE.Intersection | undefined {
  for (const h of hits) {
    if (!shown(h.object)) continue;
    const m = (h.object as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
    const mat = Array.isArray(m) ? m[h.face?.materialIndex ?? 0] : m;
    if (mat && !mat.visible) continue;
    return h;
  }
  return undefined;
}
/** Which way a click on something you are reading turns it: the left half back, the right half forward (object-local x). */
export const clickTurn = (localX: number): 1 | -1 => (localX < 0 ? -1 : 1);
