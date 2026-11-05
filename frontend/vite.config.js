import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // El 5173 es el que tiene permitido el CORS del backend
  server: { port: 5173, strictPort: true },
});
