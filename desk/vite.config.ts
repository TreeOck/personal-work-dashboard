import { defineConfig } from "vitest/config";
import { viteSingleFile } from "vite-plugin-singlefile";
import { existsSync, renameSync } from "node:fs";
import { resolve } from "node:path";

// One self-contained file, written to the repo root as desk-template.html,
// where build.py injects the data.
export default defineConfig({
  plugins: [viteSingleFile({ removeViteModuleLoader: true }),
    { name: "rename-output", closeBundle() {          // also runs after a failed build: don't mask the real error
      const out = resolve(import.meta.dirname, "dist/index.html");
      if (existsSync(out)) renameSync(out, resolve(import.meta.dirname, "../desk-template.html")); } }],
  assetsInclude: ["**/*.hdr", "**/*.bin"],   // HDRIs and glTF buffers are not Vite asset types by default
  build: { outDir: "dist", assetsInlineLimit: Number.MAX_SAFE_INTEGER, chunkSizeWarningLimit: 30000, target: "es2022" },
  test: { environment: "node" },
});
