// v1.4 S16.5 — 服务商管理员话术库（仅本服务商私有可写 + 平台预置只读）
import {
  useCreate,
  useDelete,
  useInvalidate,
  useList,
  useUpdate,
} from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface ScriptItem {
  id: number;
  tenant_id: number | null;
  provider_id: number | null;
  source: "platform" | "tenant" | "provider";
  title: string;
  trigger_intent: string;
  version: number;
  is_active: boolean;
  content: string;
  notes: string | null;
}

const TRIGGER_INTENTS = [
  "房屋质量",
  "经济困难",
  "服务不满",
  "联系困难",
  "其他",
];

const SOURCE_BADGE: Record<ScriptItem["source"], { label: string; cls: string }> = {
  platform: { label: "平台预置", cls: "ds-badge ds-badge-gray" },
  tenant: { label: "本物业", cls: "ds-badge ds-badge-blue" },
  provider: { label: "本服务商", cls: "ds-badge ds-badge-purple" },
};

export function ProviderScriptListPage() {
  const [keyword, setKeyword] = useState("");
  const [intent, setIntent] = useState("");
  const [page, setPage] = useState(1);
  const [editScript, setEditScript] = useState<ScriptItem | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const PAGE_SIZE = 20;
  const invalidate = useInvalidate();

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  if (intent) filters.push({ field: "intent", operator: "eq", value: intent });

  const { query } = useList<ScriptItem>({
    resource: "provider/scripts",
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

  function refresh() {
    void invalidate({ resource: "provider/scripts", invalidates: ["list"] });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">话术库</h1>
          <div className="page-subtitle">
            共 {total} 条 · 平台预置只读 · 仅本服务商私有可改
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
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

      <div className="table-wrap">
        <div className="table-toolbar">
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              type="text"
              className="form-control"
              placeholder="按标题/内容搜索"
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setPage(1);
              }}
              style={{ minWidth: 240 }}
            />
          </div>
          <select
            className="form-control"
            value={intent}
            onChange={(e) => {
              setIntent(e.target.value);
              setPage(1);
            }}
            style={{ width: 140 }}
          >
            <option value="">全部异议</option>
            {TRIGGER_INTENTS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>

        <table>
          <thead>
            <tr>
              <th>话术标题</th>
              <th>来源</th>
              <th>异议类型</th>
              <th>版本</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无话术
                </td>
              </tr>
            )}
            {items.map((s) => {
              const meta = SOURCE_BADGE[s.source] ?? SOURCE_BADGE.platform;
              const editable = s.source === "provider";
              return (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.title}</td>
                  <td>
                    <span className={meta.cls}>{meta.label}</span>
                  </td>
                  <td>{s.trigger_intent}</td>
                  <td>v{s.version}</td>
                  <td>
                    {s.is_active ? (
                      <span className="ds-badge ds-badge-green">启用</span>
                    ) : (
                      <span className="ds-badge ds-badge-gray">已禁用</span>
                    )}
                  </td>
                  <td>
                    {editable ? (
                      <>
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
                        <button
                          type="button"
                          className="ds-btn ds-btn-ghost ds-btn-sm"
                          style={{ color: s.is_active ? "#e02424" : "#057a55" }}
                          onClick={() =>
                            toggle(
                              {
                                resource: `provider/scripts/${s.id}/toggle`,
                                values: {},
                              },
                              { onSuccess: refresh },
                            )
                          }
                        >
                          {s.is_active ? "禁用" : "启用"}
                        </button>
                        {!s.is_active && (
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            style={{ color: "#e02424" }}
                            onClick={() =>
                              del(
                                { resource: "provider/scripts", id: s.id },
                                { onSuccess: refresh },
                              )
                            }
                          >
                            删除
                          </button>
                        )}
                      </>
                    ) : (
                      <span style={{ fontSize: 12, color: "#9ca3af" }}>仅查看</span>
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

      {sheetOpen && (
        <ProviderScriptEditor
          script={editScript}
          onClose={() => {
            setSheetOpen(false);
            setEditScript(null);
          }}
          onSaved={() => {
            setSheetOpen(false);
            setEditScript(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function ProviderScriptEditor({
  script,
  onClose,
  onSaved,
}: {
  script: ScriptItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(script?.title ?? "");
  const [intent, setIntent] = useState(script?.trigger_intent ?? "其他");
  const [content, setContent] = useState(script?.content ?? "");
  const [notes, setNotes] = useState(script?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const { mutate: create, mutation: createM } = useCreate();
  const { mutate: update, mutation: updateM } = useUpdate();
  const saving = createM.isPending || updateM.isPending;

  function submit() {
    setError(null);
    if (!title.trim() || !content.trim()) {
      setError("标题和内容不能为空");
      return;
    }
    const values = {
      title: title.trim(),
      trigger_intent: intent,
      content: content.trim(),
      notes: notes.trim() || null,
    };
    if (script) {
      update(
        { resource: "provider/scripts", id: script.id, values },
        { onSuccess: onSaved, onError: () => setError("保存失败") },
      );
    } else {
      create(
        { resource: "provider/scripts", values },
        { onSuccess: onSaved, onError: () => setError("创建失败") },
      );
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="ds-modal" style={{ width: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{script ? "编辑话术" : "新增话术"}</span>
          <button type="button" className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label className="form-label">标题<span className="req">*</span></label>
            <input
              type="text"
              className="form-control"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={128}
            />
          </div>
          <div>
            <label className="form-label">异议类型</label>
            <select
              className="form-control"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
            >
              {TRIGGER_INTENTS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">话术内容<span className="req">*</span></label>
            <textarea
              className="form-control"
              rows={6}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div>
            <label className="form-label">备注（可选）</label>
            <textarea
              className="form-control"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          {error && <p style={{ color: "#e02424", fontSize: 12 }}>{error}</p>}
        </div>
        <div className="modal-footer">
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            disabled={saving}
            onClick={submit}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
