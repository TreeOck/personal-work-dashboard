import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { drawPaper } from "../paper/render";
import { BINDER, CALENDAR, MIN_GAP, NOTEPAD, PAPER_T, restOn } from "../scene/layout";
import type { materials } from "../scene/materials";
import { Registry } from "../scene/focusables";
import { FLAT_NORMAL } from "../camera/shots";
import { binderBases, pageStack, stackBlockHeight, stackBodyHeight } from "./slots";
import { makePaperCard } from "./paperCard";
import { renderTallyPage } from "../paper/tallyPage";
import { renderCalendarPage } from "../paper/calendarPage";
import { ringFlip, tentLayout } from "./calendarTent";
import { setBodyHeight, stackBlock, stackBody } from "./paperObjects";
import { padRoot } from "../interaction/reading";
const HIDDEN_EDGE = new THREE.MeshBasicMaterial({ visible: false });

type M = ReturnType<typeof materials>;
const canvasTex = (w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) => {
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d")!);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

/** A wire-bound tent calendar: one page per day of the past week, today on top. Pages swing over the coil onto the back
 *  (calendarTent.ts has the geometry and its tests). */
export function addCalendar(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const days = model.days.slice(0, 7), n = days.length, d = CALENDAR.h, t = tentLayout(d, n), w = CALENDAR.w, top = d / 2 - t.hole;
  const cal = new THREE.Group(); cal.name = "calendar";                       // origin mid-page, so the camera frames the page
  const rig = new THREE.Group(); rig.position.z = -top; cal.add(rig);         // rig origin on the coil axis
  const hang = (y: number, angle: number, child: THREE.Object3D, s0: number) => {
    const pivot = new THREE.Group(); pivot.rotation.x = angle; child.position.set(0, y, s0); pivot.add(child); rig.add(pivot); return pivot; };
  const board = (len: number) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, t.board.t, len + t.hole), m.paper(undefined, 0x8a7a66));
    b.castShadow = b.receiveShadow = true; return b; };
  hang(t.board.front, 0, board(t.board.frontLength), (t.board.frontLength - t.hole) / 2);
  hang(t.board.back, ringFlip(1, t.opening), board(t.board.backLength), (t.board.backLength - t.hole) / 2);
  const low = (() => { const x = new THREE.CanvasTexture(renderCalendarPage(days[0], 6)); x.colorSpace = THREE.SRGBColorSpace; x.anisotropy = 8; return x; })();
  const meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  days.forEach((_, k) => {
    const sheet = makePaperCard(w, d, m.paper(k === 0 ? low : undefined, 0xece5d6), m.paper(undefined, 0xece5d6), m.paper(undefined, 0xece5d6));
    const pivot = hang(t.e(k), 0, sheet, d / 2 - t.hole); pivot.name = "page" + k;
    meshes.push(pivot); homes.push({ position: pivot.position.clone(), rotation: pivot.rotation.clone() });
  });
  const wire = new THREE.MeshPhysicalMaterial({ color: 0x2b2b2e, metalness: 1, roughness: 0.35 });
  for (let x = -w / 2 + 0.008; x <= w / 2 - 0.008 + 1e-9; x += 0.012) {        // the coil, one loop per punched hole
    const loop = new THREE.Mesh(new THREE.TorusGeometry(t.ring, 0.0007, 6, 32), wire); loop.rotation.y = Math.PI / 2; loop.position.x = x; loop.castShadow = true; rig.add(loop);
  }
  cal.position.set(CALENDAR.x, t.originY - top * Math.sin(t.rotX), CALENDAR.z + top * Math.cos(t.rotX)); cal.rotation.x = t.rotX;
  scene.add(cal);
  const pose = (k: number, p: number) => { meshes[k].rotation.x = ringFlip(p, t.opening); meshes[k].children[0].position.y = t.offset(k, p); };
  reg.add({ item: { id: "calendar", group: "calendar", pages: n, turnable: n > 1 }, object: cal, label: "Calendar", size: { w, h: d },
    normal: [0, Math.sin(0.3), Math.cos(0.3)], home: { position: cal.position.clone(), rotation: cal.rotation.clone() },
    pages: { count: n, style: "flip", meshes, homes, size: { w, d }, low, base: 0xece5d6, bodyBase: 0, pose, render: (i, px) => renderCalendarPage(days[i], px) } });
}

