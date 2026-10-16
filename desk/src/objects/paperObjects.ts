import * as THREE from "three";
import type { CardVM, DeskModel } from "../data/model";
import { cardBlocks, doneBlocks, layoutSides, overflowMark } from "../paper/layout";
import { canvasMeasure, drawPaper, drawSide } from "../paper/render";
import { CARD_PILE, MAT, MIN_GAP, PAPER_T, SHEET_SIZE, STICKY_SIZE, TRAY, restOn } from "../scene/layout";
import { FLAT_NORMAL } from "../camera/shots";
import { cardPages, PAPER, renderPage, type PaperKind } from "../paper/cardTexture";
import { Registry } from "../scene/focusables";
import { makePaperCard } from "./paperCard";
import { pageStack, stackBodyHeight, stickyLayout } from "./slots";
import type { materials } from "../scene/materials";
import { cardSlots, stickySlots, trayParts, trayStack } from "./slots";

type M = ReturnType<typeof materials>;
const PX_PER_MM = 6;   // overview resolution; Plan 2 re-renders the focused card at 24 px/mm

function textureFor(c: CardVM, kind: "card" | "sticky" | "sheet", wMm: number, hMm: number, base: string) {
  const canvas = document.createElement("canvas"); canvas.width = Math.round(wMm * PX_PER_MM); canvas.height = Math.round(hMm * PX_PER_MM);
  const ctx = canvas.getContext("2d")!;
  drawPaper(ctx, canvas.width, canvas.height, base, c.id);
  // leave a 6 mm strip at the bottom for the "continued overleaf" mark, so it never covers text
  const sides = layoutSides(cardBlocks(c, kind === "sticky" ? "sticky" : "card"), canvasMeasure(), { width: wMm - 12, height: hMm - 18 });
  drawSide(ctx, sides[0], c.ink.hex, c.id, PX_PER_MM);
  const mark = overflowMark(sides.length);
  if (mark) {                                                // review I1: never cut content silently
    ctx.save(); ctx.fillStyle = c.ink.hex; ctx.globalAlpha = 0.9; ctx.font = `${4.2 * 1.25 * PX_PER_MM}px 'Caveat'`; ctx.textAlign = "right";
    ctx.fillText(mark, (wMm - 5) * PX_PER_MM, (hMm - 4) * PX_PER_MM); ctx.restore();
  }
  const t = new THREE.CanvasTexture(canvas); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return { texture: t, sides: sides.length };
}

function sheet(m: M, w: number, d: number, top: THREE.Texture | null, y: number) {
  const edge = m.paper(undefined), face = m.paper(top ?? undefined);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, PAPER_T, d), [edge, edge, face, edge, edge, edge]);
  mesh.position.y = y; mesh.castShadow = mesh.receiveShadow = true; return mesh;
}

/** A pile of sheets drawn as one solid block: individual 0.3 mm sheets alias into a shimmering comb at a distance.
 *  The sides carry a fine page-line texture (mip-mapped, so it blurs smoothly instead of flickering). */
let edgeTex: THREE.Texture | null = null;
export function stackBlock(m: M, w: number, d: number, h: number, sheets: number) {
  if (!edgeTex) {
    const c = document.createElement("canvas"); c.width = 64; c.height = 256; const g = c.getContext("2d")!;
    g.fillStyle = "#efe8da"; g.fillRect(0, 0, 64, 256);
    for (let y = 0; y < 256; y += 4) { g.fillStyle = `rgba(90,75,55,${0.18 + Math.random() * 0.12})`; g.fillRect(0, y, 64, 1); }
    edgeTex = new THREE.CanvasTexture(c); edgeTex.colorSpace = THREE.SRGBColorSpace; edgeTex.wrapS = edgeTex.wrapT = THREE.RepeatWrapping;
    edgeTex.generateMipmaps = true; edgeTex.minFilter = THREE.LinearMipmapLinearFilter;
  }
  const side = (len: number) => { const t = edgeTex!.clone(); t.repeat.set(len / 0.05, Math.max(1, sheets) / 64); t.needsUpdate = true; return m.paper(t); };
  const top = m.paper(), sx = side(d), sz = side(w);
  const block = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), [sx, sx, top, top, sz, sz]);
  block.castShadow = block.receiveShadow = true; return block;
}

