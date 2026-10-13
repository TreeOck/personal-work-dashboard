// Where everything sits on the desk (metres; desk top is y = 0, you sit at +z).
export const DESK = { w: 1.6, d: 0.8, h: 0.03 } as const;
export const MAT = { w: 0.72, d: 0.42, t: 0.003, x: -0.05, z: 0.16 } as const;
export const CARD_SIZE = { w: 0.148, d: 0.105 } as const;          // A6 index card
export const STICKY_SIZE = { w: 0.076, d: 0.076 } as const;        // 3" sticky note
export const SHEET_SIZE = { w: 0.21, d: 0.297 } as const;          // A4
export const TRAY = { x: 0.5, z: 0.08, w: 0.25, d: 0.34, h: 0.06, wall: 0.008, rotY: 0.1 } as const;
export const CUP = { x: 0.21, z: -0.2, r: 0.038, h: 0.1 } as const;
export const BINDER = { x: -0.42, z: -0.23, w: 0.24, d: 0.3, h: 0.045, rotY: 0.18 } as const;
export const CALENDAR = { x: -0.1, z: -0.26, w: 0.13, d: 0.08, h: 0.11 } as const;
export const NOTEPAD = { x: -0.58, z: 0.22, w: 0.1, d: 0.14 } as const;   // front-left: clear of mat, tray and binders
export const STICKY_AREA = { x: 0.445, z: -0.16, cols: 4 } as const;   // between cup and plant; rows go back (-z), never toward the tray
export const LAMP = { x: -0.66, z: -0.24, rotY: 0.9 } as const;
export const PLANT = { x: 0.68, z: -0.3, scale: 0.55 } as const;
export { CAMERA, MIN_GAP, PAPER_T, OVERVIEW, stackY, restOn } from "./depth";
