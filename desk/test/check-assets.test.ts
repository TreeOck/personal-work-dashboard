import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { expect, test } from "vitest";
import { verify } from "../scripts/verify.mjs";

const md5 = (s: string) => createHash("md5").update(s).digest("hex");

test("reports missing and corrupted files, accepts good ones", () => {
  const dir = mkdtempSync(join(tmpdir(), "assets-"));
  mkdirSync(join(dir, "fonts"));
  writeFileSync(join(dir, "fonts/good.ttf"), "good");
  writeFileSync(join(dir, "fonts/bad.ttf"), "tampered");
  const lock = {
    "fonts/good.ttf": { url: "u", md5: md5("good"), size: 4 },
    "fonts/bad.ttf": { url: "u", md5: md5("original"), size: 8 },
    "fonts/missing.ttf": { url: "u", md5: md5("x"), size: 1 },
  };
  expect(verify(dir, lock)).toEqual({ missing: ["fonts/missing.ttf"], bad: ["fonts/bad.ttf"] });
});
