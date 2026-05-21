// v0.5.9 — 物业管理员存证消费页
//
// 数据源:
//   GET /api/v1/admin/billing/blockchain-summary?year_month=YYYY-MM
//   GET /api/v1/admin/billing/blockchain-attestations?page=1&page_size=30
//
// 顶部 KPI(次数 + 总金额 + provider 状态)+ 类型分布 + 列表
import { useCustom } from "@refinedev/core";
import { ExternalLink, Hash, Link2, Shield } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../../types";

interface ByTypeStats {
  count: number;
  amount: string;
}

interface BlockchainSummary {
  year_month: string;
  attestation_count: number;
  amount_total: string;
  by_data_type: Record<string, ByTypeStats>;
  chain_provider: string | null;
}

interface AttestationItem {
  id: number;
  submitted_at: string;
  case_id: number | null;
  data_type: string;
  cost_amount: string | null;
  tx_hash: string | null;
  chain_provider: string;
  status: string;
}

const DATA_TYPE_LABELS: Record<string, string> = {
  call_recording: "通话录音",
  transcript: "转写文本",
  analysis: "AI 分析",
  evidence_bundle: "证据包",
};

const DATA_TYPE_COLORS: Record<string, string> = {
  call_recording: "#1A56DB",
  transcript: "#7E3AF2",
  analysis: "#D97706",
  evidence_bundle: "#059669",
};

const STATUS_BADGE: Record<string, string> = {
  confirmed: "ds-badge ds-badge-green",
  failed: "ds-badge ds-badge-red",
  pending: "ds-badge ds-badge-gray",
};

const STATUS_LABEL: Record<string, string> = {
  confirmed: "已上链",
  failed: "失败",
  pending: "处理中",
};

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function AdminBillingBlockchainPage() {
  const [ym, setYm] = useState(currentMonth());
  const [page, setPage] = useState(1);

  const { query: summaryQ } = useCustom<BlockchainSummary>({
    url: "admin/billing/blockchain-summary",
    method: "get",
    config: { query: { year_month: ym } },
  });

  const { query: listQ } = useCustom<PaginatedResponse<AttestationItem>>({
    url: "admin/billing/blockchain-attestations",
    method: "get",
    config: { query: { year_month: ym, page, page_size: 30 } },
  });

  const summary = summaryQ.data?.data;
  const items = listQ.data?.data?.items ?? [];
  const total = listQ.data?.data?.total ?? 0;

  const sortedTypes = summary
    ? Object.entries(summary.by_data_type).sort((a, b) => b[1].count - a[1].count)
    : [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Shield className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">存证消费</h1>
        <span className="text-sm text-[var(--color-neutral-500)]">区块链 / 易保全 月度统计 + 明细</span>
        <input
          type="month"
          value={ym}
          onChange={(e) => {
            setYm(e.target.value);
            setPage(1);
          }}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
        />
      </div>

      {/* 顶部 KPI */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-primary)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2 flex items-center gap-2">
            <Hash className="w-4 h-4 text-[var(--color-primary)]" />
            本月存证次数
          </div>
          <div className="text-2xl font-bold">{summary?.attestation_count ?? 0}</div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            累计 {sortedTypes.length} 种数据类型
          </div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-success)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2">本月累计金额</div>
          <div className="text-2xl font-bold text-[var(--color-success)]">¥{summary?.amount_total ?? "0.00"}</div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            按 BillingPricing 单价冻结(平台 OPS 维护)
          </div>
        </div>
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 border-l-4 border-l-[var(--color-warning)]">
          <div className="text-sm text-[var(--color-neutral-600)] mb-2 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-[var(--color-warning)]" />
            链上服务商
          </div>
          <div className="text-2xl font-bold">
            {summary?.chain_provider === "ebaoquan" ? "易保全(生产)" : summary?.chain_provider ?? "未配置"}
          </div>
          <div className="text-xs text-[var(--color-neutral-500)] mt-1">
            {summary?.chain_provider === "mock" ? "Mock 分支(开发用,不算消费)" : ""}
            {summary?.chain_provider === "ebaoquan" ? "上链证据可在易保全平台查询" : ""}
          </div>
        </div>
      </div>

      {/* 类型分布 */}
      {sortedTypes.length > 0 && (
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4">
          <div className="text-sm font-medium text-[var(--color-neutral-700)] mb-3">
            本月按数据类型分布
          </div>
          <div className="space-y-2">
            {sortedTypes.map(([dtype, stats]) => {
              const pct =
                summary && summary.attestation_count > 0
                  ? Math.round((stats.count / summary.attestation_count) * 100)
                  : 0;
              const color = DATA_TYPE_COLORS[dtype] ?? "#6B7280";
              return (
                <div key={dtype}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span style={{ color }}>{DATA_TYPE_LABELS[dtype] ?? dtype}</span>
                    <span className="font-mono text-[var(--color-neutral-700)]">
                      {stats.count} 次 · ¥{stats.amount} · {pct}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 8, background: "#F3F4F6", borderRadius: 4, overflow: "hidden",
                    }}
                  >
                    <div style={{ width: `${pct}%`, height: "100%", background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 列表 */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] flex items-center justify-between">
          <span className="text-sm font-medium">本月存证明细 · 共 {total} 条</span>
        </div>
        {listQ.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">加载中…</div>
        )}
        {!listQ.isLoading && items.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">本月暂无存证</div>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-xs uppercase text-[var(--color-neutral-600)]">
              <tr>
                <th className="px-4 py-3 text-left">时间</th>
                <th className="px-4 py-3 text-left">案件</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">金额</th>
                <th className="px-4 py-3 text-left">链上凭证</th>
                <th className="px-4 py-3 text-left">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-[var(--color-neutral-50)]">
                  <td className="px-4 py-3 text-xs text-[var(--color-neutral-700)]">
                    {new Date(it.submitted_at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {it.case_id ? `案件 #${it.case_id}` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: `${DATA_TYPE_COLORS[it.data_type] ?? "#6B7280"}1a`,
                        color: DATA_TYPE_COLORS[it.data_type] ?? "#6B7280",
                      }}
                    >
                      {DATA_TYPE_LABELS[it.data_type] ?? it.data_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {it.cost_amount ? `¥${it.cost_amount}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {it.tx_hash ? (
                      <a
                        href={`/api/v1/public/verify/${it.tx_hash}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[var(--color-primary)] hover:underline"
                      >
                        <span className="font-mono">{it.tx_hash.slice(0, 12)}…</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="text-[var(--color-neutral-400)]">易保全 (无 hash)</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={STATUS_BADGE[it.status] ?? "ds-badge ds-badge-gray"}>
                      {STATUS_LABEL[it.status] ?? it.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 分页 */}
      {total > 30 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <button
            type="button"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1 border border-[var(--color-neutral-300)] rounded disabled:opacity-50"
          >
            上一页
          </button>
          <span className="text-[var(--color-neutral-500)]">
            第 {page} 页 / 共 {Math.ceil(total / 30)} 页
          </span>
          <button
            type="button"
            disabled={page * 30 >= total}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1 border border-[var(--color-neutral-300)] rounded disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

export default AdminBillingBlockchainPage;
