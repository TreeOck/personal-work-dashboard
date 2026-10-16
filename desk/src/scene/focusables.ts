import * as THREE from "three";
import type { Action, Item } from "../camera/director";
import type { V3 } from "../camera/shots";

/** The physical pages of a focusable thing: a clipped card stack you thumb through ("thumb"), or pages hinged at the top
 *  that flip over (a sticky pad in your hand, the notepad on the desk: "flip"). */
export interface Pages {
  count: number; style: "thumb" | "flip";
  meshes: THREE.Object3D[];                                    // index 0 = top page; each contains a "front" plane
  homes: { position: THREE.Vector3; rotation: THREE.Euler }[];
  size: { w: number; d: number };
  flip?: { root0: number; far0: number; q: number; L: number }; // flip only: where flipped pages lie (see reading.ts padFlip)
  pose?: (k: number, p: number) => void;                       // flip only: the object places page k at progress p itself (calendar)
  block?: boolean;                                             // several turns in a row go over together, as one block (binders)
  show?: (open: boolean) => void;                              // binders: draw the leaves only while open
  low: THREE.Texture;                                          // top page at overview resolution
  base: number;                                                // the paper colour (cream card, yellow sticky, pad cream)
  body?: THREE.Mesh; bodyBase: number;                         // solid side walls around the pages still in the stack (multi-page only)
  render(i: number, pxPerMm: number): HTMLCanvasElement;
}

export interface Focusable {
  item: Item;
  object: THREE.Object3D;
  size: { w: number; h: number };
  normal: V3;
  label: string;
  pages?: Pages;
  home: { position: THREE.Vector3; rotation: THREE.Euler };   // where it was laid out
  rest: { position: THREE.Vector3; rotation: THREE.Euler };   // where it lies now (a fanned pile member rests in its fan slot)
  held?: boolean;                                             // picked up to be read (cards, stickies); else read where it lies
  clip?: { mesh: THREE.Object3D; y: number };                 // paper clip on a multi-card stack; y = its height above the stack base
  heldAt?: THREE.Vector3; heldRotY?: number; heldShot?: THREE.Vector3;   // where it is held, turned how, and where to look (default HELD)
  link?: (top: number) => Action;                              // clicking it while reading goes elsewhere (calendar -> Day binder)
  slide?: THREE.Vector3;                                       // slid out this far before lifting (a binder from a stack)
  rack?: { take(id: string): string[]; put(id: string): void };   // binders: rests change as one is taken out and put back
}
type Pose = Focusable["home"];
const copy = (p: Pose): Pose => ({ position: p.position.clone(), rotation: p.rotation.clone() });

export class Registry {
  private byId = new Map<string, Focusable>();
  private byObject = new Map<THREE.Object3D, Focusable>();
  add(g: Omit<Focusable, "rest"> & { rest?: Pose }) { const f = { ...g, rest: g.rest ?? copy(g.home) }; this.byId.set(f.item.id, f); this.byObject.set(f.object, f); }
  get(id: string) { return this.byId.get(id); }
  items(): Item[] { return [...this.byId.values()].map(f => f.item); }
  all(): Focusable[] { return [...this.byId.values()]; }
  ofObject(o: THREE.Object3D | null): Focusable | undefined {
    for (let n: THREE.Object3D | null = o; n; n = n.parent) { const f = this.byObject.get(n); if (f) return f; }
    return undefined;
  }
}
