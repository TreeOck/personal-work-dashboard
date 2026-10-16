import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CAMERA, OVERVIEW } from "./depth";

/** Internal resolution scale while something moves: big canvases drop to about 2 megapixels (never below 0.6), so a moving
 *  frame fits the display's refresh rhythm in Safari (fill-rate bound there). Still frames always render at full resolution. */
export const motionScale = (wPx: number, hPx: number) => { const mp = (wPx * hPx) / 1e6; return mp <= 2 ? 1 : Math.max(0.6, Math.sqrt(2 / mp)); };

export function createRenderer(canvas: HTMLCanvasElement) {
  // no canvas MSAA: the scene is drawn into the composer's own (non-MSAA) targets, so canvas antialiasing only cost fill rate
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance" });
  const base = Math.min(devicePixelRatio, 2);
  renderer.setPixelRatio(base);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;   // r186 removed PCFSoftShadowMap; shadow.radius gives soft edges
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(CAMERA.fov, 1, CAMERA.near, CAMERA.far);
  camera.position.set(...OVERVIEW.position); camera.lookAt(...OVERVIEW.target);
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const gtao = new GTAOPass(scene, camera);
  gtao.updateGtaoMaterial({ radius: 0.08, distanceExponent: 1.4, thickness: 0.6, scale: 1.0 });
  composer.addPass(gtao);
  composer.addPass(new OutputPass());
  let pending = false;
  const requestRender = () => { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; renderer.shadowMap.needsUpdate = true; composer.render(); }); };
  const resize = () => { const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setSize(w, h, false); composer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix(); requestRender(); };
  new ResizeObserver(resize).observe(canvas); resize();
  let moving = false;
  /** Switch to the lower motion resolution while things move, and back to full for the still frame. */
  const setMoving = (on: boolean) => {
    if (on === moving) return; moving = on;
    const w = canvas.clientWidth, h = canvas.clientHeight, pr = on ? base * motionScale(w * base, h * base) : base;
    if (pr === renderer.getPixelRatio()) return;
    renderer.setPixelRatio(pr); renderer.setSize(w, h, false); composer.setPixelRatio(pr); composer.setSize(w, h);
  };
  return { renderer, scene, camera, composer, requestRender, setMoving };
}
