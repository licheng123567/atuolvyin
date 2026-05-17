# §9 收尾打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 §9 配套前端 UI 合并后整体复审遗留的三处尾巴 —— provider-legal E2E 冒烟、法务详情页 `alert()` 改内联错误、法务列表页空/错误态行抽共享小组件。

**Architecture:** 纯收尾，无新功能。①新增一个法务簇专用的表格状态行组件消除 colspan 重复；②把 `requests/[id].tsx` 的 `alert()` 换成与同目录 `cases/[id].tsx` 一致的内联红字；③seed 加一个服务商侧 legal 账号并接通已留好的 E2E TODO。

**Tech Stack:** React + TypeScript + Refine + Vitest（前端）；Python + SQLAlchemy（seed）；Playwright（E2E）。

---

## Task 1: 法务列表 colspan 状态行共享组件

**Files:**
- Create: `frontend/src/pages/provider/legal/TableStateRow.tsx`
- Create: `frontend/src/pages/provider/legal/__tests__/table-state-row.test.tsx`
- Modify: `frontend/src/pages/provider/legal/cases/index.tsx`（3 处 colspan 行）
- Modify: `frontend/src/pages/provider/legal/requests/index.tsx`（3 处 colspan 行）

背景：`cases/index.tsx` L64-83 与 `requests/index.tsx` L43-62 各有 3 个完全同构的 `<tr><td colSpan={n} style={{textAlign:"center",padding:32,color:"var(--color-neutral-400)"}}>文案</td></tr>`（加载中 / 加载失败 / 空态）。抽成一个组件，纯 DRY、不改视觉。`agent-commissions` / `provider/commission` 用 Tailwind 风格、不在本任务范围。

- [ ] **Step 1: 写失败测试** — `__tests__/table-state-row.test.tsx`：

```tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TableStateRow } from "../TableStateRow";

describe("TableStateRow", () => {
  it("renders children inside a td with the given colSpan", () => {
    const { container } = render(
      <table>
        <tbody>
          <TableStateRow colSpan={6}>加载中…</TableStateRow>
        </tbody>
      </table>,
    );
    const td = container.querySelector("td");
    expect(td).not.toBeNull();
    expect(td?.getAttribute("colspan")).toBe("6");
    expect(td?.textContent).toBe("加载中…");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/table-state-row.test.tsx`
Expected: FAIL — 模块 `../TableStateRow` 不存在。

- [ ] **Step 3: 创建 `TableStateRow.tsx`**：

```tsx
// §9.1 — 法务列表页共享的表格状态行（加载中 / 加载失败 / 空态）
import type { ReactNode } from "react";

export function TableStateRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}
      >
        {children}
      </td>
    </tr>
  );
}
```

- [ ] **Step 4: 改 `cases/index.tsx`** —— 顶部 import `import { TableStateRow } from "../TableStateRow";`。把 L64-84 的三块替换为：

```tsx
            {isLoading && <TableStateRow colSpan={6}>加载中…</TableStateRow>}
            {isError && !isLoading && <TableStateRow colSpan={6}>加载失败</TableStateRow>}
            {!isLoading && !isError && filteredItems.length === 0 && (
              <TableStateRow colSpan={6}>{keyword ? "无匹配结果" : "暂无案件"}</TableStateRow>
            )}
```

数据行 `{!isLoading && !isError && filteredItems.map(...)}` 段保持不变。

- [ ] **Step 5: 改 `requests/index.tsx`** —— 顶部 import `import { TableStateRow } from "../TableStateRow";`。把 loading / error / empty 三块（`<td colSpan={7}>`）替换为：

```tsx
            {isLoading && <TableStateRow colSpan={7}>加载中…</TableStateRow>}
            {isError && !isLoading && <TableStateRow colSpan={7}>加载失败</TableStateRow>}
            {!isLoading && !isError && items.length === 0 && (
              <TableStateRow colSpan={7}>暂无转化请求</TableStateRow>
            )}
```

数据行段保持不变。

