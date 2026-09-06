import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API and the reference audio both live under /api, so one proxy rule
// covers dev. Build output is committed, so outDir stays inside frontend/.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // ESM config, so no __dirname. Resolve @ against this file's own URL.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
