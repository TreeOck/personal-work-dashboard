import { expect, test } from "vitest";
import { firstFocusable } from "../src/interaction/hits";

type O = { name: string; visible: boolean; parent: O | null; material?: { visible: boolean } | { visible: boolean }[] };
const obj = (name: string, parent: O | null = null, material: O["material"] = { visible: true }, visible = true): O => ({ name, visible, parent, material });
const resolve = (o: O) => (o.name.startsWith("card") ? o.name : undefined);

test("the nearest visible hit decides: a lamp in front of a card does not open the card", () => {
  expect(firstFocusable([{ object: obj("lamp") }, { object: obj("card:a") }] as never, resolve as never)).toBeUndefined();
  expect(firstFocusable([{ object: obj("card:a") }, { object: obj("lamp") }] as never, resolve as never)).toBe("card:a");
});
test("hidden things are not hits: invisible objects, hidden parents, invisible materials and hidden faces", () => {
  const hiddenParent = obj("g", null, undefined, false);
  const hits = [{ object: obj("edge", null, { visible: false }) }, { object: obj("x", hiddenParent) },
    { object: obj("box", null, [{ visible: true }, { visible: false }]), face: { materialIndex: 1 } }, { object: obj("off", null, { visible: true }, false) },
    { object: obj("card:b") }];
  expect(firstFocusable(hits as never, resolve as never)).toBe("card:b");
  expect(firstFocusable([], resolve as never)).toBeUndefined();
});
