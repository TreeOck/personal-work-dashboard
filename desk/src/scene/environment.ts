import * as THREE from "three";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { ASSETS } from "../assets";

export async function loadEnvironment(renderer: THREE.WebGLRenderer, scene: THREE.Scene, which: "day" | "evening") {
  const tex = await new HDRLoader().loadAsync(which === "day" ? ASSETS.hdri.day : ASSETS.hdri.evening);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(tex).texture;
  scene.background = tex; scene.backgroundBlurriness = 0.55; scene.backgroundIntensity = 0.8; scene.environmentIntensity = 1.0;
  pmrem.dispose();
  // Plan 1 daylight key: window sun through the blinds direction.
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(1.4, 1.6, 0.6); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 10; sun.shadow.bias = -0.0002;
  Object.assign(sun.shadow.camera, { left: -1, right: 1, top: 1, bottom: -1, near: 0.1, far: 5 });
  scene.add(sun);
}
