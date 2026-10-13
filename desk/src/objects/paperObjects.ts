import * as THREE from "three";
import type { CardVM, DeskModel } from "../data/model";
import { cardBlocks, layoutSides, overflowMark } from "../paper/layout";
import { canvasMeasure, drawPaper, drawSide } from "../paper/render";
import { CARD_SIZE, PAPER_T, SHEET_SIZE, STICKY_SIZE, TRAY } from "../scene/layout";
import type { materials } from "../scene/materials";
import { cardSlots, stackBlockHeight, stickySlots, trayParts, trayStack } from "./slots";

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

export function addCards(scene: THREE.Scene, model: DeskModel, m: M, matTop: number) {
  cardSlots(model.cards.length).forEach((s, i) => {
    const { texture } = textureFor(model.cards[i], "card", CARD_SIZE.w * 1000, CARD_SIZE.d * 1000, "#f1ebde");
    const card = sheet(m, CARD_SIZE.w, CARD_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006);
    card.position.x = s.x; card.position.z = s.z; card.rotation.y = s.rotY; card.name = "card:" + model.cards[i].id; scene.add(card);
  });
  if (!model.cards.length && !model.stickies.length) {   // spec §8: an empty desk gets one note
    const note: CardVM = { id: "empty", title: "Nothing on the go", where: "", ink: { hex: "#2d2b29", name: "", variant: 0 }, notes: [], commits: [], started: null };
    const { texture } = textureFor(note, "sticky", 76, 76, "#f4d675");
    const s = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006); s.position.set(-0.05, s.position.y, 0.12); scene.add(s);
  }
}

export function addStickies(scene: THREE.Scene, model: DeskModel, m: M) {
  stickySlots(model.stickies.length).forEach((s, i) => {
    const { texture } = textureFor(model.stickies[i], "sticky", STICKY_SIZE.w * 1000, STICKY_SIZE.d * 1000, "#f4d675");
    const note = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, PAPER_T / 2 + 0.0006);
    note.position.x = s.x; note.position.z = s.z; note.rotation.y = s.rotY; note.name = "sticky:" + model.stickies[i].id; scene.add(note);
  });
}

export function addTray(scene: THREE.Scene, model: DeskModel, m: M, wood: THREE.Material) {
  const tray = new THREE.Group(); tray.position.set(TRAY.x, 0, TRAY.z); tray.rotation.y = TRAY.rotY; tray.name = "tray";
  const part = (w: number, h: number, d: number, x: number, y: number, z: number) => {
    const p = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wood); p.position.set(x, y, z); p.castShadow = p.receiveShadow = true; tray.add(p); };
  const tp = trayParts();                                   // floor fits between the walls: no shared faces
  part(tp.floor.w, tp.floor.h, tp.floor.d, 0, tp.floor.h / 2, 0);
  part(tp.side.w, tp.side.h, tp.side.d, -(TRAY.w - TRAY.wall) / 2, tp.side.h / 2, 0); part(tp.side.w, tp.side.h, tp.side.d, (TRAY.w - TRAY.wall) / 2, tp.side.h / 2, 0);
  part(tp.back.w, tp.back.h, tp.back.d, 0, tp.back.h / 2, -(TRAY.d - TRAY.wall) / 2);
  const stack = trayStack(model.done.length);
  if (stack.length) {
    const below = stack.length - 1;                        // all but the top sheet become one block
    if (below) { const blk = stackBlock(m, SHEET_SIZE.w, SHEET_SIZE.d, stackBlockHeight(below), below);
      blk.position.set(0, stack[0].y + stackBlockHeight(below) / 2, 0); tray.add(blk); }
    const t = stack[stack.length - 1];
    const tex = textureFor(model.done[0], "sheet", SHEET_SIZE.w * 1000, SHEET_SIZE.d * 1000, "#f5f0e6").texture;
    const sh = sheet(m, SHEET_SIZE.w, SHEET_SIZE.d, tex, t.y + PAPER_T / 2);
    sh.position.x = t.jitterX; sh.position.z = t.jitterZ; sh.rotation.y = t.rotY; tray.add(sh);
  }
  scene.add(tray);
}
