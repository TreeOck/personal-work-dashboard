import * as THREE from "three";
import { ASSETS } from "../assets";

/** `onTextureLoaded` re-renders when an image finishes decoding: with render-on-demand, a texture that lands after
 *  the boot frame would otherwise stay invisible until something else moved (review M5). */
export function materials(renderer: THREE.WebGLRenderer, onTextureLoaded: () => void = () => {}) {
  const aniso = renderer.capabilities.getMaxAnisotropy();
  const tl = new THREE.TextureLoader();
  const tex = (url: string, srgb: boolean, rx: number, ry: number) => { const t = tl.load(url, onTextureLoaded); if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); t.anisotropy = aniso; return t; };
  const walnut = new THREE.MeshPhysicalMaterial({ map: tex(ASSETS.walnut.map, true, 1.6, 0.8), normalMap: tex(ASSETS.walnut.normal, false, 1.6, 0.8),
    roughnessMap: tex(ASSETS.walnut.rough, false, 1.6, 0.8), roughness: 1, clearcoat: 0.6, clearcoatRoughness: 0.18 });
  const leather = new THREE.MeshPhysicalMaterial({ map: tex(ASSETS.leather.map, true, 1.5, 0.75), normalMap: tex(ASSETS.leather.normal, false, 1.5, 0.75),
    roughnessMap: tex(ASSETS.leather.rough, false, 1.5, 0.75), sheen: 0.4, sheenRoughness: 0.6, sheenColor: new THREE.Color(0x6b4a33) });
  const fibre = fibreNormal();
  const paper = (map?: THREE.Texture, color = 0xefe8da) => new THREE.MeshPhysicalMaterial({ map: map ?? null, color: map ? 0xffffff : color,
    roughness: 0.92, normalMap: fibre, normalScale: new THREE.Vector2(0.35, 0.35), sheen: 0.25, sheenRoughness: 0.9,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
  const brass = new THREE.MeshPhysicalMaterial({ color: 0xc9a46a, metalness: 1, roughness: 0.32, anisotropy: 0.7, clearcoat: 0.2, side: THREE.DoubleSide });
  const penBody = (hex: string) => new THREE.MeshPhysicalMaterial({ color: hex, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.08 });
  return { walnut, leather, paper, brass, penBody };
}

function fibreNormal(): THREE.Texture {
  const c = document.createElement("canvas"); c.width = c.height = 512; const g = c.getContext("2d")!;
  g.fillStyle = "rgb(128,128,255)"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) { const x = Math.random() * 512, y = Math.random() * 512, a = Math.random() * Math.PI, l = 3 + Math.random() * 14;
    g.strokeStyle = `rgba(${110 + Math.random() * 40},${110 + Math.random() * 40},255,0.35)`; g.lineWidth = 0.6;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
