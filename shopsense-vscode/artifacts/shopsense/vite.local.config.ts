import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 21957);
const basePath = process.env.BASE_PATH || "/shopsense/";
const backendUrl = process.env.SHOPSENSE_BACKEND_URL || "http://127.0.0.1:8001";

export default defineConfig({
  base: basePath,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(root, "src"),
    },
    dedupe: ["react", "react-dom"],
  },
  root,
  build: {
    outDir: path.resolve(root, "dist/public"),
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port,
    strictPort: true,
    proxy: {
      "/api/shopsense": {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (requestPath) =>
          requestPath.replace(/^\/api\/shopsense/, "/shopsense-backend"),
      },
    },
  },
  preview: {
    host: "127.0.0.1",
    port,
    strictPort: true,
  },
});
