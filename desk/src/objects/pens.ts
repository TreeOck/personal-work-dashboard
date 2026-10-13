import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { CUP } from "../scene/layout";
import { PEN, penSlots } from "./slots";
import type { materials } from "../scene/materials";

export function addPenCup(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>) {
  const cup = new THREE.Mesh(new THREE.CylinderGeometry(CUP.r, CUP.r * 0.95, CUP.h, 64, 1, true), m.brass);
  cup.position.set(CUP.x, CUP.h / 2, CUP.z); cup.castShadow = cup.receiveShadow = true; scene.add(cup);
  const base = new THREE.Mesh(new THREE.CircleGeometry(CUP.r * 0.95, 48), m.brass);
  base.rotation.x = -Math.PI / 2; base.position.set(CUP.x, 0.0015, CUP.z); scene.add(base);
  const slots = penSlots(model.pens.length), cupN = slots.inCup.length;
  model.pens.forEach((p, i) => {
    const pen = new THREE.Group(); pen.name = "pen:" + p.project;
    const body = new THREE.Mesh(new THREE.CylinderGeometry(PEN.r, PEN.r, PEN.len, 24), m.penBody(p.ink.hex));
    const capBand = new THREE.Mesh(new THREE.CylinderGeometry(PEN.r + 0.0003, PEN.r + 0.0003, 0.004, 24),
      new THREE.MeshPhysicalMaterial({ color: p.ink.variant ? 0xc0c0c0 : 0xd4af6a, metalness: 1, roughness: 0.25 }));   // overflow variants get silver trim
    capBand.position.y = 0.035; body.castShadow = true; pen.add(body, capBand);
    if (i < cupN) {                                                    // standing in the cup, leaning out from its ring position
      const s = slots.inCup[i], lean = Math.hypot(s.x - CUP.x, s.z - CUP.z) > 0 ? 0.16 : 0;
      pen.position.set(s.x, 0.1, s.z); pen.rotation.set(Math.sin(s.angle) * lean, s.angle, -Math.cos(s.angle) * lean);
    } else {                                                           // lying on the desk, resting on it
      const s = slots.lying[i - cupN]; pen.rotation.set(0, s.rotY, Math.PI / 2); pen.position.set(s.x, s.y, s.z);
    }
    scene.add(pen);
  });
}
