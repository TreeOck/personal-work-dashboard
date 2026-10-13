import * as THREE from "three";
import { expect, test } from "vitest";
import { Registry } from "../src/scene/focusables";

test("registry finds the focusable from any nested child and lists director items in insertion order", () => {
  const r = new Registry(), card = new THREE.Group(), child = new THREE.Mesh(); card.add(child);
  r.add({ item: { id: "card:a", group: "cards", pages: 2, turnable: true }, object: card, label: "x", size: { w: 0.148, h: 0.105 }, normal: [0, 1, 0],
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } });
  r.add({ item: { id: "notepad", group: "notepad", pages: 14, turnable: true }, object: new THREE.Group(), label: "x", size: { w: 0.1, h: 0.14 }, normal: [0, 1, 0],
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } });
  expect(r.ofObject(child)?.item.id).toBe("card:a");
  expect(r.ofObject(new THREE.Mesh())).toBeUndefined();
  expect(r.items().map(i => i.id)).toEqual(["card:a", "notepad"]);
});
