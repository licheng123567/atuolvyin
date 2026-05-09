# 列表页分页 + 搜索通用方案

适用范围：所有列表类页面（案件 / 用户 / 订单 / 工单 / 排班 / 审批 等）。

## 决策

- **服务端分页**（不要前端 slice）— 后端必须支持 `page` + `page_size` query params 并返回 `{ items, total, page, page_size }`
- **关键字搜索**走后端 `keyword` 模糊匹配（姓名 / 房号 / 手机号末四 / ID 等）— 不要前端 filter
- **debounce 300ms** — 避免每个按键都打后端
- **搜索时重置 page=1**

## 三件套

1. `frontend/src/components/ui/PaginationBar.tsx` — `<PaginationBar page pageSize total onPageChange />`
2. `frontend/src/components/ui/SearchInput.tsx` — `<SearchInput value onChange placeholder />`
3. `frontend/src/hooks/useDebouncedValue.ts` — `useDebouncedValue(value, 300)`

## 标准模板

```tsx
import { useState } from "react";
import { useList, type CrudFilter } from "@refinedev/core";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";

const PAGE_SIZE = 20;

export function MyListPage() {
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const debouncedKeyword = useDebouncedValue(keyword, 300);

  const filters: CrudFilter[] = [];
  if (debouncedKeyword.trim()) {
    filters.push({ field: "keyword", operator: "contains", value: debouncedKeyword.trim() });
  }

  const { query } = useList<MyItem>({
    resource: "admin/my-resource",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });
  const data = query.data?.data as unknown as { items: MyItem[]; total: number } | undefined;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">我的列表</h1>
        <SearchInput
          value={keyword}
          onChange={(v) => { setKeyword(v); setPage(1); }}
          placeholder="按姓名 / 手机号搜索"
        />
      </div>
      <table>{/* ... render items ... */}</table>
      <PaginationBar page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
    </div>
  );
}
```

## 后端约定

`GET /api/v1/{resource}?page=&page_size=&keyword=`

返回：
```json
{ "items": [...], "total": 123, "page": 1, "page_size": 20 }
```

后端处理 `keyword`：拼 `LIKE '%kw%'` 跨可搜字段（如 `name`, `phone_enc_search_index`, etc.）。

## 默认 pageSize

| 业务 | 推荐 pageSize |
|---|---|
| 案件 / 用户 / 订单 等主列表 | 20 |
| 看板（按状态分桶）| 不分页，加 stage filter |
| 审计日志 / 通话历史 | 30 |
| 排行榜 | 10（用 `LeaderboardTopN` 而非 `PaginationBar`）|

## 已应用

| 页面 | 路径 | 接入版本 |
|---|---|---|
| 审计日志 | `/admin/audit-logs` | 已有（v1.5.7）|
| 案件列表 | `/admin/cases` | 已有 |
| 我的案件 | `/agent/cases` | 已有（简易翻页）|
| 升级案件处理 | `/supervisor/escalated` | v1.6.4 |
| 用户管理 | `/admin/users` | v1.6.5 |
| 公海管理 | `/admin/pool` | v1.6.5 |
| 项目管理 | `/admin/projects` | v1.6.5 |
| 团队监控 | `/supervisor/team-performance` | v1.6.5 |
| 案件分配 | `/supervisor/cases` | v1.6.5 |
| 承诺催付 | `/supervisor/promises` | v1.6.5 |
| 案件超期报警 | `/supervisor/case-alerts` | v1.6.5 |
| 减免审批 | `/supervisor/discount-approvals` 与 `/admin/discount-approvals`（共用 `ApprovalListPage`）| v1.6.5 |

## TODO（后续）

- 法务订单 / 工单列表 等其余页面下批次接入
- URL query 同步（`?page=&kw=`）— 翻页可分享 / 后退恢复
