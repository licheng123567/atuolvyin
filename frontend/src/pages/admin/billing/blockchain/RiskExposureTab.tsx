// v0.8.0 Wave C — 「存证管理」双 tab 中的「风险敞口」(新)
//
// 与「计费视图」互补:计费视图回答「我花了多少钱」,本 tab 回答「我有多少案件证据不够强」。
//
// 数据源:GET /api/v1/admin/blockchain/risk-overview?year_month=YYYY-MM&top_n=10
//
// 内容:
//   1. 3 KPI 卡片:本月新增案件 / 已强化(司法链) / 仅本地哈希
//   2. 进度条:已强化 N% vs 弱证据 M%(单条对比)
//   3. 大额未上链案件 Top 10 表格(可点击跳案件详情)
//   4. 帮助提示框:为什么要上链 + 建议时机
import { useCustom, useGo } from "@refinedev/core";
import { AlertTriangle, Info, ShieldAlert, ShieldCheck } from "lucide-react";

interface HighValueLocalOnlyItem {
  case_id: number;
  owner_name: string;
  building_room: string;
  amount_owed: string;
  months_overdue: number;
  stage: string;
  supervisor_action_count: number;
  last_contact_at: string | null;
}

interface RiskOverview {
  year_month: string;
  case_total: number;
  case_with_strong: number;
  case_local_only: number;
  strong_pct: number;
  high_value_local_only: HighValueLocalOnlyItem[];
}

const STAGE_LABEL: Record<string, string> = {
  new: "新",
  contacting: "联系中",
  promised: "承诺",
  paid: "已结清",
  legal: "已转法务",
  closed: "关闭",
};

interface RiskExposureTabProps {
  yearMonth: string;
}

