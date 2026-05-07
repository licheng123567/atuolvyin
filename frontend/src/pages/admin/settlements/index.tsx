// 1:1 还原 ui/admin.html#a-settlement 结算管理
import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { useMemo, useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  formatAmount,
  formatPeriod,
  recentYearMonths,
  STATUS_LABELS,
  type SettlementStatus,
} from "./helpers";

interface SettlementItem {
  id: number;
  contract_id: number;
  provider_id: number | null;
  provider_name: string | null;
  period_start: string;
  period_end: string;
  total_amount: string;
  status: SettlementStatus;
  payment_proof_url: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
  billing_method?: string | null;
}

const STATUS_BADGE_CLASS: Record<SettlementStatus, string> = {
  DRAFT: "ds-badge ds-badge-gray",
  CONFIRMED: "ds-badge ds-badge-green",
  PAID: "ds-badge ds-badge-blue",
  DISPUTED: "ds-badge ds-badge-red",
};

export function AdminSettlementListPage() {
  const go = useGo();
  const [yearMonth, setYearMonth] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const yearMonthOptions = useMemo(() => recentYearMonths(6), []);

  const filters: CrudFilter[] = [];
  if (yearMonth) {
    filters.push({ field: "year_month", operator: "eq", value: yearMonth });
  }

  const { query } = useList<SettlementItem>({
    resource: "admin/settlements",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: SettlementItem[] =
    (rawData as unknown as PaginatedResponse<SettlementItem>)?.items ??
    (rawData as SettlementItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">结算管理</h1>
          <div className="page-subtitle">共 {total} 张结算单</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>账期：</span>
          <select
            className="form-control"
            style={{ width: 140 }}
            value={yearMonth}
            onChange={(e) => {
              setYearMonth(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部月份</option>
            {yearMonthOptions.map((ym) => (
              <option key={ym} value={ym}>
                {ym}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>服务商</th>
              <th>账期</th>
              <th>计费方式</th>
              <th>应付金额</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无结算单
                </td>
              </tr>
            )}
            {items.map((s) => {
              const period = formatPeriod(s.period_start, s.period_end);
              return (
                <tr key={s.id}>
                  <td>
                    <strong>{s.provider_name ?? "—"}</strong>
                  </td>
                  <td>{period}</td>
                  <td>{s.billing_method ?? "—"}</td>
                  <td style={{ fontWeight: 700 }}>{formatAmount(s.total_amount)}</td>
                  <td>
                    <span className={STATUS_BADGE_CLASS[s.status] ?? "ds-badge ds-badge-gray"}>
                      {STATUS_LABELS[s.status] ?? s.status}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/admin/settlements/${s.id}` })}
                    >
                      查看明细
                    </button>
                    {s.status === "DRAFT" && (
                      <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" style={{ marginLeft: 4 }}>
                        确认结算单
                      </button>
                    )}
                    {s.status === "CONFIRMED" && (
                      <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" style={{ marginLeft: 4 }}>
                        上传凭证
                      </button>
                    )}
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
    </div>
  );
}
