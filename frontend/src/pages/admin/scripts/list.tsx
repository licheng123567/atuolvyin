// 1:1 还原 ui/admin.html#a-scripts 话术库管理
import { useCreate, useCustomMutation, useDelete, useGo, useInvalidate, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { AlertTriangle, GitFork, Plus, Search, Upload } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import { TRIGGER_INTENTS, formatAdoptionRate } from "./helpers";
import { ScriptSheet } from "./ScriptSheet";

interface ScriptItem {
  id: number;
  tenant_id: number | null;
  provider_id: number | null;
  source: "platform" | "tenant" | "provider";
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

const SOURCE_BADGE: Record<ScriptItem["source"], { label: string; cls: string }> = {
  platform: { label: "平台预置", cls: "ds-badge ds-badge-gray" },
  tenant: { label: "本物业", cls: "ds-badge ds-badge-blue" },
  provider: { label: "服务商", cls: "ds-badge ds-badge-purple" },
};

const SCORE_CLASS: Record<string, string> = {
  A: "score-a",
  B: "score-b",
  C: "score-c",
  D: "score-d",
};

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

  const data = query.data?.data as unknown as
    | PaginatedResponse<ScriptItem>
    | undefined;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const { mutate: toggle } = useCreate();
  const { mutate: del } = useDelete();
  const { mutate: forkScript } = useCustomMutation();
  const invalidate = useInvalidate();

  const autoDisabledCount = items.filter(
    (s) => s.score_grade === "D" && !s.is_active,
  ).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">话术库管理</h1>
          <div className="page-subtitle">共 {total} 条话术</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            onClick={() => go({ to: "/admin/scripts/import" })}
          >
            <Upload className="w-3.5 h-3.5" />
            批量导入
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={() => {
              setEditScript(null);
              setSheetOpen(true);
            }}
          >
            <Plus className="w-3.5 h-3.5" />
            新增话术
          </button>
        </div>
      </div>

      {autoDisabledCount > 0 && (
        <div
          style={{
            background: "#fef9c3",
            border: "1px solid #fde047",
            borderRadius: 8,
            padding: "12px 16px",
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 16,
            fontSize: 13.5,
            color: "#854d0e",
          }}
        >
          <AlertTriangle className="w-4 h-4" />
          <span>
            {autoDisabledCount} 条 <strong>D 级话术</strong>（综合评分过低）已被自动禁用，建议修订后重新启用。
          </span>
        </div>
      )}

      <div className="table-wrap">
        <div className="table-toolbar">
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              className="form-control"
              placeholder="搜索话术标题或内容"
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setPage(1);
              }}
              style={{ minWidth: 200 }}
            />
          </div>
          <select
            className="form-control"
            style={{ width: 140 }}
            value={intent}
            onChange={(e) => {
              setIntent(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部异议类型</option>
            {TRIGGER_INTENTS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ width: 110 }}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部状态</option>
            <option value="active">启用</option>
            <option value="inactive">已禁用</option>
          </select>
        </div>

        <table>
          <thead>
            <tr>
              <th>话术标题</th>
              <th>来源</th>
              <th>异议类型</th>
              <th>级别</th>
              <th>使用次数</th>
              <th>采用率</th>
              <th>转化率</th>
              <th>综合评分</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={10} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={10} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无话术
                </td>
              </tr>
            )}
            {items.map((s) => {
              const isAutoDisabled = !s.is_active && s.score_grade === "D";
              return (
                <tr key={s.id} style={isAutoDisabled ? { opacity: 0.6 } : undefined}>
                  <td style={{ fontWeight: 500 }}>{s.title}</td>
                  <td>
                    {(() => {
                      const meta = SOURCE_BADGE[s.source] ?? SOURCE_BADGE.platform;
                      return <span className={meta.cls}>{meta.label}</span>;
                    })()}
                  </td>
                  <td>{s.trigger_intent}</td>
                  <td>
                    <span className="ds-badge ds-badge-gray">v{s.version}</span>
                  </td>
                  <td>{s.usage_count.toLocaleString()}次</td>
                  <td>{formatAdoptionRate(s.adoption_rate)}</td>
                  <td>{formatAdoptionRate(s.conversion_rate)}</td>
                  <td>
                    {s.score_grade ? (
                      <span className={SCORE_CLASS[s.score_grade] ?? ""}>
                        {s.score_grade}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {s.is_active ? (
                      <span className="ds-badge ds-badge-green">启用</span>
                    ) : isAutoDisabled ? (
                      <span className="ds-badge ds-badge-red">已禁用（自动）</span>
                    ) : (
                      <span className="ds-badge ds-badge-gray">已禁用</span>
                    )}
                  </td>
                  <td>
                    {s.source === "platform" ? (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        title="复制为本物业版后再编辑"
                        onClick={() =>
                          forkScript(
                            {
                              url: `admin/scripts/${s.id}/fork`,
                              method: "post",
                              values: {},
                            },
                            {
                              onSuccess: () => {
                                void invalidate({
                                  resource: "admin/scripts",
                                  invalidates: ["list"],
                                });
                              },
                            },
                          )
                        }
                      >
                        <GitFork className="w-3 h-3" />
                        Fork 为本物业版
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        onClick={() => {
                          setEditScript(s);
                          setSheetOpen(true);
                        }}
                      >
                        编辑
                      </button>
                    )}
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/admin/scripts/${s.id}/versions` })}
                    >
                      版本历史
                    </button>
                    {s.source !== "platform" && s.is_active && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        style={{ color: "#e02424" }}
                        onClick={() =>
                          toggle({
                            resource: `admin/scripts/${s.id}/toggle`,
                            values: {},
                          })
                        }
                      >
                        禁用
                      </button>
                    )}
                    {s.source !== "platform" && !s.is_active && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        style={{ color: "#057a55" }}
                        onClick={() =>
                          toggle({
                            resource: `admin/scripts/${s.id}/toggle`,
                            values: {},
                          })
                        }
                      >
                        启用
                      </button>
                    )}
                    {s.source !== "platform" && !s.is_active && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        style={{ color: "#e02424" }}
                        onClick={() =>
                          del({ resource: "admin/scripts", id: s.id })
                        }
                      >
                        删除
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="ds-pagination">
            <span className="pagination-info">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((p) => p - 1)}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div className="page-btn" onClick={() => setPage((p) => p + 1)}>
                  ›
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <ScriptSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        script={editScript}
        onSuccess={() => {
          setSheetOpen(false);
          query.refetch();
        }}
      />
    </div>
  );
}
