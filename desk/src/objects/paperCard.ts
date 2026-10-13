import * as THREE from "three";
import { PAPER_T } from "../scene/layout";

const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });

/** A sheet as two textured planes (front up, back down) plus its four edges. Flip it with rotation.x += π:
 *  both planes are rotated about x, so after the flip the back reads exactly like the front did. */
export function makePaperCard(w: number, d: number, front: THREE.Material, back: THREE.Material, edge: THREE.Material): THREE.Group {
  const g = new THREE.Group();
  const f = new THREE.Mesh(new THREE.PlaneGeometry(w, d), front);
  f.name = "front"; f.rotation.x = -Math.PI / 2; f.position.y = PAPER_T / 2;
  const b = new THREE.Mesh(new THREE.PlaneGeometry(w, d), back);
  b.name = "back"; b.rotation.x = Math.PI / 2; b.position.y = -PAPER_T / 2;
  const e = new THREE.Mesh(new THREE.BoxGeometry(w, PAPER_T, d), [edge, edge, HIDDEN, HIDDEN, edge, edge]);
  e.name = "edge";
  for (const m of [f, b, e]) { m.castShadow = m.receiveShadow = true; g.add(m); }
  return g;
}

export const faceFor = (side: number): "front" | "back" => (side % 2 === 0 ? "front" : "back");
