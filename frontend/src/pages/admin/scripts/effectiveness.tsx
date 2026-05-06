// 物业管理员 - 话术库效果看板（PRD §3.11 / L2046）
import { useCustom } from "@refinedev/core";
import { BarChart3, ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { TRIGGER_INTENTS } from "./helpers";

interface EffectivenessItem {
  template_id: number;
  title: string;
  trigger_intent: string;
  is_active: boolean;
  total_shown: number;
  total_adopted: number;
  adoption_rate: number | null;
  total_supervised: number;
  total_good: number;
  good_ratio: number | null;
  composite_score: number | null;
  composite_grade: "A" | "B" | "C" | "D" | null;
}

interface EffectivenessOut {
  period_days: number;
  items: EffectivenessItem[];
}

const PERIOD_OPTIONS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
];

const GRADE_STYLE: Record<string, { bg: string; color: string }> = {
  A: { bg: "var(--color-success-light)", color: "var(--color-success)" },
  B: { bg: "var(--color-info-light)", color: "var(--color-info)" },
  C: { bg: "var(--color-warning-light)", color: "var(--color-warning)" },
  D: { bg: "var(--color-danger-light)", color: "var(--color-danger)" },
};

function pct(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function ScriptEffectivenessPage() {
  const [periodDays, setPeriodDays] = useState(30);
  const [intent, setIntent] = useState("");

  const { query } = useCustom<EffectivenessOut>({
    url: "admin/scripts/effectiveness",
    method: "get",
    config: {
      query: { period_days: periodDays, ...(intent ? { intent } : {}) },
    },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];

  return (
    <div className="p-6">
      <Link
        to="/admin/scripts"
        className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)] mb-3"
      >
        <ArrowLeft className="w-4 h-4" /> 返回话术库
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            话术效果看板
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {items.length} 条话术
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <select
          value={periodDays}
          onChange={(e) => setPeriodDays(Number(e.target.value))}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          {PERIOD_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        <select
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部异议类型</option>
          {TRIGGER_INTENTS.map((it) => (
            <option key={it} value={it}>
              {it}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">话术</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">异议类型</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">推送次数</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">采用率</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">督导好评率</th>
              <th className="px-4 py-3 text-center font-medium text-[var(--color-neutral-600)]">综合评分</th>
              <th className="px-4 py-3 text-center font-medium text-[var(--color-neutral-600)]">评级</th>
              <th className="px-4 py-3 text-center font-medium text-[var(--color-neutral-600)]">状态</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {query.isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  暂无话术数据
                </td>
              </tr>
            )}
            {items.map((item) => {
              const gradeStyle =
                item.composite_grade && GRADE_STYLE[item.composite_grade];
              return (
                <tr key={item.template_id} className="hover:bg-[var(--color-neutral-50)]">
                  <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                    {item.title}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {item.trigger_intent}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--color-neutral-600)]">
                    {item.total_shown}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--color-neutral-600)]">
                    {pct(item.adoption_rate)}
                    {item.total_shown > 0 && (
                      <span className="ml-1 text-xs text-[var(--color-neutral-400)]">
                        ({item.total_adopted}/{item.total_shown})
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--color-neutral-600)]">
                    {pct(item.good_ratio)}
                    {item.total_supervised > 0 && (
                      <span className="ml-1 text-xs text-[var(--color-neutral-400)]">
                        ({item.total_good}/{item.total_supervised})
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-[var(--color-neutral-700)]">
                    {item.composite_score === null
                      ? "—"
                      : item.composite_score.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.composite_grade ? (
                      <span
                        className="inline-flex w-6 h-6 items-center justify-center rounded-full text-xs font-bold"
                        style={
                          gradeStyle
                            ? { background: gradeStyle.bg, color: gradeStyle.color }
                            : {}
                        }
                      >
                        {item.composite_grade}
                      </span>
                    ) : (
                      <span className="text-[var(--color-neutral-400)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                      style={
                        item.is_active
                          ? {
                              background: "var(--color-success-light)",
                              color: "var(--color-success)",
                            }
                          : {
                              background: "var(--color-neutral-100)",
                              color: "var(--color-neutral-500)",
                            }
                      }
                    >
                      {item.is_active ? "启用" : "禁用"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
