import * as THREE from "three";
import { ASSETS } from "./assets";
import { readData, type DeskData } from "./data/types";
import { buildModel } from "./data/model";
import { loadFonts } from "./paper/render";
import { createRenderer } from "./scene/renderer";
import { loadEnvironment } from "./scene/environment";
import { materials } from "./scene/materials";
import { loadModel, placeOnDesk } from "./scene/models";
import { DESK, MAT, LAMP, PLANT } from "./scene/layout";
import { buildObjects } from "./objects";
import { Animator } from "./anim/animator";
import { createFocus } from "./interaction/focus";
import { createPicking } from "./interaction/picking";
import { keyToAction, motionFactor } from "./interaction/input";
import { createLoop } from "./scene/loop";

async function getData(): Promise<DeskData> {
  return readData() ?? (await (await fetch("/dev-data.json")).json());    // dev server fallback
}

function webglOK(): boolean {
  try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
}

async function boot() {
  const canvas = document.getElementById("desk") as HTMLCanvasElement;
  if (!webglOK()) { document.getElementById("loading")!.remove(); (document.getElementById("fallback")!).style.display = "grid"; return; }
  const [data] = await Promise.all([getData(), loadFonts(ASSETS.fonts.caveat, ASSETS.fonts.specialElite)]);
  const model = buildModel(data, new Date());
  const createRendererResult = createRenderer(canvas);
  const { renderer, scene, composer } = createRendererResult;
  let renderCount = 0;
  const origRender = composer.render.bind(composer);
  composer.render = (dt?: number) => { renderCount++; origRender(dt); };
  const requestRender = createRendererResult.requestRender;
  canvas.addEventListener("webglcontextlost", e => { e.preventDefault(); });
  canvas.addEventListener("webglcontextrestored", () => location.reload());
  const m = materials(renderer, requestRender);

  const desk = new THREE.Mesh(new THREE.BoxGeometry(DESK.w, DESK.h, DESK.d), m.walnut);
  desk.position.y = -DESK.h / 2; desk.receiveShadow = true; scene.add(desk);
  const mat = new THREE.Mesh(new THREE.BoxGeometry(MAT.w, MAT.t, MAT.d), m.leather);
  mat.position.set(MAT.x, MAT.t / 2, MAT.z); mat.receiveShadow = mat.castShadow = true; scene.add(mat);

  const [lamp, plant] = await Promise.all([loadModel(ASSETS.models.lamp), loadModel(ASSETS.models.plant), loadEnvironment(renderer, scene, "day")]);
  placeOnDesk(lamp, LAMP.x, LAMP.z, LAMP.rotY, { baseY: 0 }); scene.add(lamp);   // its mounting peg goes into the desk
  plant.scale.setScalar(PLANT.scale); placeOnDesk(plant, PLANT.x, PLANT.z); scene.add(plant);

  const reg = buildObjects(scene, model, m, MAT.t);
  const animator = new Animator();
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const motion = () => motionFactor(reduceMotion.matches);
  const fade = () => { canvas.style.opacity = "0.25"; requestAnimationFrame(() => requestAnimationFrame(() => { canvas.style.opacity = "1"; })); };
  let picking: ReturnType<typeof createPicking>;
  // shadows only change when something other than the camera moves: skip re-rendering the shadow map for camera-only frames
  renderer.shadowMap.autoUpdate = false; renderer.shadowMap.needsUpdate = true;
  let objectsMoved = true;
  const loop = createLoop(() => {
    const moving = animator.movingObjects(); if (moving || objectsMoved) renderer.shadowMap.needsUpdate = true; objectsMoved = moving;
    const more = focus.tick(performance.now());
    createRendererResult.setMoving(more);                          // lower resolution while moving, full for the still frame
    composer.render(); }, () => animator.busy || picking.parallaxBusy());
  const focus = createFocus({ camera: createRendererResult.camera, reg, animator, kick: () => loop.kick(), get motion() { return motion(); }, fade,
    parallax: () => picking.parallax(), upload: t => renderer.initTexture(t), canvasHeight: () => renderer.domElement.height } as Parameters<typeof createFocus>[0]);
  picking = createPicking({ canvas, camera: createRendererResult.camera, scene, reg, dispatch: a => focus.dispatch(a), stack: focus.stack, linkOf: id => focus.linkOf(id), hover: id => focus.hover(id),
    kick: () => loop.kick(), get motion() { return motion(); }, label: document.getElementById("tag")! } as Parameters<typeof createPicking>[0]);
  canvas.addEventListener("pointermove", e => picking.onPointerMove(e));
  canvas.addEventListener("pointerdown", e => picking.onPointerDown(e));
  canvas.addEventListener("pointerup", e => picking.onPointerUp(e));
  canvas.addEventListener("pointerleave", () => picking.onPointerLeave());
  canvas.addEventListener("contextmenu", e => e.preventDefault());               // right-click = back (handled on pointerup)
  addEventListener("keydown", e => { if (e.metaKey || e.ctrlKey || e.altKey) return; const a = keyToAction(e.key, e.shiftKey);
    if (a) { e.preventDefault(); focus.dispatch(a); } });
  new ResizeObserver(() => focus.onResize()).observe(canvas);
  loop.kick();
  const loading = document.getElementById("loading")!;
  loading.style.opacity = "0"; setTimeout(() => loading.remove(), 700);
  // handle for automated browser checks (flicker sweep, idle render count); harmless for normal use
  (window as any).__desk = { scene, renderer, camera: createRendererResult.camera, requestRender, renders: () => renderCount, focus,
    busy: () => ({ animator: animator.busy, keys: [...((animator as any).anims as Map<string, unknown>).keys()], parallax: picking.parallaxBusy(), par: picking.debug() }) };
  // timing probe for performance work: frame cost with/without each expensive piece, and hi-res page texture cost
  (window as any).__desk.bench = (n = 20) => {
    const gl = renderer.getContext(), px = new Uint8Array(4), sync = () => gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
    const t = (f: () => void) => { f(); sync(); const a = performance.now(); for (let i = 0; i < n; i++) { f(); sync(); } return +((performance.now() - a) / n).toFixed(2); };
    const passes = (composer as any).passes as { enabled: boolean; constructor: { name: string } }[], ao = passes.find(p => p.constructor.name === "GTAOPass");
    const withShadows = () => { renderer.shadowMap.needsUpdate = true; origRender(); };   // a frame where objects move
    const full = t(withShadows);
    if (ao) ao.enabled = false; const noAO = t(withShadows); if (ao) ao.enabled = true;
    const noShadowUpdate = t(() => origRender());                                       // a camera-only frame
    renderer.info.autoReset = false; renderer.info.reset(); withShadows(); const calls = renderer.info.render.calls, tris = renderer.info.render.triangles; renderer.info.autoReset = true;
    const W = renderer.domElement.clientWidth, Hh = renderer.domElement.clientHeight;
    composer.setSize(W / 2, Hh / 2); renderer.setSize(W / 2, Hh / 2, false); const halfRes = t(withShadows);
    renderer.setSize(W, Hh, false); composer.setSize(W, Hh);
    const tex = (w: number, h: number) => { const c = document.createElement("canvas"); c.width = w; c.height = h; const g = c.getContext("2d")!;
      let a = performance.now(); g.fillStyle = "#eee"; g.fillRect(0, 0, w, h); g.font = `${Math.round(w / 60)}px serif`; g.fillStyle = "#222";
      for (let i = 0; i < 60; i++) g.fillText("Typed line of the weekly report, a few more words here", w * 0.05, (i + 1) * h / 62);
      const draw = performance.now() - a; const x = new THREE.CanvasTexture(c); a = performance.now(); renderer.initTexture(x); sync();
      const upload = performance.now() - a; x.dispose(); return { draw: +draw.toFixed(1), upload: +upload.toFixed(1), mpx: +(w * h / 1e6).toFixed(1) }; };
    return { dpr: renderer.getPixelRatio(), canvas: [renderer.domElement.width, renderer.domElement.height], full, noAO, noShadowUpdate,
      calls, tris, halfRes, leaf24: tex(5040, 7128), leaf12: tex(2520, 3564), card24: tex(3552, 2520), card12: tex(1776, 1260) };
  };
  // ?bench: measure, then report through the tab title (readable from outside the browser, e.g. for Safari)
  (window as any).__desk.animBench = async () => {
    const gaps: number[] = []; let last = 0, on = true;
    const tick = (t: number) => { if (last) gaps.push(t - last); last = t; if (on) requestAnimationFrame(tick); }; requestAnimationFrame(tick);
    const wait = (ms: number) => new Promise(r => setTimeout(r, ms)), act = (a: object) => focus.dispatch(a as never);
    for (const a of [{ type: "key", key: "1" }, { type: "turn", dir: 1 }, { type: "back" }, { type: "select", id: "binder:day" }, { type: "turn", dir: -1 },
      { type: "back" }, { type: "key", key: "5" }, { type: "turn", dir: 1 }, { type: "back" }]) { act(a); await wait(1300); }
    on = false; const s = [...gaps].sort((x, y) => x - y), q = (f: number) => +s[Math.floor(f * (s.length - 1))].toFixed(1);
    const idle: number[] = []; let l2 = 0; await new Promise<void>(res => { const f = (t: number) => { if (l2) idle.push(t - l2); l2 = t; if (idle.length < 60) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
    const hist = [8, 12, 17, 25, 34, 1e9].map((lim, i, a) => gaps.filter(g => g <= lim && g > (a[i - 1] ?? 0)).length);
    return { frames: gaps.length, median: q(0.5), p95: q(0.95), worst: +s[s.length - 1].toFixed(1), over33: gaps.filter(g => g > 33).length,
      idleRaf: +(idle.reduce((a, b) => a + b, 0) / idle.length).toFixed(2), hist_le8_12_17_25_34_more: hist };
  };
  if (location.search.includes("bench")) setTimeout(async () => {
    const b = (window as any).__desk.bench(10), a = await (window as any).__desk.animBench();
    document.title = "BENCH " + JSON.stringify({ ua: navigator.userAgent.includes("Chrome") ? "chrome" : "safari", ...b, anim: a });
  }, 2500);
  (window as any).__deskReadyAt = performance.now();
  (window as any).__deskReady = true;   // browser checks wait on this
}
boot().catch(err => { console.error(err); document.getElementById("loading")!.textContent = "The desk failed to load: " + err.message; });
