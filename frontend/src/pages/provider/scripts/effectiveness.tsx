// v0.7.0 — 服务商话术效果看板(对齐物业 admin/scripts/effectiveness)
//
// 数据源:GET /api/v1/provider/scripts/effectiveness
// 范围:本服务商私有 + 平台预置话术(三层归属规则)
import { useCustom } from "@refinedev/core";
import { BarChart3, Filter, Sparkles } from "lucide-react";
import { useState } from "react";

interface EffItem {
  template_id: number;
  title: string;
  trigger_intent: string;
  is_active: boolean;
  source: "platform" | "provider";
  total_shown: number;
  total_adopted: number;
  adoption_rate: number | null;
  total_supervised: number;
  total_good: number;
  good_ratio: number | null;
  composite_score: number | null;
  composite_grade: "A" | "B" | "C" | "D" | null;
  ai_score: number | null;
  ai_score_sample_count: number | null;
}

interface EffResp {
  period_days: number;
  items: EffItem[];
}

const PERIOD_OPTIONS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
];

const INTENT_OPTIONS = ["全部", "房屋质量", "经济困难", "服务不满", "联系困难", "其他"];

const GRADE_BADGE: Record<string, string> = {
  A: "ds-badge ds-badge-green",
  B: "ds-badge ds-badge-blue",
  C: "ds-badge ds-badge-orange",
  D: "ds-badge ds-badge-red",
};

function pct(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function ProviderScriptsEffectivenessPage() {
  const [periodDays, setPeriodDays] = useState(30);
  const [intent, setIntent] = useState("全部");

  const { query } = useCustom<EffResp>({
    url: "provider/scripts/effectiveness",
    method: "get",
    config: {
      query: {
        period_days: periodDays,
        ...(intent !== "全部" ? { intent } : {}),
      },
    },
  });

  const items = query.data?.data?.items ?? [];
  const aGrade = items.filter((it) => it.composite_grade === "A").length;
  const dGrade = items.filter((it) => it.composite_grade === "D").length;

  return (
    <div style={{ padding: 16 }}>
      <div className="page-header" style={{ marginBottom: 12 }}>
        <div>
          <div className="page-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <BarChart3 className="w-5 h-5" />
            话术效果看板
          </div>
          <div className="page-subtitle">
            采用率 / 督导好评率 / 综合评分(A-D)/ AI 评分(基于回款率)— 本服务商私有 + 平台预置
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Filter className="w-4 h-4 text-[var(--color-neutral-500)]" />
          <select
            className="form-control"
            style={{ height: 32, width: 130 }}
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
          >
            {PERIOD_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ height: 32, width: 130 }}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          >
            {INTENT_OPTIONS.map((i) => (
              <option key={i} value={i}>{i === "全部" ? "全部异议类型" : i}</option>
            ))}
          </select>
        </div>
      </div>

      <div
        style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 12,
        }}
      >
        <div className="ds-card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>话术总数</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{items.length}</div>
        </div>
        <div className="ds-card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>A 级话术</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4, color: "var(--color-success)" }}>
            {aGrade}
          </div>
        </div>
        <div className="ds-card" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>D 级话术(需复盘)</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4, color: "var(--color-danger)" }}>
            {dGrade}
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>话术</th>
              <th>异议类型</th>
              <th>来源</th>
              <th style={{ textAlign: "right" }}>推送</th>
              <th style={{ textAlign: "right" }}>采用率</th>
              <th style={{ textAlign: "right" }}>好评率</th>
              <th style={{ textAlign: "center" }}>综合评分</th>
              <th
                style={{ textAlign: "center" }}
                title="AI 评分(0-100):基于近 30 天案件回款率 70% + 采用率 30%,定时任务每 6h 重算"
              >
                <Sparkles className="inline w-3 h-3" /> AI 评分
              </th>
              <th style={{ textAlign: "center" }}>评级</th>
              <th style={{ textAlign: "center" }}>状态</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={10} style={{ padding: 32, textAlign: "center", color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={10} style={{ padding: 32, textAlign: "center", color: "#9ca3af" }}>
                  暂无话术数据 — 请先到话术库新增
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.template_id}>
                <td className="title-cell" style={{ maxWidth: 280 }}>{it.title}</td>
                <td>{it.trigger_intent}</td>
                <td>
                  <span
                    className={
                      it.source === "platform" ? "ds-badge ds-badge-gray" : "ds-badge ds-badge-blue"
                    }
                    style={{ fontSize: 10 }}
                  >
                    {it.source === "platform" ? "平台预置" : "本服务商"}
                  </span>
                </td>
                <td style={{ textAlign: "right" }}>{it.total_shown}</td>
                <td style={{ textAlign: "right" }}>{pct(it.adoption_rate)}</td>
                <td style={{ textAlign: "right" }}>{pct(it.good_ratio)}</td>
                <td style={{ textAlign: "center" }}>
                  {it.composite_score === null ? "—" : it.composite_score.toFixed(2)}
                </td>
                <td style={{ textAlign: "center" }}>
                  {it.ai_score === null ? (
                    <span style={{ color: "#9ca3af", fontSize: 12 }}>
                      {it.ai_score_sample_count != null && it.ai_score_sample_count > 0
                        ? `样本不足(${it.ai_score_sample_count})`
                        : "—"}
                    </span>
                  ) : (
                    <span
                      style={{
                        fontWeight: 600,
                        color: it.ai_score >= 70 ? "#059669" : it.ai_score >= 40 ? "#d97706" : "#dc2626",
                      }}
                      title={
                        it.ai_score_sample_count != null
                          ? `样本数:${it.ai_score_sample_count}`
                          : undefined
                      }
                    >
                      {it.ai_score.toFixed(1)}
                      {it.ai_score_sample_count != null && it.ai_score_sample_count < 10 && (
                        <span style={{ fontSize: 10, color: "#d97706", marginLeft: 2 }}>⚠</span>
                      )}
                    </span>
                  )}
                </td>
                <td style={{ textAlign: "center" }}>
                  {it.composite_grade ? (
                    <span className={GRADE_BADGE[it.composite_grade]}>
                      {it.composite_grade}
                    </span>
                  ) : (
                    <span style={{ color: "#9ca3af" }}>—</span>
                  )}
                </td>
                <td style={{ textAlign: "center" }}>
                  <span
                    className={
                      it.is_active ? "ds-badge ds-badge-green" : "ds-badge ds-badge-gray"
                    }
                    style={{ fontSize: 10 }}
                  >
                    {it.is_active ? "启用" : "禁用"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ProviderScriptsEffectivenessPage;
