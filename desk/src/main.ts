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
  const loop = createLoop(() => { focus.tick(performance.now()); composer.render(); }, () => animator.busy || picking.parallaxBusy());
  const focus = createFocus({ camera: createRendererResult.camera, reg, animator, kick: () => loop.kick(), get motion() { return motion(); }, fade,
    parallax: () => picking.parallax() } as Parameters<typeof createFocus>[0]);
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
  (window as any).__deskReadyAt = performance.now();
  (window as any).__deskReady = true;   // browser checks wait on this
}
boot().catch(err => { console.error(err); document.getElementById("loading")!.textContent = "The desk failed to load: " + err.message; });
