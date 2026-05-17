import { defineConfig, configDefaults } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    // e2e/ 下是 Playwright spec，由 `npm run test:e2e` 运行；
    // 不能让 vitest 收编（会因 Playwright test() 调用直接报错）。
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
})
