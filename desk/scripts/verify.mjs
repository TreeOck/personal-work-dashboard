import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export function verify(dir, lock) {
  const missing = [], bad = [];
  for (const [rel, { md5 }] of Object.entries(lock)) {
    const p = join(dir, rel);
    if (!existsSync(p)) { missing.push(rel); continue; }
    if (createHash("md5").update(readFileSync(p)).digest("hex") !== md5) bad.push(rel);
  }
  return { missing, bad };
}
