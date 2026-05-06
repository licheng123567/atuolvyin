// Sprint 10.5 — 平台超管 LLM Prompt 管理（PRD §L1969）
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Brain, Plus, X, Power, PowerOff } from "lucide-react";
import { useMemo, useState } from "react";

interface LLMPrompt {
  id: number;
  name: string;
  version: number;
  body: string;
  notes: string | null;
  is_active: boolean;
  created_by: number;
  created_at: string;
}

export function SuperLlmPromptsPage() {
  const { query } = useCustom<LLMPrompt[]>({
    url: "super/llm-prompts",
    method: "get",
  });
  const items = query.data?.data ?? [];

  const [showNew, setShowNew] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const groupedByName = useMemo(() => {
    const groups: Record<string, LLMPrompt[]> = {};
    for (const p of items) {
      (groups[p.name] ??= []).push(p);
    }
    return groups;
  }, [items]);

  const { mutate: toggle } = useCustomMutation();
  const setActive = (p: LLMPrompt, active: boolean) => {
    toggle(
      {
        url: `super/llm-prompts/${p.id}/active`,
        method: "patch",
        values: { is_active: active },
      },
      { onSuccess: () => query.refetch() },
    );
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">LLM Prompt 管理</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          {Object.keys(groupedByName).length} 组 · 共 {items.length} 版
        </span>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className="ml-auto flex items-center gap-1 px-3 py-2 text-sm font-medium text-white"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新建 Prompt 版本
        </button>
      </div>

      {Object.entries(groupedByName).map(([name, versions]) => (
        <div
          key={name}
          className="bg-white border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <div className="px-4 py-3 border-b border-[var(--color-neutral-100)]">
            <h3 className="text-sm font-semibold">{name}</h3>
            <p className="text-xs text-[var(--color-neutral-500)]">
              {versions.length} 个版本 · 当前激活：v
              {versions.find((v) => v.is_active)?.version ?? "—"}
            </p>
          </div>
          {versions.map((p) => (
            <div
              key={p.id}
              className="px-4 py-3 border-b border-[var(--color-neutral-100)] last:border-b-0"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">v{p.version}</span>
                {p.is_active ? (
                  <span
                    className="px-2 py-0.5 text-xs rounded-full font-medium"
                    style={{
                      background: "var(--color-success-light)",
                      color: "var(--color-success)",
                    }}
                  >
                    激活中
                  </span>
                ) : (
                  <span className="text-xs text-[var(--color-neutral-400)]">
                    未激活
                  </span>
                )}
                <span className="text-xs text-[var(--color-neutral-400)]">
                  {p.created_at?.slice(0, 19).replace("T", " ")}
                </span>
                <button
                  type="button"
                  onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                  className="ml-auto text-xs text-[var(--color-primary)]"
                >
                  {expandedId === p.id ? "收起" : "查看正文"}
                </button>
                <button
                  type="button"
                  onClick={() => setActive(p, !p.is_active)}
                  className="text-sm text-[var(--color-primary)] flex items-center gap-1"
                  title={p.is_active ? "停用此版本" : "激活此版本（同名其他版本会自动停用）"}
                >
                  {p.is_active ? (
                    <PowerOff className="w-4 h-4" />
                  ) : (
                    <Power className="w-4 h-4" />
                  )}
                </button>
              </div>
              {expandedId === p.id && (
                <pre className="mt-2 p-3 text-xs bg-[var(--color-neutral-50)] rounded overflow-auto max-h-[300px] whitespace-pre-wrap">
                  {p.body}
                </pre>
              )}
              {p.notes && expandedId === p.id && (
                <p className="mt-1 text-xs text-[var(--color-neutral-500)]">
                  备注：{p.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      ))}

      {showNew && (
        <NewPromptDialog
          onClose={() => setShowNew(false)}
          onSaved={() => {
            setShowNew(false);
            query.refetch();
          }}
        />
      )}
    </div>
  );
}

function NewPromptDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const { mutate: create, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!name || !body) {
      setError("名称与正文不能为空");
      return;
    }
    create(
      {
        url: "super/llm-prompts",
        method: "post",
        values: { name, body, notes: notes || null },
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
        className="bg-white p-6 w-[600px] max-h-[80vh] overflow-auto"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">新建 Prompt 版本</h2>
          <button type="button" onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              Prompt 名称（同名将自动 +1 版本）
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例：intent_classifier"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              正文
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              className="w-full px-3 py-2 text-sm font-mono border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              备注（可选）
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="例：调整了温度参数 / 修复了误报"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2">
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
              {mutation.isPending ? "保存中…" : "新增版本"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
