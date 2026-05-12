// v1.9.0 — 物业内部法务待处理列表（13000000006 法务老周等 legal 角色）
// 三 tab：待处理（internal_processing）/ 已关闭（closed_*）/ 全部
import { useCustom } from "@refinedev/core";
import { Eye, MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  internal_processing:    { label: "处理中",   cls: "ds-badge ds-badge-blue" },
  closed_paid:            { label: "已缴清",   cls: "ds-badge ds-badge-green" },
  closed_promised:        { label: "已承诺",   cls: "ds-badge ds-badge-orange" },
  closed_uncollectible:   { label: "已核销",   cls: "ds-badge ds-badge-gray" },
  escalated_to_lawfirm:   { label: "已升级律所", cls: "ds-badge ds-badge-red" },
};

const PAGE_SIZE = 20;

export function LegalInternalOrdersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"pending" | "closed" | "all">("pending");
  const [page, setPage] = useState(1);

  const { query } = useCustom<PaginatedResponse<InternalOrderItem>>({
    url: "legal/internal-orders",
    method: "get",
    config: { query: { tab, page, page_size: PAGE_SIZE } },
  });

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

      {/* tabs */}
      <div className="ds-card section-gap">
        <div className="card-header" style={{ display: "flex", gap: 0, padding: 0, borderBottom: "1px solid var(--color-neutral-200)" }}>
          {([
            { v: "pending", label: "待处理" },
            { v: "closed", label: "已关闭" },
            { v: "all", label: "全部" },
          ] as const).map((t) => (
            <button
              key={t.v}
              type="button"
              onClick={() => { setTab(t.v); setPage(1); }}
              style={{
                padding: "12px 20px", border: "none", background: "transparent", cursor: "pointer",
                fontSize: 13.5, fontWeight: 500,
                color: tab === t.v ? "var(--color-primary)" : "var(--color-neutral-600)",
                borderBottom: tab === t.v ? "2px solid var(--color-primary)" : "2px solid transparent",
                marginBottom: -1,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {isLoading ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>加载中…</div>
          ) : items.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
              {tab === "pending" ? "暂无待处理订单" : "暂无数据"}
            </div>
          ) : (
            <table className="ds-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>业主</th>
                  <th>房号</th>
                  <th>欠费金额</th>
                  <th>欠费月数</th>
                  <th>状态</th>
                  <th>申请人</th>
                  <th>处理次数</th>
                  <th>最后操作</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((o) => {
                  const room = (o.building || "") + (o.room || "") || "—";
                  const amount = o.amount_owed != null ? Number(o.amount_owed).toLocaleString("zh-CN") : "—";
                  const sb = STATUS_BADGE[o.status] ?? { label: o.status, cls: "ds-badge ds-badge-gray" };
                  return (
                    <tr key={o.id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{o.owner_name}</div>
                        <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>{o.owner_phone_masked}</div>
                      </td>
                      <td>{room}</td>
                      <td>¥{amount}</td>
                      <td>{o.months_overdue ?? "—"} 个月</td>
                      <td><span className={sb.cls}>{sb.label}</span></td>
                      <td>{o.requester_name ?? "—"}</td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{o.action_count}</span>
                        <span style={{ fontSize: 11, color: "var(--color-neutral-500)", marginLeft: 4 }}>次</span>
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
          )}
          <PaginationBar page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        </div>
      </div>
    </div>
  );
}
