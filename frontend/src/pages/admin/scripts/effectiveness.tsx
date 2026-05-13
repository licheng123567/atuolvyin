// 物业管理员 - 话术效果看板（PRD §3.11 / L2046）
// v1.5.7 — 1:1 还原 ui/admin-scripts-effectiveness.html
import { useCustom } from "@refinedev/core";
import { ArrowLeft, BarChart3 } from "lucide-react";
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

  // 顶部 4 张统计卡 — 前端聚合
  const totalShown = items.reduce((s, it) => s + it.total_shown, 0);
  const totalAdopted = items.reduce((s, it) => s + it.total_adopted, 0);
  const totalSupervised = items.reduce((s, it) => s + it.total_supervised, 0);
  const totalGood = items.reduce((s, it) => s + it.total_good, 0);
  const overallAdoption = totalShown > 0 ? (totalAdopted / totalShown) * 100 : null;
  const overallGood = totalSupervised > 0 ? (totalGood / totalSupervised) * 100 : null;
  const aGradeCount = items.filter((it) => it.composite_grade === "A").length;

  return (
    <div>
      <Link to="/admin/scripts" className="back-link" style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13.5, textDecoration: "none", marginBottom: 12 }}>
        <ArrowLeft className="w-3.5 h-3.5" /> 返回话术库
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <BarChart3 style={{ width: 22, height: 22, color: "var(--color-primary)" }} />
        <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--color-neutral-900)", margin: 0 }}>
          话术效果看板
        </h1>
        <span style={{ fontSize: 13, color: "var(--color-neutral-500)" }}>
          共 {items.length} 条话术
        </span>
      </div>

      {/* 筛选条 */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <select
          className="filter-select"
          value={periodDays}
          onChange={(e) => setPeriodDays(Number(e.target.value))}
        >
          {PERIOD_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        <select
          className="filter-select"
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
        >
          <option value="">全部异议类型</option>
          {TRIGGER_INTENTS.map((it) => (
            <option key={it} value={it}>
              {it}
            </option>
          ))}
        </select>
      </div>

      {/* 4 张统计卡 */}
      <div className="stats-band">
        <div className="stats-card">
          <div className="stats-card-label">推送总次数</div>
          <div className="stats-card-value">{totalShown.toLocaleString("zh-CN")}</div>
        </div>
        <div className="stats-card">
          <div className="stats-card-label">整体采用率</div>
          <div className="stats-card-value">
            {overallAdoption === null ? "—" : `${overallAdoption.toFixed(1)}%`}
            {totalAdopted > 0 && <span className="pct">/ {totalAdopted.toLocaleString("zh-CN")} 次</span>}
          </div>
        </div>
        <div className="stats-card">
          <div className="stats-card-label">督导好评率</div>
          <div className="stats-card-value">
            {overallGood === null ? "—" : `${overallGood.toFixed(1)}%`}
            {totalGood > 0 && <span className="pct">/ {totalGood.toLocaleString("zh-CN")} 次</span>}
          </div>
        </div>
        <div className="stats-card">
          <div className="stats-card-label">A 级话术</div>
          <div className="stats-card-value">
            {aGradeCount}
            <span className="pct">/ {items.length}</span>
          </div>
        </div>
      </div>

      {/* 表格 */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>话术</th>
              <th>异议类型</th>
              <th style={{ textAlign: "right" }}>推送次数</th>
              <th style={{ textAlign: "right" }}>采用率</th>
              <th style={{ textAlign: "right" }}>督导好评率</th>
              <th style={{ textAlign: "center" }}>综合评分</th>
              <th style={{ textAlign: "center" }}>评级</th>
              <th style={{ textAlign: "center" }}>状态</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}>
                  暂无话术数据
                </td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.template_id}>
                <td className="title-cell">{item.title}</td>
                <td>{item.trigger_intent}</td>
                <td style={{ textAlign: "right" }}>{item.total_shown}</td>
                <td style={{ textAlign: "right" }}>
                  {pct(item.adoption_rate)}
                  {item.total_shown > 0 && (
                    <span className="ratio-detail">
                      ({item.total_adopted}/{item.total_shown})
                    </span>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  {pct(item.good_ratio)}
                  {item.total_supervised > 0 && (
                    <span className="ratio-detail">
                      ({item.total_good}/{item.total_supervised})
                    </span>
                  )}
                </td>
                <td style={{ textAlign: "center" }}>
                  {item.composite_score === null ? "—" : item.composite_score.toFixed(2)}
                </td>
                <td style={{ textAlign: "center" }}>
                  {item.composite_grade ? (
                    <span className={`grade grade-${item.composite_grade.toLowerCase()}`}>
                      {item.composite_grade}
                    </span>
                  ) : (
                    <span style={{ color: "var(--color-neutral-400)" }}>—</span>
                  )}
                </td>
                <td style={{ textAlign: "center" }}>
                  <span className={`status-pill ${item.is_active ? "status-active" : "status-inactive"}`}>
                    {item.is_active ? "启用" : "禁用"}
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
