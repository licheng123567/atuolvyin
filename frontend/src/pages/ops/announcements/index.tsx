// Sprint 10.3 — 系统公告管理（PRD §L2001）
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Megaphone, Plus, Trash2, X, Edit2 } from "lucide-react";
import { useState } from "react";

interface AnnouncementItem {
  id: number;
  title: string;
  body: string;
  audience: string;
  publish_at: string | null;
  created_by: number;
  created_at: string;
}

const AUDIENCE_PRESETS = [
  { value: "all", label: "全部用户" },
  { value: "role:admin", label: "管理员" },
  { value: "role:supervisor", label: "主管/督导" },
  { value: "role:agent", label: "催收员" },
  { value: "role:legal", label: "法务专员" },
];

export function OpsAnnouncementsPage() {
  const [stateFilter, setStateFilter] = useState("");
  const [editing, setEditing] = useState<AnnouncementItem | null>(null);
  const [showNew, setShowNew] = useState(false);

  const { query } = useCustom<AnnouncementItem[]>({
    url: "ops/announcements",
    method: "get",
    config: { query: stateFilter ? { state: stateFilter } : undefined },
  });
  const items = query.data?.data ?? [];

  const { mutate: del } = useCustomMutation();
  const handleDelete = (id: number) => {
    if (!confirm("确定删除此公告?")) return;
    del(
      { url: `ops/announcements/${id}`, method: "delete", values: {} },
      { onSuccess: () => query.refetch() },
    );
  };

  const stateOf = (a: AnnouncementItem): string => {
    if (!a.publish_at) return "草稿";
    return new Date(a.publish_at) > new Date() ? "定时发布" : "已发布";
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Megaphone className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">系统公告</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {items.length} 条
        </span>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="scheduled">定时发布</option>
            <option value="published">已发布</option>
          </select>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Plus className="w-4 h-4" />
            新建公告
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {items.length === 0 && !query.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)] py-8 text-center">
            暂无公告
          </p>
        )}
        {items.map((a) => (
          <div
            key={a.id}
            className="bg-white p-4 border border-[var(--color-neutral-200)] flex items-start gap-3"
            style={{ borderRadius: "var(--radius-lg)" }}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-sm font-semibold">{a.title}</h3>
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-neutral-100)] text-[var(--color-neutral-600)]">
                  {stateOf(a)}
                </span>
                <span className="text-xs text-[var(--color-neutral-400)]">
                  {a.audience}
                </span>
              </div>
              <p className="text-sm text-[var(--color-neutral-700)] line-clamp-2">
                {a.body}
              </p>
              <p className="text-xs text-[var(--color-neutral-400)] mt-2">
                创建：{a.created_at?.slice(0, 19).replace("T", " ")}
                {a.publish_at && (
                  <> · 发布于：{a.publish_at?.slice(0, 19).replace("T", " ")}</>
                )}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setEditing(a)}
                className="text-[var(--color-primary)]"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => handleDelete(a.id)}
                className="text-[var(--color-danger)]"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {(showNew || editing) && (
        <AnnouncementDialog
          item={editing}
          onClose={() => {
            setShowNew(false);
            setEditing(null);
          }}
          onSaved={() => {
            setShowNew(false);
            setEditing(null);
            query.refetch();
          }}
        />
      )}
    </div>
  );
}

function AnnouncementDialog({
  item,
  onClose,
  onSaved,
}: {
  item: AnnouncementItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [body, setBody] = useState(item?.body ?? "");
  const [audience, setAudience] = useState(item?.audience ?? "all");
  const [publishAt, setPublishAt] = useState(
    item?.publish_at ? item.publish_at.slice(0, 16) : "",
  );
  const [error, setError] = useState("");
  const { mutate: save, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!title || !body) {
      setError("标题和内容不能为空");
      return;
    }
    const values = {
      title,
      body,
      audience,
      publish_at: publishAt ? new Date(publishAt).toISOString() : null,
    };
    save(
      item
        ? {
            url: `ops/announcements/${item.id}`,
            method: "patch",
            values,
          }
        : {
            url: "ops/announcements",
            method: "post",
            values,
          },
      {
        onSuccess: onSaved,
        onError: () => setError("保存失败"),
      },
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="bg-white p-6 w-[520px] max-h-[80vh] overflow-auto"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {item ? "编辑公告" : "新建公告"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-neutral-400)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              标题
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              内容
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                受众
              </label>
              <select
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                {AUDIENCE_PRESETS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                发布时间（留空 = 草稿）
              </label>
              <input
                type="datetime-local"
                value={publishAt}
                onChange={(e) => setPublishAt(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              取消
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={mutation.isPending}
              className="px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              {mutation.isPending ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
