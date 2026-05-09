// 1:1 还原 ui/agent-pc.html#my-profile 个人信息
// PoC 阶段使用 mock；后端 GET /api/v1/agent/me + GET /api/v1/agent/me/performance 待补
// v1.6.7 — 加 E6 AI 评分趋势卡（接 /agent/me/scoring-trend）
import { useCustom, useGetIdentity } from "@refinedev/core";
import type { AuthUser } from "../../../providers/auth-provider";

interface ScoringTrendResp {
  avg_score_30d: number;
  avg_talk: number;
  avg_emotion: number;
  avg_conversion: number;
  recent: { call_id: number; score: number; talk: number; emotion: number; conversion: number }[];
}

interface TodayStat {
  label: string;
  value: string | number;
  change: string;
  tone: "up" | "down" | "neutral";
}

const TODAY_STATS: TodayStat[] = [
  { label: "今日通话", value: 12, change: "次", tone: "neutral" },
  { label: "接通率", value: "75%", change: "↑ +5% vs 昨日", tone: "up" },
  { label: "今日承诺缴费", value: 3, change: "↑ +1 vs 昨日", tone: "up" },
  { label: "今日催收金额", value: "¥8,400", change: "↑ 已结清 1 件", tone: "up" },
  { label: "AI话术采纳率", value: "68%", change: "今日 11/16 次", tone: "neutral" },
];

interface InfoItem {
  label: string;
  value: string;
  valueColor?: string;
}

const MONTHLY_INFO: InfoItem[] = [
  { label: "总通话量", value: "187 次" },
  { label: "平均接通率", value: "71.6%" },
  { label: "承诺缴费笔数", value: "42 笔" },
  { label: "实际缴费转化", value: "28 笔 (66.7%)" },
  { label: "催收总金额", value: "¥112,600", valueColor: "var(--color-success)" },
  { label: "AI话术采纳率", value: "62.4%" },
  { label: "平均通话时长", value: "4分32秒" },
  { label: "升级案件数", value: "3 件" },
];

const SCORES = [
  { label: "通话效率", score: 78, color: "var(--color-primary)" },
  { label: "转化能力", score: 72, color: "var(--color-success)" },
  { label: "AI协作度", score: 62, color: "var(--color-purple, #8b5cf6)" },
  { label: "综合得分", score: 74, color: "var(--color-warning)", strong: true },
];

