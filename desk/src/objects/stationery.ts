import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { drawPaper } from "../paper/render";
import { BINDER, CALENDAR, NOTEPAD, PAPER_T } from "../scene/layout";
import type { materials } from "../scene/materials";
import { binderBases, notepadSheets, stackBlockHeight } from "./slots";
import { stackBlock } from "./paperObjects";

type M = ReturnType<typeof materials>;
const canvasTex = (w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) => {
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d")!);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

export function addCalendar(scene: THREE.Scene, model: DeskModel, m: M) {
  const face = canvasTex(520, 440, g => { drawPaper(g, 520, 440, "#ece5d6", "cal");
    g.fillStyle = "#7a1414"; g.font = "44px 'Special Elite'"; g.textAlign = "center"; g.fillText(model.today.monthName, 260, 90);
    g.fillStyle = "#231a14"; g.font = "bold 210px Georgia, serif"; g.fillText(String(model.today.day), 260, 300);
    g.font = "40px 'Caveat'"; g.fillText(model.today.weekday, 260, 380); });
  const easel = new THREE.Mesh(new THREE.BoxGeometry(CALENDAR.w, CALENDAR.h, 0.004), [m.paper(), m.paper(), m.paper(), m.paper(), m.paper(face), m.paper()]);
  easel.position.set(CALENDAR.x, CALENDAR.h / 2 * Math.cos(0.3), CALENDAR.z); easel.rotation.x = -0.3; easel.castShadow = true; easel.name = "calendar";
  scene.add(easel);
}

export function addNotepad(scene: THREE.Scene, model: DeskModel, m: M) {
  const face = canvasTex(400, 560, g => { drawPaper(g, 400, 560, "#f6efe0", "pad");
    g.strokeStyle = "rgba(110,140,190,.45)"; for (let y = 120; y < 540; y += 52) { g.beginPath(); g.moveTo(24, y); g.lineTo(376, y); g.stroke(); }
    g.fillStyle = "#2d2b29"; g.font = "40px 'Caveat'";
    g.fillText("This week", 30, 100); g.fillText(`commits   ${model.week.commits}`, 30, 164);
    g.fillText(`tasks     ${model.week.tasks}`, 30, 216); g.fillText(`active days  ${model.week.activeDays}`, 30, 268); });
  const pad = new THREE.Group(); pad.name = "notepad";
  const ys = notepadSheets(12), below = stackBlockHeight(11);    // 11 sheets as one block, the written top sheet on it
  const blk = stackBlock(m, NOTEPAD.w, NOTEPAD.d, below, 11); blk.position.y = ys[0] + below / 2; pad.add(blk);
  const top = new THREE.Mesh(new THREE.BoxGeometry(NOTEPAD.w, PAPER_T, NOTEPAD.d), [m.paper(), m.paper(), m.paper(face), m.paper(), m.paper(), m.paper()]);
  top.position.y = ys[11] + PAPER_T / 2; top.castShadow = top.receiveShadow = true; pad.add(top);
  pad.position.set(NOTEPAD.x, 0, NOTEPAD.z); pad.rotation.y = -0.35; scene.add(pad);
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
