import { build } from "vite";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const output = resolve(root, "../../daemon/pilot/air_handoff_web");

await build({
  configFile: false,
  root,
  publicDir: false,
  build: {
    outDir: output,
    emptyOutDir: false,
    minify: "esbuild",
    sourcemap: false,
    lib: {
      entry: resolve(root, "src/air-handoff-receiver.ts"),
      formats: ["es"],
      fileName: () => "app.js",
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
