// frontend/src/pages/admin/scripts/list.tsx
import { useCreate, useDelete, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Plus, Upload, History, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import { getScoreGradeColor, formatAdoptionRate, TRIGGER_INTENTS } from "./helpers";
import { ScriptSheet } from "./ScriptSheet";

interface ScriptItem {
  id: number;
  tenant_id: number | null;
  title: string;
  trigger_intent: string;
  version: number;
  usage_count: number;
  adoption_rate: number | null;
  conversion_rate: number | null;
  score_grade: string | null;
  is_active: boolean;
  content: string;
  notes: string | null;
}

export function ScriptListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [intent, setIntent] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editScript, setEditScript] = useState<ScriptItem | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  if (intent) filters.push({ field: "intent", operator: "eq", value: intent });
  if (status) filters.push({ field: "status", operator: "eq", value: status });

  const { query } = useList<ScriptItem>({
    resource: "admin/scripts",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const data = query.data?.data as unknown as PaginatedResponse<ScriptItem> | undefined;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const { mutate: toggle } = useCreate();
  const { mutate: del } = useDelete();

  const hasAutoDisabled = items.some((s) => s.score_grade === "D" && !s.is_active);

  return (
    <div style={{ padding: 24 }}>
      {hasAutoDisabled && (
        <div style={{
          background: "var(--color-danger-light)", color: "var(--color-danger)",
          padding: "8px 16px", borderRadius: 6, marginBottom: 16, fontSize: 14,
        }}>
          ⚠ 有话术因 D 级评分被自动禁用，请检查并决定是否删除或重写。
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <input
          placeholder="搜索标题/内容"
          value={keyword}
          onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6, width: 200 }}
        />
        <select value={intent} onChange={(e) => { setIntent(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6 }}>
          <option value="">全部类型</option>
          {TRIGGER_INTENTS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6 }}>
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">禁用</option>
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => go({ to: "/admin/scripts/import" })}
            style={{ padding: "6px 14px", background: "#f3f4f6", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <Upload size={14} /> 批量导入
          </button>
          <button onClick={() => { setEditScript(null); setSheetOpen(true); }}
            style={{ padding: "6px 14px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <Plus size={14} /> 新增话术
          </button>
        </div>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
            {["话术标题", "异议类型", "版本", "使用次数", "采用率", "评分", "状态", "操作"].map((h) => (
              <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 500, color: "#374151" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {query.isLoading && (
            <tr><td colSpan={8} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>加载中…</td></tr>
          )}
          {items.map((s) => (
            <tr key={s.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "10px 12px", maxWidth: 200 }}>
                <div style={{ fontWeight: 500 }}>{s.title}</div>
                {s.tenant_id === null && (
                  <span style={{ fontSize: 11, color: "#6b7280", background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>平台预置</span>
                )}
              </td>
              <td style={{ padding: "10px 12px" }}>{s.trigger_intent}</td>
              <td style={{ padding: "10px 12px" }}>v{s.version}</td>
              <td style={{ padding: "10px 12px" }}>{s.usage_count}</td>
              <td style={{ padding: "10px 12px" }}>{formatAdoptionRate(s.adoption_rate)}</td>
              <td style={{ padding: "10px 12px" }}>
                {s.score_grade ? (
                  <span
                    style={{ fontSize: 12, padding: "2px 8px", borderRadius: 4, border: "1px solid" }}
                    className={getScoreGradeColor(s.score_grade)}
                  >
                    {s.score_grade}
                  </span>
                ) : "—"}
              </td>
              <td style={{ padding: "10px 12px" }}>
                <span style={{
                  fontSize: 12, padding: "2px 8px", borderRadius: 4,
                  background: s.is_active ? "#dcfce7" : "#f3f4f6",
                  color: s.is_active ? "#15803d" : "#6b7280",
                }}>
                  {s.is_active ? "启用" : "禁用"}
                </span>
              </td>
              <td style={{ padding: "10px 12px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <button onClick={() => { setEditScript(s); setSheetOpen(true); }}
                    style={{ fontSize: 12, color: "var(--color-primary)", background: "none", border: "none", cursor: "pointer" }}>
                    编辑
                  </button>
                  <button onClick={() => toggle({ resource: `admin/scripts/${s.id}/toggle`, values: {} })}
                    title={s.is_active ? "禁用" : "启用"}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>
                    {s.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  </button>
                  <button onClick={() => go({ to: `/admin/scripts/${s.id}/versions` })}
                    title="版本历史"
                    style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>
                    <History size={16} />
                  </button>
                  {!s.is_active && (
                    <button onClick={() => del({ resource: "admin/scripts", id: s.id })}
                      title="删除"
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}>
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {total > PAGE_SIZE && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span>第 {page} 页 / 共 {Math.ceil(total / PAGE_SIZE)} 页</span>
          <button disabled={page * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}

      <ScriptSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        script={editScript}
        onSuccess={() => { setSheetOpen(false); query.refetch(); }}
      />
    </div>
  );
}
