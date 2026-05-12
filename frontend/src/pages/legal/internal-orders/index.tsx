// v1.9.0 + v1.9.3 — 物业内部法务待处理列表（13000000006 法务老周等 legal 角色）
// 4 tab：待处理（internal_processing）/ 已关闭（closed_*）/ 已升级律所 / 全部
// v1.9.3 — UI 统一：参 admin/partner-law-firms 的 page-header + table-wrap + ds-tabs 范式
import { useCustom } from "@refinedev/core";
import { Eye, Inbox, MessageSquarePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import type { PaginatedResponse } from "../../../types";

interface InternalOrderItem {
  id: number;
  case_id: number;
  owner_name: string;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  amount_owed: string | number | null;
  months_overdue: number | null;
  status: string;
  created_at: string;
  requester_name: string | null;
  last_action_at: string | null;
  action_count: number;
  promise_due_date: string | null;
}

interface KpiData {
  pending_count: number;
  closed_this_month: number;
  avg_processing_days: number | null;
  escalation_rate_pct: number | null;
}

function todayISO(): string { return new Date().toISOString().slice(0, 10); }

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  internal_processing:    { label: "处理中",     cls: "ds-badge ds-badge-blue" },
  closed_paid:            { label: "已缴清",     cls: "ds-badge ds-badge-green" },
  closed_promised:        { label: "已承诺",     cls: "ds-badge ds-badge-orange" },
  closed_uncollectible:   { label: "已核销",     cls: "ds-badge ds-badge-gray" },
  escalated_to_lawfirm:   { label: "已升级律所", cls: "ds-badge ds-badge-red" },
};

const PAGE_SIZE = 20;

type TabValue = "pending" | "closed" | "escalated" | "all";

const TABS: { v: TabValue; label: string }[] = [
  { v: "pending", label: "待处理" },
  { v: "closed", label: "已关闭" },
  { v: "escalated", label: "已升级律所" },
  { v: "all", label: "全部" },
];

export function LegalInternalOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as TabValue) || "pending";
  const [tab, setTab] = useState<TabValue>(initialTab);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = (searchParams.get("tab") as TabValue) || "pending";
    setTab(t);
    setPage(1);
  }, [searchParams]);

  const { query } = useCustom<PaginatedResponse<InternalOrderItem>>({
    url: "legal/internal-orders",
    method: "get",
    config: { query: { tab, page, page_size: PAGE_SIZE } },
  });

  const { query: kpiQuery } = useCustom<KpiData>({
    url: "legal/internal-orders/kpi",
    method: "get",
  });
  const kpi = kpiQuery.data?.data;

  const isLoading = query.isLoading;
  const items: InternalOrderItem[] = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h1 className="page-title">法务待内部处理</h1>
        <p className="page-subtitle">
          催收员申请转法务 → 督导审批通过的案件，物业法务在此处理（沟通业主 / 出律师函 / 调解 / 关闭）。
        </p>
      </div>

      {/* KPI 卡 */}
      {kpi && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
          <KpiCard label="待处理" value={kpi.pending_count} suffix="单" tone="primary" />
          <KpiCard label="本月关闭" value={kpi.closed_this_month} suffix="单" tone="green" />
          <KpiCard
            label="本月平均处理时长"
            value={kpi.avg_processing_days ?? "—"}
            suffix={kpi.avg_processing_days != null ? "天" : ""}
            tone="neutral"
          />
          <KpiCard
            label="本月升级律所率"
            value={kpi.escalation_rate_pct ?? "—"}
            suffix={kpi.escalation_rate_pct != null ? "%" : ""}
            tone={(kpi.escalation_rate_pct ?? 0) >= 30 ? "red" : "orange"}
          />
        </div>
      )}

      {/* tabs */}
      <div className="ds-tabs" style={{ marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.v}
            type="button"
            className={`ds-tab ${tab === t.v ? "active" : ""}`}
            onClick={() => { setTab(t.v); setPage(1); }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 表格 */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业主</th>
              <th>房号</th>
              <th style={{ textAlign: "right" }}>欠费金额</th>
              <th style={{ textAlign: "right" }}>欠费月数</th>
              <th>状态</th>
              <th>申请人</th>
              <th style={{ textAlign: "right" }}>处理次数</th>
              <th>最后操作</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 40, color: "var(--color-neutral-400)" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <Inbox className="w-8 h-8" style={{ color: "var(--color-neutral-300)" }} />
                    <span>
                      {tab === "pending" ? "暂无待处理订单"
                        : tab === "escalated" ? "暂无升级到律所的订单"
                        : "暂无数据"}
                    </span>
                  </div>
                </td>
              </tr>
            )}
            {!isLoading && items.map((o) => {
              const room = (o.building || "") + (o.room || "") || "—";
              const amount = o.amount_owed != null ? Number(o.amount_owed).toLocaleString("zh-CN") : "—";
              const sb = STATUS_BADGE[o.status] ?? { label: o.status, cls: "ds-badge ds-badge-gray" };
              const overdue = o.status === "closed_promised" && o.promise_due_date && o.promise_due_date < todayISO();
              return (
                <tr key={o.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{o.owner_name}</div>
                    <div style={{ fontSize: 11, color: "var(--color-neutral-500)", fontFamily: "var(--font-mono, monospace)" }}>{o.owner_phone_masked}</div>
                  </td>
                  <td>{room}</td>
                  <td style={{ textAlign: "right", fontWeight: 600, color: "#dc2626" }}>¥{amount}</td>
                  <td style={{ textAlign: "right" }}>{o.months_overdue ?? "—"} 个月</td>
                  <td>
                    <span className={sb.cls}>{sb.label}</span>
                    {o.status === "closed_promised" && o.promise_due_date && (
                      <div style={{ fontSize: 11, marginTop: 4, color: overdue ? "#dc2626" : "var(--color-neutral-500)" }}>
                        {overdue ? "🔴 " : ""}承诺：{o.promise_due_date}
                      </div>
                    )}
                  </td>
                  <td>{o.requester_name ?? "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    <span style={{ fontWeight: 600 }}>{o.action_count}</span>
                    <span style={{ fontSize: 11, color: "var(--color-neutral-500)", marginLeft: 2 }}>次</span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
                    {o.last_action_at ? new Date(o.last_action_at).toLocaleString("zh-CN") : "—"}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => navigate(`/legal/internal-orders/${o.id}`)}
                    >
                      {o.status === "internal_processing"
                        ? <><MessageSquarePlus className="w-3 h-3" /> 处理</>
                        : <><Eye className="w-3 h-3" /> 详情</>}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {total > 0 && (
          <div style={{ padding: "10px 16px", borderTop: "1px solid var(--color-neutral-200)" }}>
            <PaginationBar page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}

function KpiCard({ label, value, suffix, tone }: {
  label: string;
  value: number | string;
  suffix?: string;
  tone: "primary" | "green" | "orange" | "red" | "neutral";
}) {
  const COLOR: Record<typeof tone, string> = {
    primary: "var(--color-primary)",
    green: "#16a34a",
    orange: "#ea580c",
    red: "#dc2626",
    neutral: "var(--color-neutral-700)",
  };
  return (
    <div className="ds-card" style={{ padding: "14px 16px" }}>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 24, fontWeight: 700, color: COLOR[tone], lineHeight: 1 }}>{value}</span>
        {suffix && <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>{suffix}</span>}
      </div>
    </div>
  );
}
