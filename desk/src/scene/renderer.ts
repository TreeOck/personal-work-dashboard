import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CAMERA, OVERVIEW } from "./depth";

export function createRenderer(canvas: HTMLCanvasElement) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
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
  const requestRender = () => { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; composer.render(); }); };
  const resize = () => { const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setSize(w, h, false); composer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix(); requestRender(); };
  new ResizeObserver(resize).observe(canvas); resize();
  return { renderer, scene, camera, composer, requestRender };
}
