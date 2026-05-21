// 把 dist/assets/index-*.js 用 Babel preset-env 降到 Chromium 53 可执行的语法。
// Vite 8 + rolldown 的 build.target 不真正做语法降级；这里用 Babel 兜底。
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { transformSync } from "@babel/core";

const dir = "dist/assets";
const file = readdirSync(dir).find((f) => /^index-.*\.js$/.test(f));
if (!file) {
  console.error("[lower-bundle] no bundle found in", dir);
  process.exit(1);
}
const path = join(dir, file);
const src = readFileSync(path, "utf8");
console.log("[lower-bundle] transforming", path, "(", src.length, "bytes )");

const start = Date.now();
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
        // bundle 已经是 IIFE 非模块化代码，不要再注入 require / import 语句
        modules: false,
        loose: true,
        exclude: ["transform-typeof-symbol"],
      },
    ],
  ],
});

if (!out || !out.code) {
  console.error("[lower-bundle] transform produced no output");
  process.exit(2);
}
writeFileSync(path, out.code);
console.log(
  "[lower-bundle] done in",
  Date.now() - start,
  "ms; new size",
  out.code.length,
  "bytes",
);
