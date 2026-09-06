import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API and the reference audio both live under /api, so one proxy rule
// covers dev. Build output is committed, so outDir stays inside frontend/.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
