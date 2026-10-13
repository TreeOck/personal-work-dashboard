import { expect, test } from "vitest";
import { FLAT_NORMAL, fitDistance, focusShot } from "../src/camera/shots";

const projectedFraction = (extent: number, dist: number, fovRad: number) => (extent / 2) / (dist * Math.tan(fovRad / 2));

test("a wide object fills 70% of the horizontal view; a tall one 70% of the vertical", () => {
  const fov = 32, aspect = 16 / 9, v = (fov * Math.PI) / 180, h = 2 * Math.atan(Math.tan(v / 2) * aspect);
  const wide = fitDistance({ w: 0.148, h: 0.03 }, fov, aspect);
  expect(projectedFraction(0.148, wide, h)).toBeCloseTo(0.7, 6);
  const tall = fitDistance({ w: 0.03, h: 0.148 }, fov, aspect);
  expect(projectedFraction(0.148, tall, v)).toBeCloseTo(0.7, 6);
});

test("narrower windows move the camera back so the card still fits (resize while focused)", () => {
  expect(fitDistance({ w: 0.148, h: 0.105 }, 32, 9 / 16)).toBeGreaterThan(fitDistance({ w: 0.148, h: 0.105 }, 32, 16 / 9));
});

test("focusShot places the camera along the normal at the fit distance, aimed at the centre", () => {
  const s = focusShot([0.1, 0.02, 0.2], FLAT_NORMAL, { w: 0.148, h: 0.105 }, 32, 16 / 9);
  const d = fitDistance({ w: 0.148, h: 0.105 }, 32, 16 / 9);
  expect(s.target).toEqual([0.1, 0.02, 0.2]);
  const off = s.position.map((p, i) => p - s.target[i]);
  expect(Math.hypot(...off)).toBeCloseTo(d, 9);
  expect(off[1]).toBeGreaterThan(0); expect(off[2]).toBeGreaterThan(0);     // above, and from the seated (+z) side
  expect(focusShot([0, 0, 0], [0, 2, 0], { w: 1, h: 1 }, 32, 1).position[1]).toBeCloseTo(fitDistance({ w: 1, h: 1 }, 32, 1), 9); // normal is normalised
});
