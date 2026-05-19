import path from "path"
import { readFileSync, writeFileSync, readdirSync } from "node:fs"
import { defineConfig, type Plugin } from "vite"
import react from "@vitejs/plugin-react"
import { transformSync } from "@babel/core"

// v2.2 — Chromium 53（Android 6 stock WebView）不支持 <script type="module">。
// 即使 rolldownOptions.format = "iife"，Vite 仍会在 dist/index.html 注入
// type="module" + crossorigin。把这两个属性剥掉，浏览器才会把 IIFE bundle
// 当 classic script 执行。
// 同时把 script 从 <head> 搬到 </body> 前 — IIFE classic script 同步执行，
// 若放 <head> 里则 getElementById("root") 在 DOM parse 之前跑会拿到 null。
// 最后注入 polyfill prelude inline（globalThis / Object.fromEntries /
// Array.flat / Promise.allSettled 等 Chrome 53 缺的 API + JS 错误回传 endpoint）。
const stripModuleAttrs = (): Plugin => ({
  name: "strip-module-attrs",
  enforce: "post",
  // v2.4 fix — 只在 vite build 阶段跑；vite dev 不剥 type="module"，
  // 否则 PC dev /login 会因 main.tsx 被当 classic script 而抛
  // "SyntaxError: Cannot use import statement outside a module"。
  apply: "build",
  transformIndexHtml: {
    order: "post",
    handler(html: string) {
      const stripped = html
        .replace(/<script\s+type="module"\s+crossorigin\s+/g, "<script ")
        .replace(/<script\s+type="module"\s+/g, "<script ")
        .replace(/\s+crossorigin(\s|>)/g, "$1")
      const scriptMatch = stripped.match(/\s*<script\s+src="[^"]+"\s*><\/script>/)
      if (!scriptMatch) return stripped
      const scriptTag = scriptMatch[0].trim()
      // 读取 polyfill prelude，inline 嵌入；放在 bundle script 之前
      const polyfillSrc = readFileSync(
        path.resolve(__dirname, "polyfills-chrome53.js"),
        "utf8",
      )
      const inlinePolyfill = `<script>${polyfillSrc}</script>`
      return stripped
        .replace(scriptMatch[0], "")
        .replace(
          "</body>",
          `  ${inlinePolyfill}\n  ${scriptTag}\n  </body>`,
        )
    },
  },
})

// v2.2 — Vite 8 + rolldown 的 build.target 不真正做语法降级，bundle 里仍有
// optional-chaining / async / nullish-coalescing 等 Chromium 53 不认的语法。
// Babel preset-env 降到 chrome 53 兜底（Android 6 stock WebView）。
// 同时把文件名加 build 时间戳（WebView 即使开 cacheMode = LOAD_NO_CACHE，
// 部分老机型仍偶发命中老 URL；改名最稳妥）。
import { renameSync } from "node:fs"

const lowerToChrome53 = (): Plugin => ({
  name: "lower-to-chrome53",
  apply: "build",
  closeBundle: {
    sequential: true,
    handler() {
      const distDir = path.resolve(__dirname, "dist")
      const assetsDir = path.join(distDir, "assets")
      // 多入口：index.html + mobile.html，每个对应自己的 index-* / main-mobile-* bundle
      const bundles = readdirSync(assetsDir).filter((f) => /\.js$/.test(f))
      // 找所有 dist/*.html
      const htmlFiles = readdirSync(distDir).filter((f) => f.endsWith(".html"))
      for (const file of bundles) {
        const full = path.join(assetsDir, file)
        const src = readFileSync(full, "utf8")
        const start = Date.now()
        const out = transformSync(src, {
          babelrc: false,
          configFile: false,
          compact: true,
          comments: false,
          sourceMaps: false,
          presets: [
            [
              "@babel/preset-env",
              {
                targets: { chrome: "53" },
                bugfixes: true,
                modules: false,
                loose: true,
                exclude: ["transform-typeof-symbol"],
              },
            ],
          ],
        })
        if (!out || !out.code) {
          this.error(`babel transform produced no output for ${file}`)
          return
        }
        writeFileSync(full, out.code)
        // 文件名加 build 时间戳，强制 WebView 重新拉取
        const ts = Date.now()
        const newName = file.replace(/\.js$/, `-${ts}.js`)
        const newFull = path.join(assetsDir, newName)
        renameSync(full, newFull)
        // 把所有 HTML 里对老文件的引用改成新文件名
        for (const html of htmlFiles) {
          const htmlPath = path.join(distDir, html)
          const htmlSrc = readFileSync(htmlPath, "utf8")
          if (htmlSrc.includes(file)) {
            writeFileSync(htmlPath, htmlSrc.replace(file, newName))
          }
        }
        console.log(
          `[lower-to-chrome53] ${file} → ${newName}: ${src.length} → ${out.code.length} bytes (${Date.now() - start}ms)`,
        )
      }
      // SPA fallback：Python static server 默认找 index.html，alias 一下
      const mobileHtml = path.join(distDir, "mobile.html")
      const indexHtml = path.join(distDir, "index.html")
      if (htmlFiles.includes("mobile.html")) {
        writeFileSync(indexHtml, readFileSync(mobileHtml, "utf8"))
      }
    },
  },
})

export default defineConfig(({ command }) => {
  // v2.4 fix — 这些 alias 仅供 mobile build（Android WebView Chromium 53 兼容）；
  // PC dev (vite :5173) 必须走真 react-router-dom v7 + 真 @refinedev/core v5，
  // 否则 @refinedev/react-router 拉不到 v6 缺失的 Link export，dep optimize 失败 → /login 红屏。
  const mobileBuildAliases: Record<string, string> =
    command === "build"
      ? {
          // v2.2 — mobile bundle 走 react-router v6（v7 用 Chrome 95+ API，
          // Android 6 stock WebView Chrome 57 不兼容）。
          "react-router-dom": path.resolve(__dirname, "./node_modules/react-router-dom-v6"),
          "react-router": path.resolve(__dirname, "./node_modules/react-router-v6"),
          // v2.2 — Refine v5 + TanStack Query 5 在 Chrome 57 silent-abort，
          // mobile bundle 走自写 stub（只实现 mobile pages 用到的 5 个 hooks）。
          "@refinedev/core": path.resolve(__dirname, "./src/refine-mobile-stub.tsx"),
        }
      : {}
  return {
    plugins: [react(), stripModuleAttrs(), lowerToChrome53()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
        ...mobileBuildAliases,
      },
    },
    build: {
      target: ["es2015", "chrome50"],
      rolldownOptions: {
        // v2.2 — mobile-only build：避开 Chromium 53 的 2.1MB IIFE OOM。
        // PC 走 Vite dev :5173；prod build 只为 Android WebView 做。
        input: path.resolve(__dirname, "mobile.html"),
        output: {
          format: "iife",
          entryFileNames: "assets/[name]-[hash].js",
          inlineDynamicImports: true,
        },
      },
    },
  }
})
