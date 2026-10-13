// Downloads every asset in assets.lock.json into desk/assets/ and verifies md5.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { verify } from "./verify.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const lock = JSON.parse(readFileSync(join(root, "assets.lock.json"), "utf8"));
const out = join(root, "assets");
const { missing, bad } = verify(out, lock);
for (const rel of [...missing, ...bad]) {
  const res = await fetch(lock[rel].url, { headers: { "User-Agent": "Mozilla/5.0 personal-work-desk" } });
  if (!res.ok) throw new Error(`${rel}: HTTP ${res.status} from ${lock[rel].url}`);
  mkdirSync(dirname(join(out, rel)), { recursive: true });
  writeFileSync(join(out, rel), Buffer.from(await res.arrayBuffer()));
  console.log("fetched", rel);
}
const after = verify(out, lock);
if (after.missing.length || after.bad.length) { console.error("still wrong:", after); process.exit(1); }
console.log(`all ${Object.keys(lock).length} assets present and verified`);
