import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { restOn } from "./depth";

export function loadModel(spec: { gltf: string; files: Record<string, string> }): Promise<THREE.Group> {
  const manager = new THREE.LoadingManager();
  manager.setURLModifier(url => { const key = Object.keys(spec.files).find(k => url.endsWith(k)); return key ? spec.files[key] : url; });
  return new Promise((resolve, reject) => new GLTFLoader(manager).parse(spec.gltf, "", g => {
    g.scene.traverse(n => { if ((n as THREE.Mesh).isMesh) n.castShadow = n.receiveShadow = true; });
    resolve(g.scene);
  }, reject));
}

/** Rest an object on the desk at (x, z). By default its lowest point rests on the desk; pass `baseY` (model-space height of
 *  its real base) for models with parts meant to go into the desk, e.g. the lamp's mounting peg. */
export function placeOnDesk(obj: THREE.Object3D, x: number, z: number, rotY = 0, opts: { baseY?: number } = {}) {
  obj.position.set(x, 0, z); obj.rotation.y = rotY; obj.updateMatrixWorld(true);
  if (opts.baseY !== undefined) { obj.position.y = restOn(0) - opts.baseY * obj.scale.y; return; }
  const box = new THREE.Box3().setFromObject(obj); obj.position.y += restOn(0) - box.min.y;   // never coplanar with the desk
}
