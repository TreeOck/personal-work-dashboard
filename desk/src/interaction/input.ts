import type { Action } from "../camera/director";

type P = { x: number; y: number; t: number };
export const isClick = (down: P, up: P) => Math.hypot(up.x - down.x, up.y - down.y) < 6 && up.t - down.t < 500;

export function keyToAction(key: string, shift = false): Action | null {
  switch (key) {
    case "Escape": return { type: "back" };
    case " ": return { type: "turn", dir: shift ? -1 : 1 };
    case "ArrowLeft": return { type: "neighbor", dir: -1 };
    case "ArrowRight": return { type: "neighbor", dir: 1 };
    case "Home": return { type: "home" };
    case "0": case "1": case "2": case "3": case "5": case "6": return { type: "key", key };
    default: return null;                                     // 4, 7 and 8 belong to Plans 2b and 3
  }
}

export const motionFactor = (reduce: boolean) => (reduce ? 0 : 1);