const LOW_PX = 6, STICKY_DROOP = 0.3;                       // radians a flipped sticky note hangs below level
const BASE = { card: 0xf1ebde, sticky: 0xf4d675 } as const;
const canvasTexture = (c: HTMLCanvasElement) => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

/** A small steel paper clip over the stack's top-left corner (spec §3a: clipped stack). */
export function paperClip(size: { w: number; d: number }, y: number) {
  const x0 = -size.w / 2 + 0.014, z0 = -size.d / 2 - 0.004, l = 0.03, a = 0.005, b = 0.0032;
  const pts = [[x0 - a, z0 + l], [x0 - a, z0], [x0 + a, z0], [x0 + a, z0 + l * 0.85], [x0 - b, z0 + l * 0.85], [x0 - b, z0 + 0.004], [x0 + b, z0 + 0.004], [x0 + b, z0 + l * 0.6]]
    .map(([x, z]) => new THREE.Vector3(x, y, z));
  const clip = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.1), 64, 0.0006, 8),
    new THREE.MeshPhysicalMaterial({ color: 0xb8bcc2, metalness: 1, roughness: 0.25 }));
  clip.name = "clip"; clip.castShadow = true; return clip;
}

/** A task as a clipped stack of single-sided cards (or a pad of sticky notes): one physical page per page of text. */
function pageStackItem(m: M, vm: CardVM, kind: PaperKind, id: string, group: "cards" | "stickies", pile?: "cardPile" | "stickyPile") {
  const content = cardPages(vm, kind), n = Math.max(1, content.length);
  const size = { w: PAPER[kind].wMm / 1000, d: PAPER[kind].hMm / 1000 };
  const low = canvasTexture(renderPage(vm, kind, content, 0, LOW_PX));
  const obj = new THREE.Group(); obj.name = id;
  const slots = pageStack(n), meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  const hinged = kind === "sticky";                                          // sticky notes are glued along the top edge
  slots.forEach((s, i) => {
    const edge = n > 1 ? HIDDEN : m.paper(undefined, BASE[kind]);          // multi-page: the body draws the sides
    const sheet = makePaperCard(size.w, size.d, m.paper(i === 0 ? low : undefined, BASE[kind]), m.paper(undefined, BASE[kind]), edge);
    let page: THREE.Object3D = sheet;
    if (hinged) { page = new THREE.Group(); sheet.position.z = size.d / 2; page.add(sheet); }   // pivot on the glued edge
    page.name = "page" + i; page.position.set(s.dx, s.y + PAPER_T / 2, s.dz - (hinged ? size.d / 2 : 0)); page.rotation.y = s.rotY;
    obj.add(page); meshes.push(page); homes.push({ position: page.position.clone(), rotation: page.rotation.clone() });
  });
  let body: THREE.Mesh | undefined;
  if (n > 1) { body = stackBody(m, size.w, size.d, n); setBodyHeight(body, 0, stackBodyHeight(n)); obj.add(body); }
  let clip: { mesh: THREE.Object3D; y: number } | undefined;
  if (kind === "card" && n > 1) { const y = slots[0].y + PAPER_T + MIN_GAP; clip = { mesh: paperClip(size, y), y }; obj.add(clip.mesh); }
  const q = PAPER_T + MIN_GAP, root0 = slots[0].y + PAPER_T / 2 + q;      // held up, flipped notes hang back over the glued edge
  const focusable = { item: { id, group, pages: n, turnable: n > 1, pile, cyclic: !hinged && n > 1 }, object: obj, size: { w: size.w, h: size.d }, normal: FLAT_NORMAL,
    label: vm.title, held: true, clip,
    pages: { count: n, style: hinged ? "flip" as const : "thumb" as const, meshes, homes, size, low, base: BASE[kind], body, bodyBase: 0,
      flip: hinged ? { root0, far0: root0 - size.d * Math.sin(STICKY_DROOP), q, L: size.d } : undefined,
      render: (i: number, px: number) => renderPage(vm, kind, content, i, px) },
    home: { position: new THREE.Vector3(), rotation: new THREE.Euler() } };
  return { obj, focusable };
}
const settle = (f: { object: THREE.Object3D; home: { position: THREE.Vector3; rotation: THREE.Euler } }) => {
  f.home.position.copy(f.object.position); f.home.rotation.copy(f.object.rotation); };

