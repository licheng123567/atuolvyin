// 督导个人 KPI 看板 — v1.5.7 ⭐⭐⭐
// 督导自己的本月产出快照：处置 L2 / 接管 / 复核改判 / 平均响应时长 / 团队 AI 采用率提升
import { Activity, BarChart3, Clock, ShieldCheck, TrendingUp, UserCheck } from "lucide-react";
import { useState } from "react";
import { HelpPanel } from "../../../components/ui/HelpPanel";

interface MonthlyKpi {
  month: string;
  l2_handled: number;
  l2_handled_delta: number;
  takeovers: number;
  reviews_corrected: number;
  reviews_total: number;
  avg_response_min: number;
  avg_response_delta: number;
  team_adoption_pct: number;
  team_adoption_delta: number;
  promise_followups: number;
  escalated_resolved: number;
}

const MOCK_KPI: MonthlyKpi = {
  month: "2026-05",
  l2_handled: 12,
  l2_handled_delta: 3,
  takeovers: 4,
  reviews_corrected: 8,
  reviews_total: 47,
  avg_response_min: 6.5,
  avg_response_delta: -2.1,
  team_adoption_pct: 82,
  team_adoption_delta: 5,
  promise_followups: 23,
  escalated_resolved: 6,
};

const MONTHS = ["2026-05", "2026-04", "2026-03", "2026-02"];

export function SupervisorMyKpiPage() {
  const [month, setMonth] = useState(MOCK_KPI.month);
  const k = MOCK_KPI; // mock：所有月份用同一份

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">我的工作表现</div>
          <div className="page-subtitle">督导本人本月各项产出，关联月度奖金 / 晋升评定</div>
        </div>
        <select className="filter-select" value={month} onChange={(e) => setMonth(e.target.value)}>
          {MONTHS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <HelpPanel
        tone="tip"
        dismissKey="/supervisor/my-kpi"
        title="督导 KPI 怎么算"
        bullets={[
          <><strong>L2 处置数</strong>：本月由你介入的 L2 风控事件总数（接管 / 强制结束 / 转法务都算），≥10 件为合格</>,
          <><strong>接管次数</strong>：「实时通话墙」上你执行的接管 + 强制结束动作；这个不是越多越好，过高说明催收员训练不到位</>,
          <><strong>复核改判率</strong>：本月你复核 N 通通话，其中改判 M 通；改判率 &gt; 30% 说明 AI 模型需要重训</>,
          <><strong>平均响应时长</strong>：从风控告警产生到你处置的平均分钟数，目标 ≤10 分钟</>,
          <><strong>团队 AI 采用率提升</strong>：上月 vs 本月，你带的小组 AI 推送话术采用率涨了多少；最能体现你培训质量</>,
        ]}
      />

      <div className="kpi-grid">
        <KpiCard icon={<ShieldCheck size={16} />} label="L2 处置" value={k.l2_handled} unit="件" delta={k.l2_handled_delta} tone="primary" />
        <KpiCard icon={<UserCheck size={16} />} label="接管/强制" value={k.takeovers} unit="次" tone="warn" hint="过高说明培训不到位" />
        <KpiCard icon={<Activity size={16} />} label="复核改判率" value={`${Math.round((k.reviews_corrected / k.reviews_total) * 100)}%`} hint={`${k.reviews_corrected}/${k.reviews_total} 通改判`} tone="info" />
        <KpiCard icon={<Clock size={16} />} label="平均响应" value={k.avg_response_min} unit="分钟" delta={k.avg_response_delta} tone="success" />
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginTop: 16 }}>
        <KpiCard icon={<TrendingUp size={16} />} label="团队 AI 采用率" value={`${k.team_adoption_pct}%`} delta={k.team_adoption_delta} tone="success" hint="上月 vs 本月" />
        <KpiCard icon={<BarChart3 size={16} />} label="承诺催付" value={k.promise_followups} unit="单" tone="info" hint="督促回访次数" />
        <KpiCard icon={<ShieldCheck size={16} />} label="升级案件" value={k.escalated_resolved} unit="件" tone="warn" hint="本月已结案" />
      </div>

      <div className="ds-card" style={{ marginTop: 24 }}>
        <div className="card-body" style={{ padding: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>近 6 个月趋势（mock）</h3>
          <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 120, paddingTop: 16 }}>
            {[8, 11, 9, 14, 15, 12].map((v, i) => (
              <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-primary)" }}>{v}</span>
                <div
                  style={{
                    width: "100%",
                    background: i === 5 ? "var(--color-primary)" : "var(--color-primary-light, #dbeafe)",
                    height: `${(v / 18) * 100}%`,
                    borderRadius: "4px 4px 0 0",
                  }}
                />
                <span style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>{`-${5 - i}月`}</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginTop: 12 }}>
            月度 L2 处置数对比，本月（高亮）{k.l2_handled} 件 ↑{k.l2_handled_delta} 件
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, unit, delta, hint, tone }: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  delta?: number;
  hint?: string;
  tone: "primary" | "info" | "success" | "warn";
}) {
  const colors: Record<string, string> = {
    primary: "var(--color-primary)",
    info: "#3b82f6",
    success: "var(--color-success)",
    warn: "var(--color-warning)",
  };
  const deltaUp = delta !== undefined && delta > 0;
  const deltaDown = delta !== undefined && delta < 0;
  return (
    <div className="stat-card">
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, color: colors[tone] }}>
        <span style={{ display: "inline-flex", alignItems: "center", flexShrink: 0 }}>{icon}</span>
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value" style={{ color: colors[tone] }}>
        {value}
        {unit && <span style={{ fontSize: 14, marginLeft: 2, fontWeight: 400 }}>{unit}</span>}
      </div>
      {delta !== undefined && (
        <div className={`stat-change ${deltaUp ? "up" : deltaDown ? "down" : ""}`}>
          {deltaUp && `↑ ${delta}`}
          {deltaDown && `↓ ${Math.abs(delta)}`}
          {!deltaUp && !deltaDown && "持平"}
          {" "}较上月
        </div>
      )}
      {hint && (
        <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 4 }}>{hint}</div>
      )}
    </div>
  );
}
