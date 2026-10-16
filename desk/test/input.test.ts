import { expect, test } from "vitest";
import { isClick, keyToAction, motionFactor } from "../src/interaction/input";

test("a short, still press is a click; moving or holding is not (Plan 4 drags rely on this)", () => {
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 13, y: 12, t: 150 })).toBe(true);
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 30, y: 10, t: 150 })).toBe(false);      // dragged 20 px
  expect(isClick({ x: 10, y: 10, t: 0 }, { x: 10, y: 10, t: 800 })).toBe(false);      // held
});

test("keys map to director actions; reserved and unknown keys do nothing", () => {
  expect(keyToAction("Escape")).toEqual({ type: "back" });
  expect(keyToAction(" ")).toEqual({ type: "turn", dir: 1 });
  expect(keyToAction(" ", true)).toEqual({ type: "turn", dir: -1 });
  expect(keyToAction("ArrowLeft")).toEqual({ type: "neighbor", dir: -1 });
  expect(keyToAction("ArrowRight")).toEqual({ type: "neighbor", dir: 1 });
  for (const k of ["0", "1", "2", "5", "6"]) expect(keyToAction(k)).toEqual({ type: "key", key: k });
  expect(keyToAction("3")).toEqual({ type: "key", key: "3" });                 // Plan 2b: the done tray
  for (const k of ["4", "7", "8", "x", "Enter"]) expect(keyToAction(k)).toBeNull();
});

test("reduced motion collapses durations to zero", () => {
  expect(motionFactor(true)).toBe(0); expect(motionFactor(false)).toBe(1);
});
