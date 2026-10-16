import * as THREE from "three";
import { top, type Action, type Stack } from "../camera/director";
import type { Focusable, Registry } from "../scene/focusables";
import { isClick } from "./input";
import { firstFocusable } from "./hits";

interface Ctx { canvas: HTMLCanvasElement; camera: THREE.PerspectiveCamera; scene: THREE.Scene; reg: Registry;
  dispatch: (a: Action) => void; stack: () => Stack; linkOf: (id: string) => Action | null; hover: (id: string | undefined) => void; kick: () => void; motion: number; label: HTMLElement }

const NAMES: Record<string, string> = { cards: "In progress", stickies: "To do", calendar: "Calendar", notepad: "Today's tally", cardPile: "More in progress", stickyPile: "More to do" };

export function createPicking(ctx: Ctx) {
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  let hovered: Focusable | undefined, down: { x: number; y: number; t: number } | null = null;
  const parallaxGoal = new THREE.Vector3(), parallax = new THREE.Vector3();

  const pick = (e: PointerEvent): Focusable | undefined => {
    const r = ctx.canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, ctx.camera);
    const f = firstFocusable(ray.intersectObjects(ctx.scene.children, true), o => ctx.reg.ofObject(o));   // the nearest thing you see
    if (!f) return undefined;
    const t = top(ctx.stack());
    return f.item.pile && !(t.kind === "fan" || t.kind === "focus") ? ctx.reg.get(f.item.pile) : f;      // closed pile: pick the pile
  };

  function setHover(f: Focusable | undefined, e?: PointerEvent) {
    if (f === hovered) { if (f && e) placeLabel(e); return; }
    hovered = f; ctx.hover(f?.item.id);
    ctx.canvas.style.cursor = f ? "pointer" : "default";
    if (f && e) { ctx.label.textContent = f.item.group === "cards" || f.item.group === "stickies" ? `${NAMES[f.item.group]} · ${f.label}` : f.label;
      ctx.label.style.opacity = "1"; placeLabel(e); } else ctx.label.style.opacity = "0";
    ctx.kick();
  }
  const placeLabel = (e: PointerEvent) => { ctx.label.style.transform = `translate(${e.clientX + 14}px, ${e.clientY + 14}px)`; };

  return {
    onPointerMove(e: PointerEvent) {
      const r = ctx.canvas.getBoundingClientRect();
      parallaxGoal.set(((e.clientX - r.left) / r.width - 0.5) * 0.03, -((e.clientY - r.top) / r.height - 0.5) * 0.015, 0);   // ±1.5 cm drift
      setHover(pick(e), e); ctx.kick();
    },
    onPointerDown(e: PointerEvent) { down = { x: e.clientX, y: e.clientY, t: performance.now() }; },
    onPointerUp(e: PointerEvent) {
      if (!down) return; const was = down; down = null;
      if (!isClick(was, { x: e.clientX, y: e.clientY, t: performance.now() })) return;     // a drag, not a click
      if (e.button === 2) { ctx.dispatch({ type: "back" }); return; }
      const f = pick(e), t = top(ctx.stack());
      if (!f) { ctx.dispatch({ type: "back" }); return; }                                   // empty desk = back
      if (t.kind === "focus" && t.id === f.item.id) ctx.dispatch(ctx.linkOf(f.item.id) ?? { type: "turn", dir: 1 });   // follow its link, or turn a page
      else ctx.dispatch({ type: "select", id: f.item.id });
    },
    onPointerLeave() { setHover(undefined); parallaxGoal.set(0, 0, 0); ctx.kick(); },
    /** Ease the overview parallax toward the pointer; true while still easing. */
    parallax(): THREE.Vector3 { parallax.lerp(parallaxGoal, 0.12 * (ctx.motion || 1)); return parallax; },
    parallaxBusy: () => parallax.distanceTo(parallaxGoal) > 1e-5,
    debug: () => ({ goal: parallaxGoal.toArray(), now: parallax.toArray() }),
  };
}
