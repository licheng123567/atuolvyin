import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // v2.0 Task 3 — Android 6 / MIUI 10 出厂 WebView (Chromium 50 era) 不支持
  // ESNext。锁到 es2015 + chrome50 让 esbuild 自动 transpile。
  build: {
    target: ["es2015", "chrome50"],
  },
})
