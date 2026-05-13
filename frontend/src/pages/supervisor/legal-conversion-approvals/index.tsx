// v1.6.8 — 法务转化申请审批 inbox（督导 / admin / platform_super 共用）
// 后端 endpoint：GET /api/v1/legal-conversion-requests
//                 POST /api/v1/legal-conversion-requests/{id}/approve
//                 POST /api/v1/legal-conversion-requests/{id}/reject
import { useCustom, useGetIdentity, useInvalidate } from "@refinedev/core";
import { CheckCircle2, ClipboardList, Eye, Scale, X } from "lucide-react";
import { useState } from "react";
import { ConvertToLegalModal } from "../../../components/legal-conversion/ConvertToLegalModal";
import { RejectRequestModal } from "../../../components/legal-conversion/RejectRequestModal";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";

interface RequestItem {
  id: number;
  tenant_id: number;
  case_id: number;
  owner_name: string | null;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  months_overdue: number | null;
  case_stage: string | null;
  requester_user_id: number;
  requester_role: string;
  requester_name: string | null;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reviewer_user_id: number | null;
  reviewer_role: string | null;
  reviewer_name: string | null;
  reviewed_at: string | null;
  reviewer_note: string | null;
  related_order_id: number | null;
  created_at: string;
  updated_at: string;
}

interface ListResp {
  items: RequestItem[];
  total: number;
}

const STATUS_LABEL: Record<RequestItem["status"], string> = {
  pending: "待审批",
  approved: "已批准",
  rejected: "已驳回",
  cancelled: "已撤销",
};

const STATUS_BADGE: Record<RequestItem["status"], string> = {
  pending: "ds-badge ds-badge-orange",
  approved: "ds-badge ds-badge-green",
  rejected: "ds-badge ds-badge-gray",
  cancelled: "ds-badge ds-badge-gray",
};

const PAGE_SIZE = 20;

interface IdentityShape {
  role?: string;
  name?: string;
}