export function addNotepad(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const pad = new THREE.Group(); pad.name = "notepad";
  const size = { w: NOTEPAD.w, d: NOTEPAD.d }, blankSheets = 10, n = model.days.length;
  const block = stackBlock(m, size.w, size.d, stackBlockHeight(blankSheets), blankSheets);            // unused pages under the day pages
  block.position.y = restOn(0) + stackBlockHeight(blankSheets) / 2; pad.add(block);
  const base = restOn(0) + stackBlockHeight(blankSheets) + MIN_GAP, slots = pageStack(n);
  const hingeY = base + slots[0].y + PAPER_T;                         // top of the top page
  const BIND = { depth: 0.012, top: hingeY + 0.003 };                // a card header behind the hinge, a little above the pages
  const low = (() => { const t = new THREE.CanvasTexture(renderTallyPage(model.days[0], 6)); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; })();
  const meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  slots.forEach((s, i) => {                                       // each day page hinges on the top binding
    const pivot = new THREE.Group(); pivot.name = "page" + i; pivot.position.set(0, base + s.y + PAPER_T / 2, -size.d / 2);
    const sheet = makePaperCard(size.w, size.d, m.paper(i === 0 ? low : undefined, 0xf6efe0), m.paper(undefined, 0xf6efe0), HIDDEN_EDGE);   // body draws the sides
    sheet.position.z = size.d / 2; pivot.add(sheet); pad.add(pivot); meshes.push(pivot); homes.push({ position: pivot.position.clone(), rotation: pivot.rotation.clone() });
  });
  const body = stackBody(m, size.w, size.d, n); setBodyHeight(body, base, stackBodyHeight(n)); pad.add(body);
  const bindH = BIND.top - restOn(0);
  const binding = new THREE.Mesh(new THREE.BoxGeometry(size.w + 0.002, bindH, BIND.depth), new THREE.MeshPhysicalMaterial({ color: 0x3a2a20, roughness: 0.6 }));
  binding.position.set(0, restOn(0) + bindH / 2, -size.d / 2 - MIN_GAP - BIND.depth / 2); binding.castShadow = binding.receiveShadow = true; pad.add(binding);
  const far0 = MIN_GAP + PAPER_T / 2, q = PAPER_T + MIN_GAP;          // flipped pages land on the desk behind, each on the one before
  const flip = { root0: padRoot(BIND.top, BIND.depth + MIN_GAP, far0, size.d), far0, q, L: size.d };
  pad.position.set(NOTEPAD.x, 0, NOTEPAD.z); pad.rotation.y = -0.35; scene.add(pad);
  reg.add({ item: { id: "notepad", group: "notepad", pages: n, turnable: n > 1 }, object: pad, size: { w: size.w, h: size.d }, normal: FLAT_NORMAL,
    label: "Today's tally", pages: { count: n, style: "flip", meshes, homes, size, flip, low, base: 0xf6efe0, body, bodyBase: base, render: (i, px) => renderTallyPage(model.days[i], px) },
    home: { position: pad.position.clone(), rotation: pad.rotation.clone() } });
}

export function addBinders(scene: THREE.Scene, m: M) {
  const tints = [0x6b2f22, 0x2f4a3a, 0x2c3b58], labels = ["DAY", "WEEK", "MONTH"];
  labels.forEach((label, i) => {
    const cover = m.leather.clone(); cover.color = new THREE.Color(tints[i]);
    const spineLabel = canvasTex(512, 96, g => { drawPaper(g, 512, 96, "#ece5d6", label); g.fillStyle = "#231a14"; g.font = "52px 'Special Elite'";
      g.textAlign = "center"; g.fillText(label, 256, 66); });
    const b = new THREE.Mesh(new THREE.BoxGeometry(BINDER.w, BINDER.h, BINDER.d), [cover, cover, cover, cover, cover, cover]);
    b.position.set(BINDER.x + i * 0.012, binderBases(3)[i] + BINDER.h / 2, BINDER.z - i * 0.01); b.rotation.y = BINDER.rotY - i * 0.06;
    b.castShadow = b.receiveShadow = true; b.name = "binder:" + label.toLowerCase();
    const tag = new THREE.Mesh(new THREE.PlaneGeometry(0.14, 0.026), m.paper(spineLabel));
    tag.position.set(0, 0, BINDER.d / 2 + 0.0006); b.add(tag);                      // label on the spine edge, facing you
    scene.add(b);
  });
}
