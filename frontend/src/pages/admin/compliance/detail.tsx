// 物业管理员 - 合规月报详情（PRD §3.13）
// 使用 print-friendly 布局；用户用浏览器「打印 → 导出 PDF」即可
import { useCustom, useGo } from "@refinedev/core";
import { ArrowLeft, Printer } from "lucide-react";
import { useParams } from "react-router-dom";

interface RiskBucket {
  level: string;
  category: string;
  count: number;
}

interface ComplianceMonthlyReport {
  year_month: string;
  tenant_name: string;
  period_start: string;
  period_end: string;
  total_calls: number;
  total_minutes: number;
  total_risk_events: number;
  risk_events_by_level: Record<string, number>;
  risk_events_by_category: RiskBucket[];
  do_not_call_violations: number;
  after_hours_calls: number;
  overfreq_violations: number;
  interrupted_calls: number;
  generated_at: string;
}

// 风控分类英文 → 中文（与 admin/risk-keywords/list 保持一致 + 补常见后端值）
const RISK_CATEGORY_LABEL: Record<string, string> = {
  owner_abuse: "业主辱骂",
  owner_threat: "业主威胁",
  agent_violation: "催收员违规",
  agent_minor_misconduct: "轻微不当",
  complaint: "投诉",
  threat: "威胁",
  owner: "业主端",
  agent: "催收员端",
  customer: "业主端",
  none: "无",
};

export function ComplianceDetailPage() {
  const { yearMonth } = useParams<{ yearMonth: string }>();
  const go = useGo();

  const { query } = useCustom<ComplianceMonthlyReport>({
    url: `admin/compliance/monthly/${yearMonth}`,
    method: "get",
  });
  const data = query.data?.data;

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!data) {
    return <div className="p-6 text-red-600">月报加载失败</div>;
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4 print:hidden">
        <button
          type="button"
          onClick={() => go({ to: "/admin/compliance" })}
          className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)]"
        >
          <ArrowLeft className="w-4 h-4" /> 返回月报列表
        </button>
        <button
          type="button"
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Printer className="w-4 h-4" />
          打印 / 导出 PDF
        </button>
      </div>

      <div
        className="bg-white p-8 border border-[var(--color-neutral-200)] print:border-0 print:shadow-none"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <header className="mb-6 pb-4 border-b border-[var(--color-neutral-200)]">
          <h1 className="text-2xl font-bold text-[var(--color-neutral-900)]">
            {data.tenant_name} 合规催收行为月报
          </h1>
          <p className="text-sm text-[var(--color-neutral-500)] mt-1">
            统计周期 {data.period_start} ～ {data.period_end} · 生成于{" "}
            {data.generated_at?.slice(0, 19).replace("T", " ")}
          </p>
        </header>

        <section className="mb-6">
          <h2 className="text-base font-semibold mb-2">外呼概览</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="通话总数" value={data.total_calls} />
            <Stat label="累计计费分钟" value={data.total_minutes} />
            <Stat label="时段外通话" value={data.after_hours_calls} warn={data.after_hours_calls > 0} />
            <Stat label="超频联系案件" value={data.overfreq_violations} warn={data.overfreq_violations > 0} />
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-semibold mb-2">风控干预统计</h2>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <Stat label="L1 提示" value={data.risk_events_by_level.L1 ?? 0} />
            <Stat label="L2 督导接管" value={data.risk_events_by_level.L2 ?? 0} warn={(data.risk_events_by_level.L2 ?? 0) > 0} />
            <Stat label="L3 强制中止" value={data.risk_events_by_level.L3 ?? 0} warn={(data.risk_events_by_level.L3 ?? 0) > 0} />
          </div>
          <p className="text-xs text-[var(--color-neutral-500)] mt-2">
            其中 {data.interrupted_calls} 通通话被 AI 中止或终止。
          </p>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-semibold mb-2">合规违规明细</h2>
          <div className="text-sm space-y-1">
            <p>
              <span className="text-[var(--color-neutral-500)]">DNC（请勿来电）违规：</span>
              <strong
                className={
                  data.do_not_call_violations > 0
                    ? "text-red-600"
                    : "text-[var(--color-neutral-700)]"
                }
              >
                {data.do_not_call_violations} 次
              </strong>
            </p>
            <p>
              <span className="text-[var(--color-neutral-500)]">联系频次超限案件：</span>
              <strong
                className={
                  data.overfreq_violations > 0
                    ? "text-red-600"
                    : "text-[var(--color-neutral-700)]"
                }
              >
                {data.overfreq_violations} 户
              </strong>
            </p>
            <p>
              <span className="text-[var(--color-neutral-500)]">非工作时段外呼：</span>
              <strong
                className={
                  data.after_hours_calls > 0
                    ? "text-red-600"
                    : "text-[var(--color-neutral-700)]"
                }
              >
                {data.after_hours_calls} 通
              </strong>
              <span className="text-xs text-[var(--color-neutral-400)] ml-2">
                （工作时段：北京时间 09:00-21:00）
              </span>
            </p>
          </div>
        </section>

        {data.risk_events_by_category.length > 0 && (
          <section>
            <h2 className="text-base font-semibold mb-2">风控分类明细</h2>
            <table className="w-full text-sm">
              <thead className="text-left text-[var(--color-neutral-500)]">
                <tr className="border-b border-[var(--color-neutral-200)]">
                  <th className="py-2 font-medium">级别</th>
                  <th className="py-2 font-medium">类别</th>
                  <th className="py-2 font-medium text-right">次数</th>
                </tr>
              </thead>
              <tbody>
                {data.risk_events_by_category.map((b, i) => (
                  <tr key={i} className="border-b border-[var(--color-neutral-100)]">
                    <td className="py-2">{b.level}</td>
                    <td className="py-2">{RISK_CATEGORY_LABEL[b.category] ?? b.category}</td>
                    <td className="py-2 text-right">{b.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  warn,
}: {
  label: string;
  value: number;
  warn?: boolean;
}) {
  return (
    <div className="flex items-center justify-between bg-[var(--color-neutral-50)] px-3 py-2 rounded">
      <span className="text-[var(--color-neutral-500)]">{label}</span>
      <span
        className="font-bold"
        style={{ color: warn ? "var(--color-danger)" : "var(--color-neutral-900)" }}
      >
        {value}
      </span>
    </div>
  );
}
