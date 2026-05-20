// v0.5.4 — 物业法务工作台「待法务接单」列表
// 列出 status=approved_pending_legal 的 LegalConversionRequest,法务点接单 → LegalFinalizeModal 选包 → 建 Order
import { useCustom, useInvalidate } from "@refinedev/core";
import { Briefcase, Inbox } from "lucide-react";
import { useState } from "react";
import {
  LegalFinalizeModal,
  type LegalFinalizeContext,
} from "../../../components/legal-conversion/LegalFinalizeModal";
import { PaginationBar } from "../../../components/ui/PaginationBar";

interface RequestItem {
  id: number;
  case_id: number;
  owner_name: string | null;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  months_overdue: number | null;
  requester_user_id: number;
  requester_role: string;
  requester_name: string | null;
  reason: string | null;
  status: string;
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

const PAGE_SIZE = 20;

export function LegalPendingFinalizePage() {
  const invalidate = useInvalidate();
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<RequestItem | null>(null);

  // 后端 legal 角色已限定只看 approved_pending_legal 状态(Wave 3 list 端点改造)
  const { query } = useCustom<ListResp>({
    url: "legal-conversion-requests",
    method: "get",
    config: { query: { page, page_size: PAGE_SIZE } },
  });

  const items = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  function handleFinalized() {
    setTarget(null);
    void invalidate({
      resource: "legal-conversion-requests",
      invalidates: ["all"],
    });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Briefcase size={20} style={{ color: "#0ea5e9" }} />
            <div className="page-title">待法务接单</div>
          </div>
          <div className="page-subtitle">
            督导/admin 已批准的转法务申请等你选服务包并建单 — 总{total} 单
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>申请号</th>
              <th>业主 / 房号</th>
              <th>项目</th>
              <th>欠费金额</th>
              <th>申请人(催收员)</th>
              <th>催收员理由</th>
              <th>审批人</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td
                  colSpan={9}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}
                >
                  <Inbox size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
                  <div>暂无待接单申请</div>
                </td>
              </tr>
            )}
            {items.map((r) => {
              const room =
                r.building && r.room
                  ? `${r.building}${r.room}`
                  : r.building ?? r.room ?? "—";
              const reasonText = r.reason
                ? r.reason.length > 40
                  ? `${r.reason.slice(0, 40)}…`
                  : r.reason
                : "—";
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
                      {room}
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
                  <td style={{ fontSize: 12 }}>{r.requester_name ?? "—"}</td>
                  <td
                    style={{ fontSize: 12, maxWidth: 220 }}
                    title={r.reason ?? ""}
                  >
                    {reasonText}
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {r.reviewer_name ?? "—"}
                    {r.reviewer_role && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--color-neutral-400)",
                        }}
                      >
                        {r.reviewer_role}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
                    {new Date(r.created_at).toLocaleString("zh-CN", {
                      hour12: false,
                    })}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-primary ds-btn-sm"
                      onClick={() => setTarget(r)}
                    >
                      接单选包
                    </button>
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

      {target && (
        <LegalFinalizeModal
          ctx={{
            requestId: target.id,
            caseId: target.case_id,
            ownerName: target.owner_name,
            ownerRoom:
              target.building && target.room
                ? `${target.building}${target.room}`
                : target.building ?? target.room,
            projectName: target.project_name,
            amountOwed: target.amount_owed,
            requesterName: target.requester_name,
            reason: target.reason,
            reviewerNote: target.reviewer_note,
            reviewerName: target.reviewer_name,
          } satisfies LegalFinalizeContext}
          onClose={() => setTarget(null)}
          onFinalized={handleFinalized}
        />
      )}
    </div>
  );
}
