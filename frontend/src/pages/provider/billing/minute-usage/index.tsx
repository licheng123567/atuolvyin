// v0.5.9 — 服务商管理员跨租户分钟消费视图
//
// 数据源:
//   GET /api/v1/provider/billing/minute-summary?year_month=YYYY-MM
//
// 视角:「我接了 N 个租户,每个贡献多少分钟」 — 按金额降序排
import { useCustom } from "@refinedev/core";
import { Phone, TrendingUp } from "lucide-react";
import { useState } from "react";

interface TenantItem {
  tenant_id: number;
  tenant_name: string;
  realtime_minutes: number;
  post_minutes: number;
  amount: string;
}

interface ProviderMinuteSummary {
  year_month: string;
  tenants: TenantItem[];
  minute_total: number;
  amount_total: string;
  price_live: string;
  price_post: string;
}

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ProviderBillingMinuteUsagePage() {
  const [ym, setYm] = useState(currentMonth());

  const { query } = useCustom<ProviderMinuteSummary>({
    url: "provider/billing/minute-summary",
    method: "get",
    config: { query: { year_month: ym } },
  });

  const data = query.data?.data;
  const tenants = data?.tenants ?? [];
  const maxAmount = tenants.reduce(
    (max, t) => Math.max(max, parseFloat(t.amount) || 0),
    0,
  );

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Phone className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">分钟消费</h1>
        <span className="text-sm text-[var(--color-neutral-500)]">跨租户明细 — 我服务的所有租户本月用量</span>
        <input
          type="month"
          value={ym}
          onChange={(e) => setYm(e.target.value)}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
        />
      </div>

      {/* KPI */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-primary)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2">合作租户</div>
          <div className="text-2xl font-bold">{tenants.length}</div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            active 合作中的物业租户数
          </div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-warning)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2">本月总分钟</div>
          <div className="text-2xl font-bold text-[var(--color-warning)]">
            {data?.minute_total ?? 0}
          </div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">分钟(实时 + 事后)</div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-success)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-[var(--color-success)]" />
            本月总金额
          </div>
          <div className="text-2xl font-bold text-[var(--color-success)]">
            ¥{data?.amount_total ?? "0.00"}
          </div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            实时 ¥{data?.price_live ?? "0.5"} / 事后 ¥{data?.price_post ?? "0.3"}
          </div>
        </div>
      </div>

      {/* 租户明细 */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] text-sm font-medium">
          本月各租户消费明细 · 按金额降序
        </div>
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">加载中…</div>
        )}
        {!query.isLoading && tenants.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            本月暂无消费,或当前账号未绑定合作租户
          </div>
        )}
        {tenants.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-xs uppercase text-[var(--color-neutral-600)]">
              <tr>
                <th className="px-4 py-3 text-left">租户</th>
                <th className="px-4 py-3 text-right">实时分钟</th>
                <th className="px-4 py-3 text-right">事后分钟</th>
                <th className="px-4 py-3 text-right">金额</th>
                <th className="px-4 py-3 text-left w-1/3">占比</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {tenants.map((t) => {
                const amt = parseFloat(t.amount) || 0;
                const pct = maxAmount > 0 ? Math.round((amt / maxAmount) * 100) : 0;
                return (
                  <tr key={t.tenant_id} className="hover:bg-[var(--color-neutral-50)]">
                    <td className="px-4 py-3">
                      <span className="font-medium">{t.tenant_name}</span>
                      <span className="ml-2 text-xs text-[var(--color-neutral-400)]">
                        #{t.tenant_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {t.realtime_minutes}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {t.post_minutes}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-[var(--color-success)]">
                      ¥{t.amount}
                    </td>
                    <td className="px-4 py-3">
                      <div
                        style={{
                          height: 8,
                          background: "#F3F4F6",
                          borderRadius: 4,
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${pct}%`,
                            height: "100%",
                            background: "var(--color-primary)",
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-[var(--color-neutral-50)] text-sm font-medium">
              <tr>
                <td className="px-4 py-3">合计</td>
                <td className="px-4 py-3 text-right font-mono">
                  {tenants.reduce((s, t) => s + t.realtime_minutes, 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {tenants.reduce((s, t) => s + t.post_minutes, 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-[var(--color-success)]">
                  ¥{data?.amount_total ?? "0.00"}
                </td>
                <td className="px-4 py-3" />
              </tr>
            </tfoot>
          </table>
        )}
      </div>

      <div className="text-xs text-[var(--color-neutral-500)] bg-amber-50 border border-amber-200 rounded p-3">
        <strong>说明:</strong>本表统计的是「本服务商接手的 active 合作租户」当月的分钟消费。
        单价由平台 OPS 维护(BillingPricing 表);金额按业主侧实际拨打的实时 / 事后分钟拆分计算。
        服务商分成、回款明细另见结算报表(后续期次)。
      </div>
    </div>
  );
}

export default ProviderBillingMinuteUsagePage;
