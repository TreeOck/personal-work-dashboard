import * as THREE from "three";
import { Animator } from "../anim/animator";
import { reduce, START, top, type Action, type Frame, type Stack } from "../camera/director";
import { FLAT_NORMAL, focusShot, type Shot, type V3 } from "../camera/shots";
import { fanSlots, stackBodyHeight } from "../objects/slots";
import { setBodyHeight } from "../objects/paperObjects";
import { CAMERA, MAT, MIN_GAP, OVERVIEW } from "../scene/layout";
import type { Focusable, Registry } from "../scene/focusables";
import { padFlip, pageQuality, stepsTo, TextureLedger, thumbPose, type Quality } from "./reading";

// Channels: "camera"; "pose:<id>" moves a whole object (hover, fan, pick up, put down: one channel, so the newest move wins);
// "stack:<id>" is the one page move in progress on that object; "clip:<id>" its paper clip.
const HI_PX = 24, LOW_PX = 6, CAM_MS = 750, LIFT_MS = 700, TURN_MS = 560, QUICK_MS = 220, CLIP_MS = 280, FAN_MS = 600,
  HOVER_LIFT = 0.003, HOVER_MS = 140;
/** Where you hold a stack to read it: over the middle of the mat, 10 cm up, squared to you. */
export const HELD = new THREE.Vector3(MAT.x, MAT.t + 0.1, MAT.z);
const CLIP_OFF = new THREE.Vector3(0, 0.015, -0.035);           // clip lifted off and held clear behind the stack

/** One readable object: which page is on top, the single moves still to make, and whether it is wanted in the hand. */
interface Reader { f: Focusable; top: number; moving: 0 | 1 | -1; queue: (1 | -1)[]; want: boolean; pose: "rest" | "held";
  busy: boolean; tex: TextureLedger<THREE.Texture>; q: Quality[]; holder?: THREE.Group; clipDrop: number }

interface Ctx { camera: THREE.PerspectiveCamera; reg: Registry; animator: Animator; kick: () => void; motion: number;
  fade: () => void; parallax: () => THREE.Vector3 }

