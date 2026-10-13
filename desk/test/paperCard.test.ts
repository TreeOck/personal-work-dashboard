import * as THREE from "three";
import { expect, test } from "vitest";
import { faceFor, makePaperCard } from "../src/objects/paperCard";

const mat = () => new THREE.MeshBasicMaterial();
// World position of a plane's UV corner (u, v) — e.g. (0,1) is the top-left of the drawn canvas.
function uvCorner(plane: THREE.Mesh, u: number, v: number): THREE.Vector3 {
  const g = plane.geometry as THREE.PlaneGeometry, uv = g.attributes.uv, pos = g.attributes.position;
  for (let i = 0; i < uv.count; i++) if (Math.abs(uv.getX(i) - u) < 1e-6 && Math.abs(uv.getY(i) - v) < 1e-6)
    return new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(plane.matrixWorld);
  throw new Error("corner not found");
}
const facing = (plane: THREE.Object3D) => new THREE.Vector3(0, 0, 1).applyQuaternion(plane.getWorldQuaternion(new THREE.Quaternion()));

test("front reads correctly from the seated side: canvas top-left is far-left, facing up", () => {
  const c = makePaperCard(0.148, 0.105, mat(), mat(), mat()); c.updateMatrixWorld(true);
  const f = c.getObjectByName("front") as THREE.Mesh;
  expect(facing(f).y).toBeCloseTo(1, 6);
  const tl = uvCorner(f, 0, 1); expect(tl.x).toBeLessThan(0); expect(tl.z).toBeLessThan(0);
});

test("after a flip about x, the back faces up and reads the same way (not mirrored, not upside down)", () => {
  const c = makePaperCard(0.148, 0.105, mat(), mat(), mat()); c.rotation.x += Math.PI; c.updateMatrixWorld(true);
  const b = c.getObjectByName("back") as THREE.Mesh;
  expect(facing(b).y).toBeCloseTo(1, 6);
  const tl = uvCorner(b, 0, 1), br = uvCorner(b, 1, 0);
  expect(tl.x).toBeLessThan(0); expect(tl.z).toBeLessThan(0); expect(br.x).toBeGreaterThan(0); expect(br.z).toBeGreaterThan(0);
});

test("faces sit on the card's own surfaces; even sides on the front, odd on the back", () => {
  const c = makePaperCard(0.1, 0.1, mat(), mat(), mat());
  expect((c.getObjectByName("front")!.position.y)).toBeGreaterThan((c.getObjectByName("back")!.position.y));
  expect([0, 1, 2, 3].map(faceFor)).toEqual(["front", "back", "front", "back"]);
});
