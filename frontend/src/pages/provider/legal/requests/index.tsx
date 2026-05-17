// §9 — 服务商法务-转化请求列表页
import { useGo } from "@refinedev/core";
import { ClipboardList } from "lucide-react";
import { useState } from "react";
import { PaginationBar } from "../../../../components/ui/PaginationBar";
import { useProviderLegalRequests } from "../api";
import { TableStateRow } from "../TableStateRow";
import { STATUS_META, UNKNOWN_STATUS_META } from "./status-meta";

const PAGE_SIZE = 20;

export function ProviderLegalRequestsPage() {
  const go = useGo();
  const [page, setPage] = useState(1);

  const { items, total, isLoading, isError } = useProviderLegalRequests({ page, pageSize: PAGE_SIZE });

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ClipboardList size={20} style={{ color: "var(--color-primary)" }} />
            <h1 className="page-title">法务转化请求</h1>
          </div>
          <p className="page-subtitle">本服务商法务发起的转化请求 · 跟踪审批结果与订单进度</p>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>案件</th>
              <th>项目</th>
              <th>申请理由</th>
              <th>审批状态</th>
              <th>订单状态</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <TableStateRow colSpan={7}>加载中…</TableStateRow>}
            {isError && !isLoading && <TableStateRow colSpan={7}>加载失败</TableStateRow>}
            {!isLoading && !isError && items.length === 0 && (
              <TableStateRow colSpan={7}>暂无转化请求</TableStateRow>
            )}
            {!isLoading && !isError && items.map((r) => {
              const meta = STATUS_META[r.status];
              return (
                <tr key={r.id}>
                  <td>{r.owner_name ?? "—"}</td>
                  <td>{r.project_name ?? "—"}</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        maxWidth: 240,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {r.reason ?? "—"}
                    </span>
                  </td>
                  <td>
                    {meta ? (
                      <span
                        className="ds-badge"
                        style={{ background: meta.background, color: meta.color }}
                      >
                        {meta.label}
                      </span>
                    ) : (
                      <span
                        className="ds-badge"
                        style={{ background: UNKNOWN_STATUS_META.background, color: UNKNOWN_STATUS_META.color }}
                      >
                        {r.status}
                      </span>
                    )}
                  </td>
                  <td>
                    {r.order_status == null ? (
                      "—"
                    ) : (
                      <span className="ds-badge ds-badge-blue">{r.order_status}</span>
                    )}
                  </td>
                  <td>{r.created_at.slice(0, 10)}</td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/provider/legal/requests/${r.id}` })}
                    >
                      查看
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
    </div>
  );
}