export function createFocus(ctx: Ctx) {
  const { camera, reg, animator } = ctx;
  let stack: Stack = START, hand: string | null = null, hovered: string | undefined;
  const camPos = new THREE.Vector3(...OVERVIEW.position), camTarget = new THREE.Vector3(...OVERVIEW.target);
  const now = () => performance.now(), ms = (d: number) => d * ctx.motion;
  const readers = new Map<string, Reader>();
  for (const f of reg.all()) if (f.item.group !== "cardPile" && f.item.group !== "stickyPile")
    readers.set(f.item.id, { f, top: 0, moving: 0, queue: [], want: false, pose: "rest", busy: false, tex: new TextureLedger(),
      q: f.pages ? f.pages.meshes.map((_, i) => (i === 0 ? "low" : "none")) : [], clipDrop: 0 });

  /** Page i's printed face at quality q. The text never changes: the same page, re-rendered sharper or blurrier. */
  function setFace(r: Reader, i: number, q: Quality) {
    const pages = r.f.pages!; if (r.q[i] === q) return;
    const mat = (pages.meshes[i].getObjectByName("front") as THREE.Mesh).material as THREE.MeshPhysicalMaterial;
    let t: THREE.Texture | null = null;
    if (q === "hi" || (q === "low" && i !== 0)) {
      t = new THREE.CanvasTexture(pages.render(i, q === "hi" ? HI_PX : LOW_PX)); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = q === "hi" ? 16 : 8;
    }
    mat.map = q === "none" ? null : t ?? pages.low;               // page 0's small texture is shared and never disposed
    r.tex.set(i, t);
    mat.color.set(mat.map ? 0xffffff : pages.base); mat.needsUpdate = true; r.q[i] = q;
  }
  const faces = (r: Reader) => r.f.pages?.meshes.forEach((_, i) => setFace(r, i, pageQuality(i, r.top, r.want)));

  // ---- where things go -------------------------------------------------------------------------------------------
  const restOf = (r: Reader) => r.f.rest;
  const heldLocal = (r: Reader) => r.f.object.parent!.worldToLocal((r.f.heldAt ?? HELD).clone());
  function shotFor(frame: Frame): Shot {
    if (frame.kind === "overview") return { position: [...OVERVIEW.position], target: [...OVERVIEW.target] };
    if (frame.kind === "fan") { const f = reg.get(frame.pile)!; const c = f.home.position;
      return focusShot([c.x, c.y + 0.02, c.z], FLAT_NORMAL, f.size, CAMERA.fov, camera.aspect, 0.9); }
    const f = reg.get(frame.id)!;                                    // from where it will be, never from mid-move
    const c = f.held ? (f.heldShot ?? f.heldAt ?? HELD).clone() : f.object.parent!.localToWorld(f.rest.position.clone());
    return focusShot([c.x, c.y, c.z] as V3, f.normal, f.size, CAMERA.fov, camera.aspect);
  }
  function moveCamera(shot: Shot) {
    const fromP = camPos.clone(), fromT = camTarget.clone(), toP = new THREE.Vector3(...shot.position), toT = new THREE.Vector3(...shot.target);
    const arc = fromP.distanceTo(toP) * 0.12;
    if (ctx.motion === 0) ctx.fade();
    animator.play("camera", ms(CAM_MS), p => { camPos.lerpVectors(fromP, toP, p); camPos.y += Math.sin(p * Math.PI) * arc; camTarget.lerpVectors(fromT, toT, p); }, now());
  }

  /** Ease an object to its rest pose (plus the hover lift if the pointer is on it). */
  function settle(r: Reader, delay = 0) {
    const o = r.f.object, to = restOf(r).position.clone(), toRy = restOf(r).rotation.y;
    if (hovered === r.f.item.id && !r.want) to.y += HOVER_LIFT;
    if (o.position.distanceTo(to) < 1e-7 && Math.abs(o.rotation.y - toRy) < 1e-7) return;
    const from = o.position.clone(), fromRy = o.rotation.y, far = from.distanceTo(to) > 0.01;
    animator.play("pose:" + r.f.item.id, ms(far ? FAN_MS : HOVER_MS), p => { o.position.lerpVectors(from, to, p); o.rotation.y = fromRy + (toRy - fromRy) * p; }, now() + delay);
  }

  // ---- the clip ------------------------------------------------------------------------------------------------------
  /** Tween the clip (in its holder's space) from wherever it is now to `to` (identity rotation). */
  function clipTo(r: Reader, to: THREE.Vector3, delay: number, done?: () => void) {
    const c = r.f.clip!.mesh, from = c.position.clone(), fromQ = c.quaternion.clone(), id = new THREE.Quaternion();
    animator.play("clip:" + r.f.item.id, ms(CLIP_MS), p => { c.position.lerpVectors(from, to, p); c.quaternion.slerpQuaternions(fromQ, id, p); }, now() + ms(delay), { done });
  }
  /** A holder for the clip where the stack rests (the clip stays behind on the mat while the stack is in your hand). */
  function holderAt(r: Reader, pose: { position: THREE.Vector3; rotation: THREE.Euler }) {
    const parent = r.f.object.parent!, c = r.f.clip!.mesh;
    r.holder ??= Object.assign(new THREE.Group(), { name: "clipHolder:" + r.f.item.id });
    if (c.parent) parent.attach(c);                                 // keep the clip where it is in the world
    r.holder.position.copy(pose.position); r.holder.rotation.copy(pose.rotation); parent.add(r.holder); r.holder.updateMatrixWorld(true);
    r.holder.attach(c);
    const world = r.holder.localToWorld(new THREE.Vector3());
    r.clipDrop = MAT.t + MIN_GAP + 0.0006 - world.y - r.f.clip!.y;   // lying on the mat (0.6 mm wire) where the stack was
  }

  // ---- whole-object moves -------------------------------------------------------------------------------------------
  function pickUp(r: Reader) {
    r.busy = true; hand = r.f.item.id;
    const o = r.f.object, toRy = r.f.heldRotY ?? 0, lift = () => {
      const s = (t: number) => { const x = Math.min(1, Math.max(0, t)); return x * x * (3 - 2 * x); };
      const start = o.position.clone(), out = r.f.slide ? start.clone().add(r.f.slide) : start, k = r.f.slide ? 0.35 : 0;   // slide out first
      const fromRy = o.rotation.y, to = heldLocal(r);
      const above = r.f.rack?.take(r.f.item.id) ?? [];                // the binders on top of it drop once it is clear
      above.forEach(id => { const w = readers.get(id); if (w && !w.busy && w.pose === "rest") settle(w, ms(LIFT_MS) * (k + 0.05)); });
      r.f.pages?.show?.(true);
      animator.play("pose:" + r.f.item.id, ms(LIFT_MS * (1 + k)), p0 => {
        if (p0 < k / (1 + k)) { o.position.lerpVectors(start, out, s(p0 * (1 + k) / k)); return; }
        const p = (p0 - k / (1 + k)) * (1 + k);                       // then straight up, then across to you
        o.position.set(out.x + (to.x - out.x) * s((p - 0.2) / 0.8), out.y + (to.y - out.y) * s(p / 0.5), out.z + (to.z - out.z) * s((p - 0.2) / 0.8));
        o.rotation.y = fromRy + (toRy - fromRy) * s((p - 0.2) / 0.8);
      }, now(), { done: () => { r.pose = "held"; r.busy = false; pump(r); } });
      if (r.f.clip) clipTo(r, new THREE.Vector3(0, r.clipDrop, 0), LIFT_MS * 0.45);   // once the stack is clear, set the clip down
    };
    faces(r);
    if (!r.f.clip) return lift();
    holderAt(r, { position: o.position, rotation: o.rotation });
    clipTo(r, CLIP_OFF, 0, lift);                                    // take the clip off first
  }

  function putDown(r: Reader) {
    r.busy = true;
    r.f.rack?.put(r.f.item.id);                                       // a binder goes back on top of the stack
    const o = r.f.object, rest = restOf(r), from = o.position.clone(), to = rest.position.clone(), toRy = rest.rotation.y, fromRy = o.rotation.y;
    const s = (t: number) => { const x = Math.min(1, Math.max(0, t)); return x * x * (3 - 2 * x); };
    if (r.f.clip) { holderAt(r, rest); clipTo(r, CLIP_OFF, 0); }      // lift the clip off the spot before the stack lands
    animator.play("pose:" + r.f.item.id, ms(LIFT_MS), p => {         // across first, then straight down
      o.position.set(from.x + (to.x - from.x) * s(p / 0.8), from.y + (to.y - from.y) * s((p - 0.5) / 0.5), from.z + (to.z - from.z) * s(p / 0.8));
      o.rotation.y = fromRy + (toRy - fromRy) * s(p / 0.8);
    }, now(), { done: () => {
      const landed = () => { r.pose = "rest"; r.busy = false; hand = null; r.f.pages?.show?.(false); faces(r); pump(r); for (const w of readers.values()) if (w !== r) pump(w); };
      if (!r.f.clip) return landed();
      clipTo(r, new THREE.Vector3(), 0, () => { o.add(r.f.clip!.mesh); r.f.clip!.mesh.position.set(0, 0, 0); r.f.clip!.mesh.quaternion.identity(); landed(); });
    } });
  }

  // ---- page moves -------------------------------------------------------------------------------------------------------
  function move(r: Reader, dir: 1 | -1) {
    const pages = r.f.pages!, n = pages.count, id = r.f.item.id, dur = ms(r.queue.length ? QUICK_MS : TURN_MS);
    r.busy = true; r.moving = dir;
    const done = () => { r.top = next; r.moving = 0; r.busy = false; faces(r); pump(r); };
    let next: number;
    if (pages.style === "thumb") {
      next = (r.top + dir + n) % n;
      setFace(r, next, r.want ? "hi" : "low");                       // the card coming to the top has its face before it moves
      animator.play("stack:" + id, dur, p => {
        const { cards, body } = thumbPose(n, dir, p, pages.size.d);
        cards.forEach((c, j) => { const i = (r.top + j) % n, h = pages.homes[i].position; pages.meshes[i].position.set(h.x, c.y, h.z + c.z); });
        if (pages.body) setBodyHeight(pages.body, pages.bodyBase + body.base, body.h);
      }, now(), { done });
    } else {
      let m = 1; if (pages.block) while (r.queue[0] === dir) { r.queue.shift(); m++; }   // a run of turns goes over as one block
      next = r.top + dir * m;
      const ks = [...Array(m)].map((_, j) => (dir === 1 ? r.top + j : r.top - 1 - j));
      const place = pages.pose ?? ((i: number, p: number) => { const f = padFlip(i, p, { home: (j: number) => pages.homes[j].position.y, ...pages.flip! });
        pages.meshes[i].position.y = f.y; pages.meshes[i].rotation.x = f.angle; });
      if (dir === 1) { if (next < n) setFace(r, next, r.want ? "hi" : "low"); body(r, n - next); }   // the pages have left the pad
      else setFace(r, next, r.want ? "hi" : "low");
      animator.play("stack:" + id, m > 1 ? ms(TURN_MS) : dur, p => ks.forEach(i => place(i, dir === 1 ? p : 1 - p)), now(),
        { done: () => { if (dir === -1) body(r, n - next); done(); } });
    }
  }
  const body = (r: Reader, remaining: number) => { const p = r.f.pages!; if (p.body) setBodyHeight(p.body, p.bodyBase, stackBodyHeight(remaining)); };

  /** Do the next thing this object needs, one motion at a time: pick up, turn, put down, or come to rest. */
  function pump(r: Reader) {
    if (r.busy) return;
    const held = !!r.f.held;
    if (held && r.want && r.pose === "rest") { if (!hand || hand === r.f.item.id) pickUp(r); return; }   // one thing in the hand
    if (r.queue.length && (!held || r.pose === "held")) { move(r, r.queue.shift()!); return; }
    if (held && !r.want && r.pose === "held") { putDown(r); return; }
    faces(r); if (r.pose === "rest") settle(r);
    ctx.kick();
  }
  /** The page the object will show once its current move and queue are done. */
  const after = (r: Reader) => { const n = r.f.pages?.count ?? 1, cyc = !!r.f.item.cyclic; let p = r.top + r.moving;
    for (const d of r.queue) p += d; return cyc ? ((p % n) + n) % n : p; };
  function want(r: Reader, page: number, dir: 1 | -1 | undefined) {
    r.want = true;
    if (r.f.pages) { const s = stepsTo(after(r), page, r.f.pages.count, dir, !!r.f.item.cyclic); for (let i = 0; i < s.steps; i++) r.queue.push(s.dir); }
    pump(r);
  }
  function release(r: Reader) {
    r.want = false; r.queue = [];
    if (r.f.pages) { const s = stepsTo(after(r), 0, r.f.pages.count, undefined, !!r.f.item.cyclic); for (let i = 0; i < s.steps; i++) r.queue.push(s.dir); }
    pump(r);
  }

  function fan(pile: "cardPile" | "stickyPile", open: boolean) {
    const members = [...readers.values()].filter(r => r.f.item.pile === pile);
    const slots = fanSlots(members.length, members[0] ? { w: members[0].f.size.w, d: members[0].f.size.h } : { w: 0.1, d: 0.1 });
    members.forEach((r, i) => {
      const parent = r.f.object.parent!;
      r.f.rest.position.copy(open ? parent.worldToLocal(new THREE.Vector3(slots[i].x, slots[i].y, slots[i].z)) : r.f.home.position);
      r.f.rest.rotation.y = open ? slots[i].rotY : r.f.home.rotation.y;
      if (!r.busy && r.pose === "rest") settle(r);                   // one in your hand goes to its new rest when put down
    });
  }

  function apply(prev: Stack, next: Stack) {
    const pt = top(prev), nt = top(next);
    const prevR = pt.kind === "focus" ? readers.get(pt.id) : undefined, nextR = nt.kind === "focus" ? readers.get(nt.id) : undefined;
    const prevFan = prev.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    const nextFan = next.find(f => f.kind === "fan") as Extract<Frame, { kind: "fan" }> | undefined;
    if (prevR && prevR !== nextR) release(prevR);                     // gather it and put it back down
    if (prevFan && prevFan.pile !== nextFan?.pile) fan(prevFan.pile, false);
    if (nextFan && nextFan.pile !== prevFan?.pile) fan(nextFan.pile, true);
    if (nextR && nt.kind === "focus") want(nextR, nt.page, nextR === prevR ? nt.dir : undefined);
    if (nt.kind !== pt.kind || (nt.kind === "focus" && pt.kind === "focus" && nt.id !== pt.id) || nt.kind === "fan") moveCamera(shotFor(nt));
    ctx.kick();
  }

  return {
    dispatch(a: Action) { const next = reduce(stack, a, reg.items()); if (next !== stack) { const prev = stack; stack = next; apply(prev, next); } },
    stack: () => stack,
    /** Where clicking the focused thing leads, given the page it shows (null: just turn the page). */
    linkOf(id: string): Action | null { const r = readers.get(id); return r?.f.link ? r.f.link(r.top) : null; },
    /** The pointer is over this object (or nothing). Only something lying at rest lifts a little. */
    hover(id: string | undefined) {
      if (id === hovered) return; const old = hovered; hovered = id;
      for (const k of [old, id]) { const r = k ? readers.get(k) : undefined; if (r && !r.busy && r.pose === "rest" && !r.want) settle(r); }
      ctx.kick();
    },
    tick(t: number): boolean {
      const moving = animator.step(t);
      const par = top(stack).kind === "overview" ? ctx.parallax() : new THREE.Vector3();
      camera.position.copy(camPos).add(par); camera.lookAt(camTarget);
      return moving;
    },
    onResize() {                                   // refit the current shot to the new aspect: snap, don't animate
      const shot = shotFor(top(stack)); animator.cancel("camera");
      camPos.set(...shot.position); camTarget.set(...shot.target); ctx.kick();
    },
    /** For browser checks: live textures we created, and whether anything is still in hand or moving. */
    debug: () => ({ textures: [...readers.values()].reduce((a, r) => a + r.tex.size, 0), hand,
      busy: [...readers.values()].filter(r => r.busy || r.queue.length || r.pose !== "rest").map(r => r.f.item.id) }),
  };
}