- [ ] **Step 6: 跑测试确认通过 + 回归**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/table-state-row.test.tsx src/pages/provider/legal/__tests__/cases-list.test.tsx src/pages/provider/legal/__tests__/requests-list.test.tsx`
Expected: PASS —— `table-state-row` 新测试通过；`cases-list` / `requests-list` 既有测试（断言「加载中…」「加载失败」空态文案）零回归（文案未变，仅 DOM 结构封装）。

- [ ] **Step 7: lint + typecheck + commit**

```bash
cd frontend && npm run lint && npx tsc -p tsconfig.json --noEmit
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/TableStateRow.tsx frontend/src/pages/provider/legal/__tests__/table-state-row.test.tsx frontend/src/pages/provider/legal/cases/index.tsx frontend/src/pages/provider/legal/requests/index.tsx
git commit -m "refactor(§9-fe): 抽 TableStateRow 共享组件消除法务列表 colspan 重复"
```

---

## Task 2: 法务转化请求详情页 alert() 改内联错误

**Files:**
- Modify: `frontend/src/pages/provider/legal/requests/[id].tsx`
- Modify: `frontend/src/pages/provider/legal/__tests__/request-detail.test.tsx`

背景：`requests/[id].tsx` 的上传/下载/超限错误用了 3 处 `alert()`（L80 / L91 / L104）。同目录 `cases/[id].tsx` 用的是内联红字 `setErr` + `{err && <div style={{color:"var(--color-danger)",fontSize:13}}>{err}</div>}`（L26、L148-150）。本任务把 `alert()` 换成同样的内联写法，统一到 §9.1 法务簇风格。

- [ ] **Step 1: 改测试先反映目标行为** — `request-detail.test.tsx`：当前「超大文件」用例断言 `window.alert` 被调用。改为断言内联错误文案出现。把该用例（及上传失败用例，如有）改成不再 spy `alert`，而是：

  - 超大文件用例：触发选文件（`file.size` > 20MB）后，`await waitFor(() => expect(screen.getByText("文件超过 20MB 上限")).toBeDefined())`，并断言 `uploadRequestMaterial` 未被调用。
  - 上传失败用例（让 mock 的 `uploadRequestMaterial` reject `new Error("上传炸了")`）：`await waitFor(() => expect(screen.getByText("上传炸了")).toBeDefined())`。

  其余既有用例（渲染、空材料态、加载/错误态、下载调用）保持不变。若既有用例里有 `vi.spyOn(window, "alert")` 相关代码，一并删除。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/request-detail.test.tsx`
Expected: FAIL —— 页面仍走 `alert()`，DOM 里没有内联错误文案。

- [ ] **Step 3: 改 `requests/[id].tsx`**：

  - 在 `const [uploading, setUploading] = useState(false);` 之后加一行：`const [errMsg, setErrMsg] = useState("");`
  - `handleFileChange` 开头（取到 `file` 之后、`if (!file) return;` 之后）加 `setErrMsg("");` 清空旧错误。
  - 把 `alert("文件超过 20MB 上限")` 改为 `setErrMsg("文件超过 20MB 上限");`
  - 把 `alert(uploadErr.message ?? "上传失败")` 改为 `setErrMsg(uploadErr.message ?? "上传失败");`
  - `handleDownload` 开头加 `setErrMsg("");`；把 `alert(downloadErr.message ?? "获取下载链接失败")` 改为 `setErrMsg(downloadErr.message ?? "获取下载链接失败");`
  - 在「补充材料卡」内、标题/上传按钮那一行 `</div>` 之后、材料列表 `{detail.materials.length === 0 ? ...}` 之前，插入内联错误块：

```tsx
          {errMsg && (
            <div style={{ color: "var(--color-danger)", fontSize: 13, marginBottom: 8 }}>
              {errMsg}
            </div>
          )}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/request-detail.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + typecheck + commit**

```bash
cd frontend && npm run lint && npx tsc -p tsconfig.json --noEmit
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/requests/\[id\].tsx frontend/src/pages/provider/legal/__tests__/request-detail.test.tsx
git commit -m "refactor(§9-fe): 法务请求详情页上传/下载错误改内联红字（对齐 cases 详情页）"
```

---

## Task 3: seed 服务商法务账号 + provider-legal E2E 冒烟

**Files:**
- Modify: `poc/backend/scripts/seed_demo.py`
- Modify: `frontend/e2e/per-role-pages.spec.ts`

背景：§9 T8 把 provider-legal 的 nav/route 做完了，但 E2E 冒烟因 seed 无「服务商侧 legal」账号而搁置，`per-role-pages.spec.ts` L111-121 留了 TODO。本任务补 seed 账号（phone `13000000013`，沿用服务商侧号段）并接通 E2E。

- [ ] **Step 1: seed 加服务商法务用户** —— `seed_demo.py` 在「新增服务商侧催收员 + 督导」段（`provider_supervisor_user` 那行，约 L855）之后加一行：

```python
        provider_legal_user, _ = _upsert_user(db, "13000000013", "服务商法务李")
