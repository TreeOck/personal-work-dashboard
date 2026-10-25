import { expect, test } from "vitest";
import { join } from "node:path";
import { templatePath, trackerHome } from "../scripts/paths.mjs";

test("the data folder is TRACKER_HOME, else ~/.personal-tracker (same rule as the Python side)", () => {
  expect(trackerHome({ TRACKER_HOME: "/data/my tracker" }, "/home/me")).toBe("/data/my tracker");
  expect(trackerHome({}, "/home/me")).toBe(join("/home/me", ".personal-tracker"));
  expect(trackerHome({ TRACKER_HOME: "" }, "/home/me")).toBe(join("/home/me", ".personal-tracker"));   // empty counts as unset
});

test("the built desk template is written into the data folder", () => {
  expect(templatePath({ TRACKER_HOME: "/data/t" }, "/home/me")).toBe(join("/data/t", "desk-template.html"));
});