export function RiskExposureTab({ yearMonth }: RiskExposureTabProps) {
  const go = useGo();
  const { query } = useCustom<RiskOverview>({
    url: "admin/blockchain/risk-overview",
    method: "get",
    config: { query: { year_month: yearMonth, top_n: 10 } },
  });

  const data = query.data?.data;
  const isLoading = query.isLoading;

  if (isLoading || !data) {
    return (
      <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
        加载中…
      </div>
    );
  }

  const weakPct = Math.max(0, 100 - data.strong_pct);

  return (
    <div className="space-y-4">
      {/* 顶部 3 KPI */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-neutral-400)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2">本月新增案件</div>
          <div className="text-2xl font-bold">{data.case_total}</div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            {yearMonth} 新建的催收案件
          </div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-success)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--color-success)]" />
            已强化为司法链证据
          </div>
          <div className="text-2xl font-bold text-[var(--color-success)]">
            {data.case_with_strong}
          </div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            ≥1 件 confirmed 上链记录
          </div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-warning)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[var(--color-warning)]" />
            仅本地哈希(弱证据)
          </div>
          <div className="text-2xl font-bold text-[var(--color-warning)]">
            {data.case_local_only}
          </div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            未来若进入诉讼建议上链
          </div>
        </div>
      </div>

      {/* 进度条 */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="font-medium text-[var(--color-neutral-700)]">
            证据强度分布
          </span>
          <span className="text-xs text-[var(--color-neutral-500)]">
            {data.strong_pct}% 已强化 / {weakPct.toFixed(1)}% 仅本地
          </span>
        </div>
        <div
          style={{
            display: "flex",
            height: 12,
            borderRadius: 6,
            overflow: "hidden",
            background: "#F3F4F6",
          }}
        >
          <div
            style={{
              width: `${data.strong_pct}%`,
              background: "var(--color-success)",
            }}
            title={`已强化 ${data.case_with_strong} 件`}
          />
          <div
            style={{
              width: `${weakPct}%`,
              background: "var(--color-warning)",
            }}
            title={`仅本地 ${data.case_local_only} 件`}
          />
        </div>
        <div
          className="flex items-center gap-4 mt-2 text-xs text-[var(--color-neutral-500)]"
        >
          <span className="flex items-center gap-1.5">
            <span
              style={{
                width: 10,
                height: 10,
                background: "var(--color-success)",
                borderRadius: 2,
                display: "inline-block",
              }}
            />
            司法链强证据(可直接核验)
          </span>
          <span className="flex items-center gap-1.5">
            <span
              style={{
                width: 10,
                height: 10,
                background: "var(--color-warning)",
                borderRadius: 2,
                display: "inline-block",
              }}
            />
            仅本地哈希(对方律师可质疑)
          </span>
        </div>
      </div>

      {/* 大额未上链案件 Top 10 */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
            <span className="text-sm font-medium">
              高风险未上链案件 Top {data.high_value_local_only.length}
            </span>
          </div>
          <span className="text-xs text-[var(--color-neutral-500)]">
            排序:欠款金额 + 逾期月数 + 督导介入次数
          </span>
        </div>
        {data.high_value_local_only.length === 0 ? (
          <div className="p-8 text-center text-sm text-[var(--color-neutral-500)]">
            本月暂无大额仅本地案件 — 状态良好 ✓
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-xs uppercase text-[var(--color-neutral-600)]">
              <tr>
                <th className="px-4 py-3 text-left">业主</th>
                <th className="px-4 py-3 text-left">房号</th>
                <th className="px-4 py-3 text-right">欠款</th>
                <th className="px-4 py-3 text-right">逾期</th>
                <th className="px-4 py-3 text-left">阶段</th>
                <th className="px-4 py-3 text-right">督导介入</th>
                <th className="px-4 py-3 text-left">最近联系</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {data.high_value_local_only.map((it) => (
                <tr key={it.case_id} className="hover:bg-[var(--color-neutral-50)]">
                  <td className="px-4 py-3">{it.owner_name || "—"}</td>
                  <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                    {it.building_room || "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-[var(--color-warning)]">
                    ¥{it.amount_owed}
                  </td>
                  <td className="px-4 py-3 text-right text-xs">
                    {it.months_overdue} 月
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {STAGE_LABEL[it.stage] ?? it.stage}
                  </td>
                  <td className="px-4 py-3 text-right text-xs">
                    {it.supervisor_action_count > 0 ? (
                      <span className="text-[var(--color-danger)] font-semibold">
                        {it.supervisor_action_count} 次
                      </span>
                    ) : (
                      <span className="text-[var(--color-neutral-400)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                    {it.last_contact_at
                      ? new Date(it.last_contact_at).toLocaleDateString("zh-CN")
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        go({ to: `/admin/cases/${it.case_id}`, type: "push" })
                      }
                      className="ds-btn ds-btn-secondary ds-btn-sm"
                    >
                      查看案件 →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 帮助提示框 */}
      <div
        className="rounded-lg p-4 flex gap-3"
        style={{
          background: "#EFF6FF",
          border: "1px solid #BFDBFE",
        }}
      >
        <Info
          className="w-5 h-5 flex-shrink-0 mt-0.5"
          style={{ color: "#1D4ED8" }}
        />
        <div className="text-sm text-[var(--color-neutral-700)] leading-relaxed">
          <div className="font-semibold mb-1 text-[#1D4ED8]">
            为什么要上链?
          </div>
          仅本地哈希的催收记录,对方律师可主张「平台单方面计算,无第三方背书」。上司法链
          (易保全)后,依据
          <span className="font-mono mx-1">最高法 2018 第 11 号文</span>
          互联网法院直接核验,法庭采信度显著提升。
          <div className="mt-2 text-xs text-[var(--color-neutral-600)]">
            <span className="font-semibold">建议上链时机:</span>
            欠款额 ≥¥10,000 且业主多次拒缴 / 已升级督导 ≥2 次 / 进入法务转化流程 — 单次
            ¥99/案件(含通话录音 + 转写 + 分析 + 风险事件全部上链)。
          </div>
        </div>
      </div>
    </div>
  );
}

export default RiskExposureTab;
