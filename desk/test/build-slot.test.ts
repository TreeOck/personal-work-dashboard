import { execSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { expect, test } from "vitest";
import { templatePath } from "../scripts/paths.mjs";

const shipped = templatePath();   // where `npm run build` leaves the template that ships

test("production build keeps the /*__DATA__*/null slot verbatim, without touching the shipped template", () => {
  const before = existsSync(shipped) ? statSync(shipped).mtimeMs : null;
  const out = mkdtempSync(join(tmpdir(), "desk-build-"));
  const home = mkdtempSync(join(tmpdir(), "desk-home-"));   // a throwaway data folder: nothing may land in it either
  execSync(`npx vite build --outDir ${out} --emptyOutDir`, { cwd: resolve(import.meta.dirname, ".."), stdio: "pipe",
    env: { ...process.env, TRACKER_HOME: home } });
  const html = readFileSync(join(out, "index.html"), "utf8");
  expect(html).toContain("window.__DESK_DATA__ = /*__DATA__*/null;");
  expect(html).not.toMatch(/<script[^>]+src=/);   // everything inlined
  expect(existsSync(shipped) ? statSync(shipped).mtimeMs : null).toBe(before);   // review I5: tests must not replace what ships
  expect(existsSync(join(home, "desk-template.html"))).toBe(false);
}, 120_000);
