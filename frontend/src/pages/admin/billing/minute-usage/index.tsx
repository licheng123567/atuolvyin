// v0.5.9 — 物业管理员通话计费页(分钟数消费金额)
//
// 数据源:
//   GET /api/v1/admin/billing/minute-summary?year_month=YYYY-MM
//   GET /api/v1/admin/billing/minute-trend?months=6
//
// 设计:顶部 4 KPI 卡(实时/事后/总额/剩余配额)+ 中部 6 月堆叠条形图 + 底部说明
import { useCustom } from "@refinedev/core";
import { Activity, Clock, Phone, TrendingUp } from "lucide-react";
import { useState } from "react";

interface MinuteSummary {
  year_month: string;
  used_minutes: number;
  realtime_minutes: number;
  post_minutes: number;
  price_live: string;
  price_post: string;
  amount_realtime: string;
  amount_post: string;
  amount_total: string;
  quota_total: number | null;
  quota_remaining: number | null;
}

interface MinuteTrendItem {
  year_month: string;
  realtime_minutes: number;
  post_minutes: number;
  amount: string;
}

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function AdminBillingMinuteUsagePage() {
  const [ym, setYm] = useState(currentMonth());

  const { query: summaryQ } = useCustom<MinuteSummary>({
    url: "admin/billing/minute-summary",
    method: "get",
    config: { query: { year_month: ym } },
  });

  const { query: trendQ } = useCustom<MinuteTrendItem[]>({
    url: "admin/billing/minute-trend",
    method: "get",
    config: { query: { months: 6 } },
  });

  const summary = summaryQ.data?.data;
  const trend = trendQ.data?.data ?? [];

  // 配额使用率
  const quotaPct =
    summary?.quota_total && summary.quota_total > 0
      ? Math.round((summary.used_minutes / summary.quota_total) * 100)
      : null;
  const quotaWarn = quotaPct !== null && quotaPct >= 80;

  // 趋势图最大值(用于条形高度归一化)
  const maxTotalMin = Math.max(
    1,
    ...trend.map((t) => t.realtime_minutes + t.post_minutes),
  );

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Phone className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">通话计费</h1>
        <span className="text-sm text-[var(--color-neutral-500)]">本月分钟消费 + 趋势</span>
        <input
          type="month"
          value={ym}
          onChange={(e) => setYm(e.target.value)}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
        />
      </div>

      {/* KPI 4 卡 */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard
          icon={<Clock className="w-5 h-5" />}
          title="实时通话"
          value={`${summary?.realtime_minutes ?? 0} 分钟`}
          sub={`¥${summary?.amount_realtime ?? "0.00"} · 单价 ¥${summary?.price_live ?? "0.5"}/分`}
          color="#1A56DB"
        />
        <KpiCard
          icon={<Activity className="w-5 h-5" />}
          title="事后上传"
          value={`${summary?.post_minutes ?? 0} 分钟`}
          sub={`¥${summary?.amount_post ?? "0.00"} · 单价 ¥${summary?.price_post ?? "0.3"}/分`}
          color="#D97706"
        />
        <KpiCard
          icon={<TrendingUp className="w-5 h-5" />}
          title="本月总额"
          value={`¥${summary?.amount_total ?? "0.00"}`}
          sub={`${summary?.used_minutes ?? 0} 分钟合计`}
          color="#059669"
          emphasize
        />
        <KpiCard
          icon={<Clock className="w-5 h-5" />}
          title="剩余配额"
          value={
            summary?.quota_total
              ? `${summary.quota_remaining} / ${summary.quota_total} 分`
              : "未设配额"
          }
          sub={quotaPct !== null ? `已用 ${quotaPct}%` : "可联系平台 OPS 配置"}
          color={quotaWarn ? "#E02424" : "#6B7280"}
        />
      </div>

      {/* 趋势图(简化 SVG 堆叠条) */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4">
        <div className="text-sm font-medium text-[var(--color-neutral-700)] mb-3">
          近 6 月分钟趋势(实时 蓝 / 事后 橙)
        </div>
        {trendQ.isLoading ? (
          <div className="text-sm text-[var(--color-neutral-500)]">加载中…</div>
        ) : (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 16, height: 200, padding: "0 8px" }}>
            {trend.map((t) => {
              const total = t.realtime_minutes + t.post_minutes;
              const barH = (total / maxTotalMin) * 160;
              const rtH = total === 0 ? 0 : (t.realtime_minutes / total) * barH;
              const ptH = total === 0 ? 0 : (t.post_minutes / total) * barH;
              return (
                <div key={t.year_month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginBottom: 4 }}>
                    ¥{t.amount}
                  </div>
                  <div
                    style={{
                      width: "100%", maxWidth: 60, display: "flex",
                      flexDirection: "column", justifyContent: "flex-end",
                      height: 160, borderRadius: 4, overflow: "hidden",
                    }}
                  >
                    {ptH > 0 && (
                      <div style={{ height: ptH, background: "#D97706" }} title={`事后 ${t.post_minutes} 分`} />
                    )}
                    {rtH > 0 && (
                      <div style={{ height: rtH, background: "#1A56DB" }} title={`实时 ${t.realtime_minutes} 分`} />
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--color-neutral-600)", marginTop: 6 }}>
                    {t.year_month.slice(5)}月
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="text-xs text-[var(--color-neutral-500)] bg-[var(--color-neutral-50)] rounded p-3 leading-relaxed">
        💡 <strong>单价说明</strong>:实时通话(live)¥{summary?.price_live ?? "0.5"}/分,事后上传(post_upload)
        ¥{summary?.price_post ?? "0.3"}/分。单价由平台 OPS 在 BillingPricing 表统一维护,租户不可改。
        配额由租户套餐决定,超额按 fragments 计费(详见 PRD §20.1.1)。
      </div>
    </div>
  );
}

function KpiCard({
  icon, title, value, sub, color, emphasize,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  sub: string;
  color: string;
  emphasize?: boolean;
}) {
  return (
    <div
      className="bg-white border rounded-lg p-4"
      style={{
        borderColor: emphasize ? color : "var(--color-neutral-200)",
        borderLeftWidth: emphasize ? 4 : 1,
        borderLeftColor: color,
      }}
    >
      <div className="flex items-center gap-2 text-sm text-[var(--color-neutral-600)] mb-2">
        <span style={{ color }}>{icon}</span>
        {title}
      </div>
      <div className="text-2xl font-bold text-[var(--color-neutral-900)]" style={{ color: emphasize ? color : undefined }}>
        {value}
      </div>
      <div className="text-xs text-[var(--color-neutral-500)] mt-1">{sub}</div>
    </div>
  );
}

export default AdminBillingMinuteUsagePage;