export function AgentProfilePage() {
  const { data: user } = useGetIdentity<AuthUser>();
  const initials = user?.name?.slice(0, 1) ?? "刘";
  const name = user?.name ?? "刘晓雯";

  // v1.6.7 — E6 评分趋势
  const { query: scoringQuery } = useCustom<ScoringTrendResp>({
    url: "agent/me/scoring-trend", method: "get",
  });
  const scoring = scoringQuery.data?.data;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">个人信息</div>
          <div className="page-subtitle">账号管理 &amp; 绩效概览</div>
        </div>
        <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => alert("编辑资料 — 联系管理员")}>
          编辑信息
        </button>
      </div>

      {/* Profile Card */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 16,
          background: "white", border: "1px solid var(--color-neutral-200)",
          borderRadius: 8, padding: 20, marginBottom: 20,
        }}
      >
        <div
          style={{
            width: 64, height: 64, borderRadius: "50%",
            background: "var(--color-primary)", color: "white",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 24, fontWeight: 600,
          }}
        >
          {initials}
        </div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600, color: "var(--color-neutral-900)" }}>{name}</div>
          <div style={{ fontSize: 13, color: "var(--color-neutral-600)", marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-success)", display: "inline-block" }} />
            在线
            <span style={{ color: "var(--color-neutral-300)" }}>·</span>
            催收员 · 绿城锦绣物业
            <span style={{ color: "var(--color-neutral-300)" }}>·</span>
            工号：LJ-2024-088
          </div>
          <div style={{ fontSize: 12.5, color: "var(--color-neutral-600)", marginTop: 6 }}>
            入职日期：2024-03-15 &nbsp;·&nbsp; 工龄：1年1个月
          </div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>今日登录</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-neutral-900)" }}>09:02:14</div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-600)", marginTop: 4 }}>
            在线时长 <strong>5h 26m</strong>
          </div>
        </div>
      </div>

      {/* Today Stats */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        {TODAY_STATS.map((s) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={typeof s.value === "string" && s.value.startsWith("¥") ? { fontSize: 22 } : undefined}>{s.value}</div>
            <div className={`stat-change ${s.tone}`}>{s.change}</div>
          </div>
        ))}
      </div>

      {/* v1.6.7 — E6 AI 评分趋势卡 */}
      {scoring && (
        <div className="ds-card" style={{ marginBottom: 20 }} data-testid="agent-scoring-trend">
          <div
            style={{
              padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-200)",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}
          >
            <span style={{ fontWeight: 600, fontSize: 14 }}>🎯 AI 通话评分（近 30 天）</span>
            <span style={{
              fontSize: 24, fontWeight: 700,
              color: scoring.avg_score_30d >= 80 ? "#15803d" : scoring.avg_score_30d >= 60 ? "#1d4ed8" : "#b45309",
              fontFamily: "var(--font-mono, monospace)",
            }}>
              {scoring.avg_score_30d}
              <span style={{ fontSize: 12, color: "#6b7280", fontWeight: 400, marginLeft: 4 }}>/ 100</span>
            </span>
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
              <ScoreCell label="话术" value={scoring.avg_talk} color="#1A56DB" />
              <ScoreCell label="情绪管理" value={scoring.avg_emotion} color="#7e3af2" />
              <ScoreCell label="转化能力" value={scoring.avg_conversion} color="#059669" />
            </div>
            {scoring.recent.length > 0 && (
              <>
                <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>近 10 通通话评分</div>
                <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 40 }}>
                  {scoring.recent.map((r) => (
                    <div
                      key={r.call_id}
                      title={`通话 #${r.call_id} · ${r.score} 分（话术 ${r.talk} / 情绪 ${r.emotion} / 转化 ${r.conversion}）`}
                      style={{
                        flex: 1,
                        height: `${Math.max(8, (r.score / 100) * 40)}px`,
                        background: r.score >= 80 ? "#bbf7d0" : r.score >= 60 ? "#bfdbfe" : "#fde68a",
                        borderRadius: "2px 2px 0 0",
                        cursor: "pointer",
                      }}
                    />
                  ))}
                </div>
              </>
            )}
            {scoring.recent.length === 0 && (
              <div style={{ textAlign: "center", color: "#9ca3af", fontSize: 12, padding: 12 }}>
                还没有通话数据，发起通话后这里会自动累计评分
              </div>
            )}
          </div>
        </div>
      )}

      {/* Monthly Performance */}
      <div className="ds-card">
        <div
          style={{
            padding: "12px 16px", borderBottom: "1px solid var(--color-neutral-200)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}
        >
          <span style={{ fontWeight: 600, fontSize: 14 }}>本月绩效摘要 (2026年5月)</span>
          <span className="ds-badge ds-badge-blue">评级：良好</span>
        </div>
        <div style={{ padding: 16 }}>
          <div
            style={{
              display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: 12, marginBottom: 20,
            }}
          >
            {MONTHLY_INFO.map((it) => (
              <div key={it.label} style={{ padding: 8 }}>
                <div style={{ fontSize: 12, color: "var(--color-neutral-600)", marginBottom: 4 }}>{it.label}</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: it.valueColor ?? "var(--color-neutral-900)" }}>{it.value}</div>
              </div>
            ))}
            {/* 通话分钟配额（特殊高亮） */}
            <div
              style={{
                background: "#fff7ed", borderRadius: 6, padding: 8,
                border: "1px solid #fed7aa",
              }}
            >
              <div style={{ fontSize: 12, color: "#92400e", marginBottom: 4 }}>本月通话分钟</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "#d97706" }}>
                847 <span style={{ fontSize: 13, fontWeight: 400, color: "#92400e" }}>分钟</span>
              </div>
              <div style={{ background: "#fde68a", borderRadius: 3, height: 4, marginTop: 6, overflow: "hidden" }}>
                <div style={{ background: "#d97706", height: "100%", width: "84.7%", borderRadius: 3 }} />
              </div>
              <div style={{ fontSize: 11, color: "#92400e", marginTop: 3 }}>
                个人配额 1,000 分 · 已用 84.7%
              </div>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>综合评分</div>
            {SCORES.map((s) => (
              <div
                key={s.label}
                style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}
              >
                <span style={{ fontSize: 12.5, color: "var(--color-neutral-600)", width: 80 }}>{s.label}</span>
                <div style={{ flex: 1, background: "var(--color-neutral-200)", borderRadius: 4, height: 8, overflow: "hidden" }}>
                  <div style={{ background: s.color, height: "100%", width: `${s.score}%`, borderRadius: 4 }} />
                </div>
                <span
                  style={{
                    fontSize: 12.5, width: 32,
                    fontWeight: s.strong ? 700 : 600,
                    color: s.strong ? s.color : undefined,
                  }}
                >
                  {s.score}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoreCell({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ padding: 10, background: "#f9fafb", borderRadius: 6, textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: "var(--font-mono, monospace)" }}>{value}</div>
    </div>
  );
}
