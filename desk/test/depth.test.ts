import { expect, test } from "vitest";
import { CAMERA, MIN_GAP, OVERVIEW, PAPER_T, depthResolutionAt, restOn, stackY } from "../src/scene/depth";

const farthest = Math.hypot(...OVERVIEW.position) + 1.0;  // the overview position plus the far edge of the desk, generously

test("MIN_GAP beats depth-buffer resolution at the farthest viewing distance by ≥ 4×", () => {
  expect(MIN_GAP).toBeGreaterThan(4 * depthResolutionAt(farthest, CAMERA.near, CAMERA.far));
});
test("stacked sheets are separated by thickness + MIN_GAP", () => {
  expect(stackY(0, 3, PAPER_T) - stackY(0, 2, PAPER_T)).toBeCloseTo(PAPER_T + MIN_GAP, 10);
});
// Confirmed cause of the mockup flicker (GPU renders, 14.85% -> 0.77% changed pixels): a model resting at
// exactly the desk height. Anything resting on a surface must sit MIN_GAP above it.
test("objects resting on a surface are never coplanar with it", () => {
  expect(restOn(0) - 0).toBe(MIN_GAP);
  expect(restOn(0.003) - 0.003).toBeCloseTo(MIN_GAP, 12);
});
