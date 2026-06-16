import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    // In the dev compose, the API is reachable at the service name `api`.
    proxy: {
      "/api": { target: "http://api:8000", changeOrigin: true },
    },
  },
});
