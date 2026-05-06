import { useGo, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft, Save, Scale } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  LEGAL_STAGES,
  formatStage,
  getStageColor,
} from "./helpers";

interface CollectionCaseRef {
  id: number;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  owner_name: string;
  owner_phone_masked: string;
}

interface LegalCaseDetail {
  id: number;
  case_id: number;
  stage: string;
  amount_disputed: string | null;
  lawyer_name: string | null;
  law_firm: string | null;
  next_milestone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  owner_name: string | null;
  owner_phone_masked: string | null;
  collection_case: CollectionCaseRef | null;
}

interface FormState {
  stage: string;
  lawyer_name: string;
  law_firm: string;
  next_milestone: string;
  amount_disputed: string;
  notes: string;
}

function detailToForm(detail: LegalCaseDetail): FormState {
  return {
    stage: detail.stage,
    lawyer_name: detail.lawyer_name ?? "",
    law_firm: detail.law_firm ?? "",
    next_milestone: detail.next_milestone ?? "",
    amount_disputed: detail.amount_disputed ?? "",
    notes: detail.notes ?? "",
  };
}

export function LegalCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<LegalCaseDetail>({
    resource: "legal/cases",
    id: id ?? "",
  });
  const detail = query.data?.data;

  // Derived-state form: starts as null, becomes initialized form once
  // we have detail. Subsequent edits override the derived value.
  const [overrideForm, setOverrideForm] = useState<FormState | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const form: FormState = overrideForm ?? (detail ? detailToForm(detail) : {
    stage: "pending_eval",
    lawyer_name: "",
    law_firm: "",
    next_milestone: "",
    amount_disputed: "",
    notes: "",
  });

  const setForm = (next: FormState) => setOverrideForm(next);

  const { mutate: update, mutation: updateMutation } = useUpdate();
  const saving = updateMutation.isPending;

  const handleSave = () => {
    if (!detail) return;
    setErrorMsg("");
    update(
      {
        resource: "legal/cases",
        id: detail.id,
        values: {
          stage: form.stage,
          lawyer_name: form.lawyer_name || null,
          law_firm: form.law_firm || null,
          next_milestone: form.next_milestone || null,
          amount_disputed: form.amount_disputed || null,
          notes: form.notes || null,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setOverrideForm(null); // re-derive from refetched detail
          query.refetch();
        },
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "保存失败");
        },
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-8 text-sm text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!detail) {
    return <div className="p-8 text-sm text-[var(--color-danger)]">法务案件不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/legal/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <Scale className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          法务案件详情
        </h1>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={getStageColor(detail.stage)}
        >
          {formatStage(detail.stage)}
        </span>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "340px 1fr" }}>
        {/* Left: source case info */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5">
            <h3 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">
              关联催收案件
            </h3>
            {detail.collection_case ? (
              <dl className="text-sm space-y-2">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">业主</dt>
                  <dd className="font-medium">
                    {detail.collection_case.owner_name}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">手机</dt>
                  <dd>{detail.collection_case.owner_phone_masked}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">案件 ID</dt>
                  <dd>#{detail.collection_case.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">欠费金额</dt>
                  <dd className="font-medium">
                    {detail.collection_case.amount_owed
                      ? `¥${detail.collection_case.amount_owed}`
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">逾期月数</dt>
                  <dd>{detail.collection_case.months_overdue ?? "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">原案件状态</dt>
                  <dd>{detail.collection_case.stage}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">
                关联案件已删除
              </p>
            )}
          </div>
        </div>

        {/* Right: editable form */}
        <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5 space-y-4">
          <h3 className="text-sm font-semibold text-[var(--color-neutral-900)]">
            法务进度
          </h3>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              当前阶段
            </label>
            <select
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              {LEGAL_STAGES.map((s) => (
                <option key={s} value={s}>
                  {formatStage(s)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                律师姓名
              </label>
              <input
                type="text"
                value={form.lawyer_name}
                onChange={(e) =>
                  setForm({ ...form, lawyer_name: e.target.value })
                }
                placeholder="例：王律师"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                律师事务所
              </label>
              <input
                type="text"
                value={form.law_firm}
                onChange={(e) => setForm({ ...form, law_firm: e.target.value })}
                placeholder="例：某某律师事务所"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                涉案金额(元)
              </label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={form.amount_disputed}
                onChange={(e) =>
                  setForm({ ...form, amount_disputed: e.target.value })
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                下一里程碑
              </label>
              <input
                type="text"
                value={form.next_milestone}
                onChange={(e) =>
                  setForm({ ...form, next_milestone: e.target.value })
                }
                placeholder="例：2026-06-15 开庭"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              备注
            </label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={4}
              placeholder="案件进展、举证情况等"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {errorMsg && (
            <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
          )}

          <div className="flex items-center justify-between pt-2">
            {savedAt ? (
              <p className="text-xs text-[var(--color-success)]">
                已保存 ({savedAt})
              </p>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <Save className="w-4 h-4" />
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
