import * as THREE from "three";
import { expect, test } from "vitest";
import { placeOnDesk } from "../src/scene/models";
import { MIN_GAP } from "../src/scene/depth";

// Review I4: the lamp model has a clamp peg hanging 88 mm below its base; resting on the lowest vertex lifted the lamp off the desk.
function lampLike() {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.02, 0.1)); base.position.y = 0.01;        // base sits on model y = 0
  const peg = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.088, 0.02)); peg.position.y = -0.044;     // peg below it
  g.add(base, peg); return g;
}
test("default: lowest point rests on the desk", () => {
  const o = lampLike(); placeOnDesk(o, 0, 0); o.updateMatrixWorld(true);
  expect(new THREE.Box3().setFromObject(o).min.y).toBeCloseTo(MIN_GAP, 9);
});
test("baseY: the model's own base plane rests on the desk (peg goes into the desk)", () => {
  const o = lampLike(); placeOnDesk(o, 0, 0, 0, { baseY: 0 });
  expect(o.position.y).toBeCloseTo(MIN_GAP, 9);
});