```

- [ ] **Step 2: seed 加 membership** —— 在 `provider_supervisor_user` 的 `_upsert_membership(...)` 调用（约 L884-886）之后加：

```python
        _upsert_membership(
            db, provider_legal_user, tenant, "legal", provider_id=provider.id
        )
```

- [ ] **Step 3: 校验 seed 脚本** —— 语法/导入校验，能跑则跑：

Run: `cd poc/backend && python3.12 -m py_compile scripts/seed_demo.py`
Expected: 无输出（编译通过）。
若本地 autoluyin dev DB 已起，可进一步 `python3.12 scripts/seed_demo.py` 跑一遍确认账号落库（`[ok] UserAccount: 服务商法务李`）；DB 未起则跳过，E2E 实跑时再 seed。

- [ ] **Step 4: 接通 E2E** —— `per-role-pages.spec.ts` 把 L111-121 的 TODO 注释块整体替换为真实 ROLE_CASES 项：

```ts
  {
    name: "legal (provider)",
    phone: "13000000013",
    pages: [
      { path: "/provider/legal/cases", expectText: /法务案件|案件/ },
      { path: "/provider/legal/requests", expectText: /转化请求|请求/ },
    ],
  },
```

（保留该项前面 L108-109 关于 `13000000012` 的注释；删掉整段 `TODO(§9-provider-legal)` 注释含「导航与路由已通过 nav.test.ts 单测覆盖」那行。）

- [ ] **Step 5: 校验 E2E spec 不破坏** —— TypeScript 校验 spec 文件无误（E2E 实跑需完整 dev stack，本任务不强求实跑）：

Run: `cd frontend && npx tsc -p tsconfig.json --noEmit`
Expected: 无类型报错。
注：`per-role-pages.spec.ts` 用 Playwright，由 `npm run test:e2e` 在 dev stack 起来后运行；本任务交付的是 seed 账号 + spec 项，实跑验证留待 dev 环境。

- [ ] **Step 6: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/scripts/seed_demo.py frontend/e2e/per-role-pages.spec.ts
git commit -m "test(§9): seed 服务商法务账号 + 接通 provider-legal E2E 冒烟"
```

---

## Self-Review

**范围核对：** 三个 task 对应整体复审遗留的三处尾巴 —— Task 1 = 法务簇空/错误态抽组件（用户已确认「只抽法务簇、提成 3 页不动」）；Task 2 = `alert()` 改内联（用户确认）；Task 3 = provider-legal E2E（T8 TODO）。未纳入：跨簇统一 7 页（用户明确否决）、法务列表服务端搜索（既有模式延续，复审判定可不动）、项目级 125 处 `alert()` 清理（超出 §9 范围）。

**占位符扫描：** 无 TBD/TODO。Task 3 Step 3/5 的「能跑则跑 / 留待 dev 环境」是 E2E 客观依赖完整 dev stack 的如实说明，非占位符 —— 已给出可在 CI 外执行的校验（`py_compile` / `tsc`）。

**类型一致性：** `TableStateRow` props `{ colSpan: number; children: ReactNode }` 在 Task 1 各处用法一致；`errMsg`/`setErrMsg` 在 Task 2 内一致；seed 的 `provider_legal_user` 与 `_upsert_membership` 签名（`provider_id` 关键字参数）对齐 `seed_demo.py` 既有服务商侧用法。

**回归保障：** Task 1 不改任何状态态文案，`cases-list.test.tsx` / `requests-list.test.tsx` 既有断言即回归网；Task 2 改测试先行（Step 1）守住 alert→内联的行为迁移。
