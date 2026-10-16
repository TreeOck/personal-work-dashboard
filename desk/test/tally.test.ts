import { expect, test } from "vitest";
import { tallyLines } from "../src/paper/tallyPage";

test("a working day lists counts and the first/last commit times", () => {
  expect(tallyLines({ ymd: "2026-10-13", label: "Today", commits: 12, tasks: 4, todosDone: 2, first: "09:12", last: "18:40" }))
    .toEqual(["Today", "commits  12", "tasks  4", "to-dos done  2", "09:12 → 18:40"]);
});
test("a day with nothing says so instead of showing an empty page", () => {
  expect(tallyLines({ ymd: "2026-10-11", label: "Sat 11 Oct", commits: 0, tasks: 0, todosDone: 0, first: null, last: null }))
    .toEqual(["Sat 11 Oct", "a quiet day"]);
});

import { doneBlocks } from "../src/paper/layout";
test("a done sheet records the task, where it lived, when it was finished and how long it took", () => {
  const vm = { id: "t-0001", title: "Ship it", where: "alpha / api", ink: { hex: "#123456", name: "", variant: 0 }, notes: [{ at: "", text: "merged" }], commits: [],
    started: "2026-10-12T09:00:00+05:30", closed: "2026-10-14T12:30:00+05:30" };
  const text = doneBlocks(vm).map(b => b.text);
  expect(text.slice(0, 3)).toEqual(["t-0001 · alpha / api", "Ship it", "done Wed 14 Oct · took 2d 3h"]);
  expect(text).toContain("— merged");
});
