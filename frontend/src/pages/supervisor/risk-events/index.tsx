// Sprint 9.4 — 主管督导风控事件时间线（PRD §L4068）
import { useCustom, useCustomMutation } from "@refinedev/core";
import { AlertTriangle, MessageSquare, Save } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

interface RiskEventItem {
  id: number;
  call_id: number;
  case_id: number | null;
  level: "L1" | "L2" | "L3";
  category: string;
  intervention: string;
  trigger_text: string | null;
  audio_offset_ms: number | null;
  occurred_at: string;
  disposition_note: string | null;
  disposition_at: string | null;
  agent_user_id: number | null;
  agent_name: string | null;
}

const LEVEL_BADGE: Record<string, { bg: string; color: string }> = {
  L1: { bg: "var(--color-warning-light)", color: "var(--color-warning)" },
  L2: { bg: "var(--color-warning-light)", color: "#a16207" },
  L3: { bg: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function SupervisorRiskEventsPage() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("");
  const [period, setPeriod] = useState(7);

  const { query, queryResult } = useCustom<RiskEventItem[]>({
    url: "supervisor/risk-events",
    method: "get",
    config: {
      query: {
        period_days: period,
        ...(level ? { level } : {}),
      },
    },
  });
  const items = query.data?.data ?? [];

  const refetch = (queryResult ?? query)?.refetch;
  const { mutate: annotate } = useCustomMutation();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [noteDraft, setNoteDraft] = useState("");

  const startEdit = (it: RiskEventItem) => {
    setEditingId(it.id);
    setNoteDraft(it.disposition_note ?? "");
  };
  const saveNote = (id: number) => {
    annotate(
      {
        url: `supervisor/risk-events/${id}`,
        method: "patch",
        values: { note: noteDraft },
      },
      {
        onSuccess: () => {
          setEditingId(null);
          refetch?.();
        },
      },
    );
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-[var(--color-danger)]" />
        <h1 className="text-xl font-semibold">风控事件时间线</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {items.length} 条
        </span>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="">全部等级</option>
            <option value="L1">L1 提示</option>
            <option value="L2">L2 督导接管</option>
            <option value="L3">L3 强制中止</option>
          </select>
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value={1}>近 1 天</option>
            <option value={7}>近 7 天</option>
            <option value={30}>近 30 天</option>
            <option value={90}>近 90 天</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        {query.isLoading && (
          <p className="p-4 text-sm text-[var(--color-neutral-400)]">加载中…</p>
        )}
        {!query.isLoading && items.length === 0 && (
          <p className="p-4 text-sm text-[var(--color-neutral-400)]">
            该时间窗内无风控事件
          </p>
        )}
        {items.map((it) => {
          const badge = LEVEL_BADGE[it.level] ?? LEVEL_BADGE.L1;
          return (
            <div
              key={it.id}
              className="p-4 border-b border-[var(--color-neutral-100)] last:border-b-0"
            >
              <div className="flex items-center gap-3">
                <span
                  className="px-2 py-0.5 text-xs rounded-full font-medium"
                  style={{ background: badge.bg, color: badge.color }}
                >
                  {it.level}
                </span>
                <span className="text-sm font-medium text-[var(--color-neutral-700)]">
                  {it.category}
                </span>
                <span className="text-xs text-[var(--color-neutral-400)]">
                  {it.intervention}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    navigate(`/supervisor/reviews/${it.call_id}`)
                  }
                  className="ml-auto text-xs text-[var(--color-primary)]"
                >
                  跳转复核 →
                </button>
              </div>
              {it.trigger_text && (
                <p className="mt-2 text-sm text-[var(--color-neutral-700)]">
                  「{it.trigger_text}」
                </p>
              )}
              <div className="mt-2 flex items-center gap-3 text-xs text-[var(--color-neutral-500)]">
                <span>坐席：{it.agent_name ?? "—"}</span>
                <span>·</span>
                <span>{it.occurred_at?.slice(0, 19).replace("T", " ")}</span>
                {it.audio_offset_ms !== null && (
                  <>
                    <span>·</span>
                    <span>音频 {(it.audio_offset_ms / 1000).toFixed(1)}s</span>
                  </>
                )}
              </div>

              <div className="mt-3 pl-2 border-l-2 border-[var(--color-neutral-200)]">
                {editingId === it.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={noteDraft}
                      onChange={(e) => setNoteDraft(e.target.value)}
                      rows={2}
                      placeholder="处置备注：与坐席沟通要点、改进措施等"
                      className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                      style={{ borderRadius: "var(--radius-md)" }}
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => saveNote(it.id)}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-white"
                        style={{
                          background: "var(--color-primary)",
                          borderRadius: "var(--radius-sm)",
                        }}
                      >
                        <Save className="w-3 h-3" />
                        保存
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="px-2 py-1 text-xs text-[var(--color-neutral-500)]"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : it.disposition_note ? (
                  <div className="flex items-start gap-2 text-sm">
                    <MessageSquare className="w-4 h-4 mt-0.5 text-[var(--color-primary)]" />
                    <div className="flex-1">
                      <p className="text-[var(--color-neutral-700)]">
                        {it.disposition_note}
                      </p>
                      <p className="text-xs text-[var(--color-neutral-400)] mt-1">
                        处置于 {it.disposition_at?.slice(0, 19).replace("T", " ")}
                        <button
                          type="button"
                          onClick={() => startEdit(it)}
                          className="ml-2 text-[var(--color-primary)]"
                        >
                          编辑
                        </button>
                      </p>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEdit(it)}
                    className="text-xs text-[var(--color-primary)] flex items-center gap-1"
                  >
                    <MessageSquare className="w-3 h-3" />
                    添加处置备注
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
