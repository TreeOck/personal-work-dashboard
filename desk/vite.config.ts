import { defineConfig } from "vitest/config";
import { viteSingleFile } from "vite-plugin-singlefile";
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, unlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { templatePath, trackerHome } from "./scripts/paths.mjs";

// One self-contained file, written to the tracker data folder as desk-template.html,
// where `tracker build` injects the data.
export default defineConfig({
  plugins: [viteSingleFile({ removeViteModuleLoader: true }),
    { name: "place-output", closeBundle() {           // also runs after a failed build: don't mask the real error
      const out = resolve(import.meta.dirname, "dist/index.html");
      if (!existsSync(out)) return;
      const dest = templatePath();
      mkdirSync(dirname(dest), { recursive: true });
      copyFileSync(out, dest + ".tmp");               // copy + rename: the data folder may be on another disk, and a
      renameSync(dest + ".tmp", dest);                // half-written template must never be read by `tracker build`
      unlinkSync(out); } },
    { name: "serve-dev-data", configureServer(server) {   // `npm run dev` reads the data `tracker build` wrote
      server.middlewares.use("/dev-data.json", (_req, res) => {
        try { res.setHeader("content-type", "application/json"); res.end(readFileSync(join(trackerHome(), "dev-data.json"))); }
        catch { res.statusCode = 404; res.end("no dev-data.json in " + trackerHome() + " -- run: tracker build"); } }); } }],
  assetsInclude: ["**/*.hdr", "**/*.bin"],   // HDRIs and glTF buffers are not Vite asset types by default
  build: { outDir: "dist", assetsInlineLimit: Number.MAX_SAFE_INTEGER, chunkSizeWarningLimit: 30000, target: "es2022" },
  test: { environment: "node" },
});
