import * as THREE from "three";
import { binderSheets, HEATMAP_MM, type BinderKind, type Period, type Sheet } from "../data/binders";
import type { DeskModel } from "../data/model";
import { drawPaper, drawSide, canvasMeasure, FONTS } from "../paper/render";
import { BINDER, MAT, MIN_GAP } from "../scene/layout";
import type { materials } from "../scene/materials";
import type { Focusable, Registry } from "../scene/focusables";
import { binderBases } from "./slots";
import { makePaperCard } from "./paperCard";
import { ringBook } from "./rings";
import { FLAT_NORMAL } from "../camera/shots";

type M = ReturnType<typeof materials>;
const KINDS: BinderKind[] = ["day", "week", "month"], TINTS = [0x6b2f22, 0x2f4a3a, 0x2c3b58];
const R = 0.02, ZS = 0.012, BT = 0.0025, HOLE = 0.006, LEAF_T = 0.0001, Q = 0.0001 + 0.00015;   // ring radius, spine set-back, board, leaf
const PAGE = { wMm: 210, hMm: 297 }, L = PAGE.wMm / 1000, H = BINDER.h, D = BINDER.d;
const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });

/** Where the three binders lie: stacked, each a little turned. Taking one out lets the ones above drop; one put back goes
 *  on top, the way you actually put a binder back. */
export function binderRack(members: Map<string, Focusable>) {
  const order: string[] = [];
  const slot = (k: number) => ({ position: new THREE.Vector3(BINDER.x + k * 0.012, binderBases(3)[k] + H / 2, BINDER.z - k * 0.01),
    rotation: new THREE.Euler(0, BINDER.rotY - k * 0.06, 0) });
  const reslot = () => order.forEach((id, k) => { const f = members.get(id)!, s = slot(k); f.rest.position.copy(s.position); f.rest.rotation.copy(s.rotation); });
  return {
    slot, order: () => [...order],
    /** Taken out: returns the binders that were above it (they drop one place). */
    take(id: string) { const i = order.indexOf(id); if (i < 0) return []; const above = order.slice(i + 1); order.splice(i, 1); reslot(); return above; },
    put(id: string) { if (!order.includes(id)) order.push(id); reslot(); },
  };
}

function renderLeaf(p: Period, sheet: Sheet, kind: BinderKind, px: number) {
  const c = document.createElement("canvas"); c.width = PAGE.wMm * px; c.height = PAGE.hMm * px; const g = c.getContext("2d")!;
  drawPaper(g, c.width, c.height, "#f7f3ea", `leaf:${kind}:${p.key}:${sheet.part}`);
  if (kind === "month" && sheet.part === 0) drawHeatmap(g, p, px);
  drawSide(g, sheet.side, "#231a14", `${kind}:${p.key}:${sheet.part}`, px, 12, 14);
  g.fillStyle = "#6b625a"; g.font = `${3 * px}px ${FONTS.typed}`; g.textAlign = "right";
  g.fillText(sheet.parts > 1 ? `${p.label} · ${sheet.part + 1}/${sheet.parts}` : p.label, (PAGE.wMm - 12) * px, (PAGE.hMm - 9) * px);
  return c;
}
/** The month at a glance: one cell per day, inked in the day's main project, darker for more commits. */
function drawHeatmap(g: CanvasRenderingContext2D, p: Period, px: number) {
  g.save();
  const max = Math.max(1, ...p.days.map(d => d.commits)), lead = (new Date(p.key + "-01T12:00:00Z").getUTCDay() + 6) % 7, cell = 22, x0 = 28, y0 = 18;
  g.font = `${3 * px}px ${FONTS.typed}`; g.fillStyle = "#6b625a"; g.textAlign = "center";
  "MTWTFSS".split("").forEach((l, i) => g.fillText(l, (x0 + i * cell + cell / 2) * px, (y0 - 2) * px));
  p.days.forEach((d, i) => {
    const k = i + lead, x = x0 + (k % 7) * cell, y = y0 + Math.floor(k / 7) * 9;
    g.strokeStyle = "rgba(60,50,40,.25)"; g.lineWidth = Math.max(1, px * 0.15); g.strokeRect((x + 1) * px, y * px, (cell - 2) * px, 8 * px);
    if (d.commits && d.ink) { g.globalAlpha = 0.2 + 0.7 * (d.commits / max); g.fillStyle = d.ink.hex; g.fillRect((x + 1.5) * px, (y + 0.5) * px, (cell - 3) * px, 7 * px); g.globalAlpha = 1; }
    g.fillStyle = "#231a14"; g.textAlign = "left"; g.fillText(String(i + 1), (x + 2.5) * px, (y + 3.5) * px); g.textAlign = "center";
  });
  g.restore();                                                     // leave the canvas as we found it (text alignment!)
  void HEATMAP_MM;
}

