// Build guard: fail loudly instead of producing a desk with missing textures.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { verify } from "./verify.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { missing, bad } = verify(join(root, "assets"), JSON.parse(readFileSync(join(root, "assets.lock.json"), "utf8")));
if (missing.length || bad.length) {
  for (const f of missing) console.error("missing asset:", f);
  for (const f of bad) console.error("corrupted asset (md5 mismatch):", f);
  console.error("run: npm run assets");
  process.exit(1);
}
