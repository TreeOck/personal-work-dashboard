import { describe, expect, test } from "vitest";
import { Animator, easeInOutCubic } from "../src/anim/animator";

describe("Animator", () => {
  test("eases from 0 to 1 over the duration, then finishes and calls done once", () => {
    const a = new Animator(), seen: number[] = []; let done = 0;
    a.play("cam", 1000, p => seen.push(p), 0, { done: () => done++ });
    expect(a.step(0)).toBe(true); expect(a.step(500)).toBe(true); expect(a.step(1000)).toBe(false); a.step(2000);
    expect(seen[0]).toBe(0); expect(seen[1]).toBeCloseTo(0.5, 6); expect(seen[2]).toBe(1); expect(seen.length).toBe(3);
    expect(done).toBe(1); expect(a.busy).toBe(false);
  });
  test("zero duration applies the end state immediately (reduced motion)", () => {
    const a = new Animator(); let v = 0, done = false;
    a.play("lift", 0, p => (v = p), 123, { done: () => (done = true) });
    expect([v, done, a.busy]).toEqual([1, true, false]);
  });
  test("same key retargets: the old animation stops without its done, the new one runs", () => {
    const a = new Animator(); const log: string[] = [];
    a.play("cam", 1000, p => log.push("A" + p), 0, { done: () => log.push("A done") });
    a.step(100);
    a.play("cam", 1000, p => log.push("B" + p), 100, { done: () => log.push("B done") });
    a.step(1100);
    expect(log.some(l => l === "A done")).toBe(false);
    expect(log[log.length - 1]).toBe("B done");
  });
  test("independent keys run together; cancel stops one", () => {
    const a = new Animator(); let x = 0, y = 0;
    a.play("x", 100, p => (x = p), 0); a.play("y", 100, p => (y = p), 0);
    a.cancel("y"); a.step(100);
    expect([x, y]).toEqual([1, 0]);
  });
  test("easeInOutCubic is symmetric and hits its ends", () => {
    expect([easeInOutCubic(0), easeInOutCubic(1)]).toEqual([0, 1]);
    expect(easeInOutCubic(0.25) + easeInOutCubic(0.75)).toBeCloseTo(1, 12);
  });
});