const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });
/** Solid side walls for a multi-page stack (top and bottom open): from the side it reads as one block of paper,
 *  not as separate sheets with gaps; from above you see the top page. Height is set by setBodyHeight(). */
export function stackBody(m: M, w: number, d: number, sheets: number): THREE.Mesh {
  const b = stackBlock(m, w, d, 1, sheets); const mats = b.material as THREE.Material[];
  mats[2] = HIDDEN; mats[3] = HIDDEN; b.name = "body"; return b;
}
export function setBodyHeight(body: THREE.Mesh, base: number, h: number) {
  body.visible = h > 0; body.scale.y = Math.max(h, 1e-6); body.position.y = base + h / 2;
}

export function addCards(scene: THREE.Scene, model: DeskModel, m: M, matTop: number, reg: Registry) {
  cardSlots(model.cards.length).forEach((s, i) => {
    const { obj, focusable } = pageStackItem(m, model.cards[i], "card", "card:" + model.cards[i].id, "cards");
    obj.position.set(s.x, restOn(matTop), s.z); obj.rotation.y = s.rotY; scene.add(obj); settle(focusable); reg.add(focusable);
  });
  if (model.cardOverflow.length) {
    const pile = new THREE.Group(); pile.name = "cardPile"; scene.add(pile);
    reg.add({ item: { id: "cardPile", group: "cardPile", pages: 1, turnable: false }, object: pile, size: { w: 0.33, h: 0.42 }, normal: FLAT_NORMAL,
      label: `${model.cardOverflow.length} more`, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    let base = restOn(MAT.t);                                                // each overflow stack rests on the one below
    model.cardOverflow.forEach(vm => {
      const { obj, focusable } = pageStackItem(m, vm, "card", "card:" + vm.id, "cards", "cardPile");
      obj.position.set(CARD_PILE.x, base, CARD_PILE.z); obj.rotation.y = CARD_PILE.rotY; pile.add(obj); settle(focusable); reg.add(focusable);
      base += pageStack(focusable.item.pages)[0].y + PAPER_T + MIN_GAP;
    });
  }
  if (!model.cards.length && !model.stickies.length) {   // spec §8: an empty desk gets one note
    const note: CardVM = { id: "empty", title: "Nothing on the go", where: "", ink: { hex: "#2d2b29", name: "", variant: 0 }, notes: [], commits: [], started: null };
    const { texture } = textureFor(note, "sticky", 76, 76, "#f4d675");
    const s = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006); s.position.set(-0.05, s.position.y, 0.12); scene.add(s);
  }
}

export function addStickies(scene: THREE.Scene, model: DeskModel, m: M, reg: Registry) {
  const { singles, pile } = stickyLayout(model.stickies.length), slots = stickySlots(8);
  model.stickies.slice(0, singles).forEach((vm, i) => {
    const { obj, focusable } = pageStackItem(m, vm, "sticky", "sticky:" + vm.id, "stickies");
    obj.position.set(slots[i].x, restOn(0), slots[i].z); obj.rotation.y = slots[i].rotY; scene.add(obj); settle(focusable); reg.add(focusable);
  });
  if (pile) {
    const group = new THREE.Group(); group.name = "stickyPile"; scene.add(group);
    reg.add({ item: { id: "stickyPile", group: "stickyPile", pages: 1, turnable: false }, object: group, size: { w: 0.33, h: 0.42 }, normal: FLAT_NORMAL,
      label: `${pile} more`, home: { position: new THREE.Vector3(MAT.x, MAT.t, MAT.z), rotation: new THREE.Euler() } });
    let base = restOn(0);
    model.stickies.slice(singles).forEach((vm, i) => {
      const { obj, focusable } = pageStackItem(m, vm, "sticky", "sticky:" + vm.id, "stickies", "stickyPile");
      obj.position.set(slots[7].x, base, slots[7].z); obj.rotation.y = slots[7].rotY + i * 0.04; group.add(obj); settle(focusable); reg.add(focusable);
      base += pageStack(focusable.item.pages)[0].y + PAPER_T + MIN_GAP;
    });
  }
}

const SHEET = { wMm: 210, hMm: 297, base: 0xf5f0e6 };
/** One done task, typed up on an A4 sheet. */
function renderDoneSheet(c: CardVM, px: number) {
  const canvas = document.createElement("canvas"); canvas.width = SHEET.wMm * px; canvas.height = SHEET.hMm * px; const g = canvas.getContext("2d")!;
  drawPaper(g, canvas.width, canvas.height, "#f5f0e6", "done:" + c.id);
  const sides = layoutSides(doneBlocks(c), canvasMeasure(), { width: SHEET.wMm - 24, height: SHEET.hMm - 36 });
  drawSide(g, sides[0], c.ink.hex, c.id, px, 12, 14);
  const mark = overflowMark(sides.length);
  if (mark) { g.fillStyle = c.ink.hex; g.font = `${5 * px}px 'Caveat'`; g.textAlign = "right"; g.fillText(mark, (SHEET.wMm - 12) * px, (SHEET.hMm - 10) * px); }
  return canvas;
}

/** This week's finished tasks as loose sheets in the tray, newest on top: lifted straight up out of the tray and read in the
 *  hand like a card stack (the top sheet tucked under). */
function doneStack(m: M, done: CardVM[], reg: Registry) {
  const n = done.length, size = { w: SHEET_SIZE.w, d: SHEET_SIZE.d }, slots = pageStack(n), mess = trayStack(n);
  const obj = new THREE.Group(); obj.name = "doneSheets"; obj.position.y = restOn(TRAY.wall);          // never coplanar with the tray floor
  const low = canvasTexture(renderDoneSheet(done[0], LOW_PX)), meshes: THREE.Object3D[] = [], homes: { position: THREE.Vector3; rotation: THREE.Euler }[] = [];
  slots.forEach((s, i) => {
    const j = mess[n - 1 - i];                                                // loose sheets: a little askew
    const page = makePaperCard(size.w, size.d, m.paper(i === 0 ? low : undefined, SHEET.base), m.paper(undefined, SHEET.base), n > 1 ? HIDDEN : m.paper(undefined, SHEET.base));
    page.name = "page" + i; page.position.set(j.jitterX, s.y + PAPER_T / 2, j.jitterZ); page.rotation.y = j.rotY;
    obj.add(page); meshes.push(page); homes.push({ position: page.position.clone(), rotation: page.rotation.clone() });
  });
  let body: THREE.Mesh | undefined;
  if (n > 1) { body = stackBody(m, size.w, size.d, n); setBodyHeight(body, 0, stackBodyHeight(n)); obj.add(body); }
  reg.add({ item: { id: "tray", group: "tray", pages: n, turnable: n > 1, cyclic: n > 1, marks: [...Array(n).keys()] }, object: obj,
    label: `${n} done this week`, size: { w: size.w, h: size.d }, normal: FLAT_NORMAL, held: true, heldRotY: -TRAY.rotY,
    slide: new THREE.Vector3(0, TRAY.h + 0.015, 0),                           // straight up, clear of the tray walls, first
    home: { position: obj.position.clone(), rotation: obj.rotation.clone() },
    pages: { count: n, style: "thumb", meshes, homes, size, low, base: SHEET.base, body, bodyBase: 0, render: (i, px) => renderDoneSheet(done[i], px) } });
  return obj;
}

export function addTray(scene: THREE.Scene, model: DeskModel, m: M, wood: THREE.Material, reg: Registry) {
  const tray = new THREE.Group(); tray.position.set(TRAY.x, 0, TRAY.z); tray.rotation.y = TRAY.rotY; tray.name = "tray";
  const part = (w: number, h: number, d: number, x: number, y: number, z: number) => {
    const p = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wood); p.position.set(x, y, z); p.castShadow = p.receiveShadow = true; tray.add(p); };
  const tp = trayParts();                                   // floor fits between the walls: no shared faces
  part(tp.floor.w, tp.floor.h, tp.floor.d, 0, tp.floor.h / 2, 0);
  part(tp.side.w, tp.side.h, tp.side.d, -(TRAY.w - TRAY.wall) / 2, tp.side.h / 2, 0); part(tp.side.w, tp.side.h, tp.side.d, (TRAY.w - TRAY.wall) / 2, tp.side.h / 2, 0);
  part(tp.back.w, tp.back.h, tp.back.d, 0, tp.back.h / 2, -(TRAY.d - TRAY.wall) / 2);
  if (model.done.length) tray.add(doneStack(m, model.done, reg));
  scene.add(tray);
}
