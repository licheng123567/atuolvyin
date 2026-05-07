// 1:1 还原 ui/agent-pc.html#my-cases 我的案件
import { useCreate, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { ChevronDown, Phone, QrCode, Search } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { PaginatedResponse } from "../../../types";
import { QrDialDialog } from "../../../components/dial/QrDialDialog";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at?: string | null;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待跟进",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级处理",
  closed: "已关闭",
};

const STAGE_BADGE_CLASS: Record<string, string> = {
  new: "ds-badge ds-badge-orange",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-blue",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

function formatLast(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return `今天 ${d.toTimeString().slice(0, 5)}`;
  const yest = new Date(); yest.setDate(yest.getDate() - 1);
  if (d.toDateString() === yest.toDateString()) return `昨天 ${d.toTimeString().slice(0, 5)}`;
  return d.toISOString().slice(0, 10);
}

export function AgentCaseListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [stage, setStage] = useState("");
  const [keyword, setKeyword] = useState("");
  const [claimingId] = useState<number | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [qrState, setQrState] = useState<{
    caseId: number;
    qrPayload: string;
    expiresAt: string;
  } | null>(null);
  const lastQrCaseId = useRef<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });

  const { query } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // 过滤关键词
  const visible = keyword
    ? items.filter((c) => c.owner.name.includes(keyword) || (c.owner.room ?? "").includes(keyword))
    : items;

  const { mutate: dialMutate } = useCreate();

  function requestQrPayload(caseId: number) {
    setOpenMenuId(null);
    lastQrCaseId.current = caseId;
    dialMutate(
      {
        resource: "calls/dial-request",
        values: { case_id: caseId },
      },
      {
        onSuccess: (resp) => {
          const data = resp.data as { qr_payload?: string; expires_at?: string };
          if (data.qr_payload && data.expires_at) {
            setQrState({
              caseId,
              qrPayload: data.qr_payload,
              expiresAt: data.expires_at,
            });
          }
        },
      },
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">我的案件</h1>
          <div className="page-subtitle">共 {total} 件分配案件</div>
        </div>
        <div className="filters-bar">
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              type="text"
              className="form-control"
              placeholder="搜索业主姓名 / 房号"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>
          <select
            className="form-control"
            style={{ width: "auto" }}
            value={stage}
            onChange={(e) => {
              setStage(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部状态</option>
            {Object.entries(STAGE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业主姓名</th>
              <th>楼栋/房号</th>
              <th>欠费金额</th>
              <th>欠费月数</th>
              <th>状态</th>
              <th>最近联系</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无分配的案件
                </td>
              </tr>
            )}
            {visible.map((c) => {
              const room =
                c.owner.building && c.owner.room
                  ? `${c.owner.building}${c.owner.room}`
                  : c.owner.building ?? c.owner.room ?? "—";
              const isPaid = c.stage === "paid";
              return (
                <tr key={c.id}>
                  <td>
                    <strong>{c.owner.name}</strong>
                    <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                      {c.owner.phone_masked}
                    </div>
                  </td>
                  <td>{room}</td>
                  <td
                    style={{
                      color: isPaid ? "#057a55" : "#e02424",
                      fontWeight: 600,
                    }}
                  >
                    {c.amount_owed
                      ? `¥${Number(c.amount_owed).toLocaleString()}`
                      : "—"}
                  </td>
                  <td>
                    {c.months_overdue != null ? `${c.months_overdue}个月` : "—"}
                  </td>
                  <td>
                    <span className={STAGE_BADGE_CLASS[c.stage] ?? "ds-badge ds-badge-gray"}>
                      {STAGE_LABELS[c.stage] ?? c.stage}
                    </span>
                  </td>
                  <td>{formatLast(c.last_contact_at)}</td>
                  <td>
                    <div style={{ position: "relative", display: "inline-block" }}>
                      <button
                        type="button"
                        className="ds-btn ds-btn-primary ds-btn-sm"
                        onClick={() =>
                          setOpenMenuId(openMenuId === c.id ? null : c.id)
                        }
                        disabled={claimingId === c.id || c.owner.do_not_call}
                      >
                        <Phone className="w-3 h-3" />
                        拨号
                        <ChevronDown className="w-3 h-3" />
                      </button>
                      {openMenuId === c.id && (
                        <div
                          style={{
                            position: "absolute",
                            top: "100%",
                            right: 0,
                            marginTop: 4,
                            background: "white",
                            border: "1px solid var(--color-neutral-200)",
                            borderRadius: "var(--radius-md)",
                            boxShadow: "var(--shadow-md, 0 4px 12px rgba(0,0,0,0.10))",
                            zIndex: 10,
                            minWidth: 160,
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => requestQrPayload(c.id)}
                            style={{
                              display: "flex",
                              width: "100%",
                              alignItems: "center",
                              gap: 6,
                              padding: "8px 12px",
                              fontSize: 13,
                              border: "none",
                              background: "transparent",
                              textAlign: "left",
                              cursor: "pointer",
                            }}
                          >
                            <QrCode className="w-3.5 h-3.5" />
                            扫码到 App 拨号
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setOpenMenuId(null);
                              navigate(`/agent/cases/${c.id}`);
                            }}
                            style={{
                              display: "flex",
                              width: "100%",
                              alignItems: "center",
                              gap: 6,
                              padding: "8px 12px",
                              fontSize: 13,
                              border: "none",
                              background: "transparent",
                              textAlign: "left",
                              cursor: "pointer",
                            }}
                          >
                            查看详情
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {totalPages > 1 && (
          <div className="ds-pagination">
            <span className="pagination-info">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((p) => p - 1)}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div className="page-btn" onClick={() => setPage((p) => p + 1)}>
                  ›
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {qrState && (
        <QrDialDialog
          qrPayload={qrState.qrPayload}
          expiresAt={qrState.expiresAt}
          onClose={() => setQrState(null)}
          onRegenerate={() => requestQrPayload(qrState.caseId)}
        />
      )}
    </div>
  );
}
