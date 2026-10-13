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