/** Which page of an open binder a click landed on (binder-local z): past the ring axis is the left-hand page, so back. */
export const binderSide = (localZ: number): 1 | -1 => (localZ > D / 2 - ZS ? -1 : 1);

/** The Day binder sheet to open for a date: that day's page, or the nearest earlier day that has one. */
export function daySheetFor(keys: string[], marks: number[], ymd: string) {
  let i = -1; keys.forEach((k, j) => { if (k <= ymd) i = j; });
  return marks[Math.max(0, i)];
}

export function addBinders(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const members = new Map<string, Focusable>(), rack = binderRack(members);
  KINDS.forEach((kind, i) => {
    const periods = model.binders[kind];
    const { sheets, marks, start } = binderSheets(periods, kind, canvasMeasure(), { width: PAGE.wMm - 24, height: PAGE.hMm - 34 });
    const n = sheets.length, book = ringBook({ R, hole: HOLE, L, n, q: Q, t: LEAF_T, base: BT + MIN_GAP });
    const cover = m.leather.clone(); cover.color = new THREE.Color(TINTS[i]);
    const obj = new THREE.Group(); obj.name = "binder:" + kind;
    const rig = new THREE.Group(); rig.position.set(0, -H / 2 + R, D / 2 - ZS); rig.rotation.y = Math.PI; obj.add(rig);   // origin on the ring axis
    const box = (w: number, h: number, d: number, mat: THREE.Material) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); b.castShadow = b.receiveShadow = true; return b; };
    // back cover (under the right-hand stack), with the ring mechanism
    const back = box(BINDER.w, BT, D, cover); back.position.set(0, -R + BT / 2, D / 2 - ZS); rig.add(back);
    const steel = new THREE.MeshPhysicalMaterial({ color: 0xc9ccd1, metalness: 1, roughness: 0.25 });
    for (const x of [-0.08, 0.08]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(R, 0.0012, 8, 48), steel); ring.rotation.y = Math.PI / 2; ring.position.x = x; ring.castShadow = true; rig.add(ring); }
    // the spine hinges on the back cover's edge; the front cover hinges on the spine's other edge
    const spine = new THREE.Group(); spine.position.set(0, -R, -ZS); rig.add(spine);
    const spineBox = box(BINDER.w, H, BT, cover); spineBox.position.set(0, H / 2, -BT / 2); spine.add(spineBox);
    const tagTex = (() => { const c = document.createElement("canvas"); c.width = 512; c.height = 96; const g = c.getContext("2d")!; drawPaper(g, 512, 96, "#ece5d6", kind);
      g.fillStyle = "#231a14"; g.font = "52px 'Special Elite'"; g.textAlign = "center"; g.fillText(kind.toUpperCase(), 256, 66);
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
    const tag = new THREE.Mesh(new THREE.PlaneGeometry(0.14, 0.026), m.paper(tagTex)); tag.position.set(0, H / 2, -BT - 0.0004); tag.rotation.y = Math.PI; spineBox.parent!.add(tag);
    const front = new THREE.Group(); rig.add(front);
    const frontBox = box(BINDER.w, BT, D, cover); frontBox.position.set(0, -BT / 2, D / 2); front.add(frontBox);
    const label = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 0.05), m.paper(tagTex)); label.name = "front";   // a paper label on the cover
    label.rotation.x = -Math.PI / 2; label.position.set(0, 0.0004, D / 2); front.add(label);
    const coverAt = (u: number) => {                                    // u: 0 closed, 1 open flat to the left
      const a = (u * Math.PI) / 2; spine.rotation.x = -a;
      front.position.set(0, -R + H * Math.cos(a), -ZS - H * Math.sin(a)); front.rotation.x = -u * Math.PI;
    };
    coverAt(0);
    // the leaves, and a solid block standing in for them while the binder is shut
    const leaves: THREE.Object3D[] = [];
    sheets.forEach((_, k) => {
      const pivot = new THREE.Group(), sheet = makePaperCard(L, PAGE.hMm / 1000, m.paper(undefined, 0xf7f3ea), m.paper(undefined, 0xf7f3ea), HIDDEN);
      sheet.rotation.y = -Math.PI / 2;                                  // text runs along the spine, top toward the rig's +x
      const holder = new THREE.Group(); holder.add(sheet); pivot.add(holder); pivot.name = "leaf" + k; pivot.visible = false; rig.add(pivot); leaves.push(pivot);
    });
    const leafAt = (k: number, p: number) => { const x = book.pose(k, p); leaves[k].rotation.x = x.angle; (leaves[k].children[0] as THREE.Object3D).position.set(0, x.e, x.s0 + L / 2); };
    sheets.forEach((_, k) => leafAt(k, 0));
    const block = box(BINDER.w - 0.012, Math.max(0.001, n * Q), L, m.paper(undefined, 0xf7f3ea)); block.position.set(0, -R + BT + MIN_GAP + n * Q / 2, ZS + L / 2 - 0.002); rig.add(block);
    const show = (open: boolean) => { leaves.forEach(l => (l.visible = open)); block.visible = !open; };
    const meshes = [front, ...leaves];                                   // sheet 0 is the cover
    const homes = meshes.map(o => ({ position: o.position.clone(), rotation: o.rotation.clone() }));
    const low = tagTex;
    scene.add(obj);
    const heldAt = new THREE.Vector3(MAT.x + (D / 2 - ZS), MAT.t + 0.18, MAT.z + 0.01);   // spine over the middle of the mat
    const f: Omit<Focusable, "rest"> = {
      item: { id: obj.name, group: "binders", pages: n + 1, turnable: n > 0, min: 1, start, marks }, object: obj, label: kind[0].toUpperCase() + kind.slice(1) + " binder",
      size: { w: 0.5, h: 0.32 }, normal: FLAT_NORMAL, held: true, heldAt, heldRotY: -Math.PI / 2,
      heldShot: new THREE.Vector3(MAT.x, heldAt.y - H / 2 + R, heldAt.z), sideOf: v => binderSide(v.z), slide: new THREE.Vector3(0, 0, D + 0.04), rack,
      home: { position: new THREE.Vector3(), rotation: new THREE.Euler() },
      pages: { count: n + 1, style: "flip", block: true, meshes, homes, size: { w: BINDER.w, d: D }, low, base: 0xece5d6, bodyBase: 0, show,
        pose: (k, p) => (k === 0 ? coverAt(p) : leafAt(k - 1, p)),
        render: (k, px) => (k === 0 ? (tagTex.image as HTMLCanvasElement) : renderLeaf(periods[sheets[k - 1].period], sheets[k - 1], kind, px)) },
    };
    if (kind === "day") { const cal = reg.get("calendar"), days = model.days.slice(0, 7), keys = periods.map(p => p.key);
      if (cal) cal.link = top => ({ type: "select", id: obj.name, page: daySheetFor(keys, marks, days[top]?.ymd ?? days[0].ymd) }); }
    reg.add(f); const g = reg.get(obj.name)!; members.set(obj.name, g); rack.put(obj.name);   // stacked in order: day, week, month on top
    obj.position.copy(g.rest.position); obj.rotation.copy(g.rest.rotation); g.home.position.copy(g.rest.position); g.home.rotation.copy(g.rest.rotation);
  });
}