export function SupervisorLegalConversionApprovalsPage() {
  const { data: identity } = useGetIdentity<IdentityShape>();
  const invalidate = useInvalidate();
  const [tab, setTab] = useState<"pending" | "approved" | "rejected" | "all">("pending");
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const debouncedKw = useDebouncedValue(keyword, 300);
  const [approveTarget, setApproveTarget] = useState<RequestItem | null>(null);
  const [rejectTarget, setRejectTarget] = useState<RequestItem | null>(null);

  const statusForApi = tab === "all" ? undefined : tab;

  const { query } = useCustom<ListResp>({
    url: "legal-conversion-requests",
    method: "get",
    config: { query: { status: statusForApi, page, page_size: PAGE_SIZE } },
  });
  // 计数（pageSize=1 仅取 total）
  const { query: pendingQ } = useCustom<ListResp>({
    url: "legal-conversion-requests",
    method: "get",
    config: { query: { status: "pending", page: 1, page_size: 1 } },
  });
  const { query: approvedQ } = useCustom<ListResp>({
    url: "legal-conversion-requests",
    method: "get",
    config: { query: { status: "approved", page: 1, page_size: 1 } },
  });
  const { query: rejectedQ } = useCustom<ListResp>({
    url: "legal-conversion-requests",
    method: "get",
    config: { query: { status: "rejected", page: 1, page_size: 1 } },
  });

  const allItems = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;
  const pendingCount = pendingQ.data?.data?.total ?? 0;
  const approvedCount = approvedQ.data?.data?.total ?? 0;
  const rejectedCount = rejectedQ.data?.data?.total ?? 0;

  // 前端 keyword 过滤当前页（业主 / 房号 / 申请号）
  const kw = debouncedKw.trim().toLowerCase();
  const visibleItems = kw
    ? allItems.filter((r) =>
        `${r.owner_name ?? ""} ${r.building ?? ""}${r.room ?? ""} ${r.id} ${r.project_name ?? ""}`
          .toLowerCase()
          .includes(kw),
      )
    : allItems;

  function handleApproved() {
    setApproveTarget(null);
    void invalidate({ resource: "legal-conversion-requests", invalidates: ["all"] });
  }
  function handleRejected() {
    setRejectTarget(null);
    void invalidate({ resource: "legal-conversion-requests", invalidates: ["all"] });
  }

  const role = identity?.role ?? "";
  const isAdmin = role === "admin" || role === "platform_super" || role === "platform_superadmin";

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Scale size={20} style={{ color: "#7e3af2" }} />
            <div className="page-title">
              法务转化审批{isAdmin ? " — admin 视角" : " — 督导视角"}
            </div>
          </div>
          <div className="page-subtitle">
            催收员对「不可能自愿缴」案件提交「申请转法务」后，在此审批是否真正建单转化
          </div>
        </div>
      </div>

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>
          <ClipboardList size={14} /> 待我审批 <strong>{pendingCount}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          <CheckCircle2 size={14} /> 已批准 <strong>{approvedCount}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-neutral-500)" }}>
          已驳回 <strong>{rejectedCount}</strong>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <SearchInput
          value={keyword}
          onChange={(v) => {
            setKeyword(v);
            setPage(1);
          }}
          placeholder="按申请号 / 业主 / 房号 / 项目搜索"
          width={260}
        />
        {(["pending", "approved", "rejected", "all"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`ds-btn ${tab === t ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`}
            onClick={() => {
              setTab(t);
              setPage(1);
            }}
          >
            {t === "pending" && `待审批（${pendingCount}）`}
            {t === "approved" && `已批准（${approvedCount}）`}
            {t === "rejected" && `已驳回（${rejectedCount}）`}
            {t === "all" && "全部"}
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>申请号</th>
              <th>业主 / 房号</th>
              <th>项目</th>
              <th>欠费金额</th>
              <th>欠费月数</th>
              <th>申请人</th>
              <th>申请理由</th>
              <th>状态</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td
                  colSpan={10}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && visibleItems.length === 0 && (
              <tr>
                <td
                  colSpan={10}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  暂无{tab === "pending" ? "待审批" : ""}申请
                </td>
              </tr>
            )}
            {visibleItems.map((r) => {
              const room =
                r.building && r.room
                  ? `${r.building}${r.room}`
                  : r.building ?? r.room ?? "—";
              const reasonText = r.reason
                ? r.reason.length > 30
                  ? `${r.reason.slice(0, 30)}…`
                  : r.reason
                : "—";
              const canAct = r.status === "pending";
              return (
                <tr key={r.id}>
                  <td
                    style={{
                      color: "var(--color-primary)",
                      fontFamily: "monospace",
                    }}
                  >
                    #{r.id}
                  </td>
                  <td>
                    <strong>{r.owner_name ?? "—"}</strong>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--color-neutral-500)",
                        marginTop: 2,
                      }}
                    >
                      {room} {r.owner_phone_masked ?? ""}
                    </div>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--color-primary)" }}>
                    {r.project_name ? `📁 ${r.project_name}` : "—"}
                  </td>
                  <td style={{ color: "#e02424", fontWeight: 600 }}>
                    {r.amount_owed
                      ? `¥${Number(r.amount_owed).toLocaleString("zh-CN")}`
                      : "—"}
                  </td>
                  <td>
                    {r.months_overdue != null ? `${r.months_overdue}个月` : "—"}
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {r.requester_name ?? "—"}
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--color-neutral-400)",
                      }}
                    >
                      {r.requester_role}
                    </div>
                  </td>
                  <td
                    style={{
                      fontSize: 12,
                      maxWidth: 220,
                    }}
                    title={r.reason ?? ""}
                  >
                    {reasonText}
                  </td>
                  <td>
                    <span className={STATUS_BADGE[r.status]}>
                      {STATUS_LABEL[r.status]}
                    </span>
                    {r.status === "approved" && r.related_order_id && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--color-neutral-500)",
                          marginTop: 2,
                        }}
                      >
                        订单 #{r.related_order_id}
                      </div>
                    )}
                    {r.status !== "pending" && r.reviewer_name && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--color-neutral-500)",
                          marginTop: 2,
                        }}
                      >
                        审批人：{r.reviewer_name}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                    {new Date(r.created_at).toLocaleString("zh-CN", {
                      hour12: false,
                    })}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {canAct ? (
                        <>
                          <button
                            type="button"
                            className="ds-btn ds-btn-primary ds-btn-sm"
                            onClick={() => setApproveTarget(r)}
                          >
                            <CheckCircle2 size={12} /> 批准
                          </button>
                          <button
                            type="button"
                            className="ds-btn ds-btn-secondary ds-btn-sm"
                            style={{ color: "var(--color-danger)" }}
                            onClick={() => setRejectTarget(r)}
                          >
                            <X size={12} /> 驳回
                          </button>
                        </>
                      ) : (
                        <span
                          className="ds-btn ds-btn-ghost ds-btn-sm"
                          style={{ cursor: "default", opacity: 0.6 }}
                          title={r.reviewer_note ?? "已处理"}
                        >
                          <Eye size={12} /> 已处理
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </div>

      {approveTarget && (
        <ConvertToLegalModal
          caseId={approveTarget.case_id}
          mode="approve"
          requestId={approveTarget.id}
          approveContext={{
            requesterName: approveTarget.requester_name,
            reason: approveTarget.reason,
          }}
          onClose={() => setApproveTarget(null)}
          onSuccess={handleApproved}
        />
      )}

      {rejectTarget && (
        <RejectRequestModal
          requestId={rejectTarget.id}
          onClose={() => setRejectTarget(null)}
          onRejected={handleRejected}
        />
      )}
    </div>
  );
}
