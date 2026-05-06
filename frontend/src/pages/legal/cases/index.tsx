import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Scale, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  LEGAL_STAGES,
  formatStage,
  getStageColor,
} from "./helpers";

interface LegalCaseItem {
  id: number;
  case_id: number;
  stage: string;
  amount_disputed: string | null;
  lawyer_name: string | null;
  law_firm: string | null;
  next_milestone: string | null;
  notes: string | null;
  owner_name: string | null;
  owner_phone_masked: string | null;
}

export function LegalCaseListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });

  const { query } = useList<LegalCaseItem>({
    resource: "legal/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: LegalCaseItem[] =
    (rawData as unknown as PaginatedResponse<LegalCaseItem>)?.items ??
    (rawData as LegalCaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Scale className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            法务案件
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 件
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索业主姓名…"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] w-48"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
        <select
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部阶段</option>
          {LEGAL_STAGES.map((s) => (
            <option key={s} value={s}>
              {formatStage(s)}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                业主姓名
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                案件号
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                当前阶段
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                涉案金额(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                律师
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                下一里程碑
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无法务案件
                </td>
              </tr>
            )}
            {items.map((c) => (
              <tr
                key={c.id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--color-neutral-900)]">
                    {c.owner_name ?? "—"}
                  </div>
                  {c.owner_phone_masked && (
                    <div className="text-xs text-[var(--color-neutral-400)]">
                      {c.owner_phone_masked}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  #{c.case_id}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={getStageColor(c.stage)}
                  >
                    {formatStage(c.stage)}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_disputed ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.lawyer_name ? (
                    <>
                      <div>{c.lawyer_name}</div>
                      {c.law_firm && (
                        <div className="text-xs text-[var(--color-neutral-400)]">
                          {c.law_firm}
                        </div>
                      )}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {c.next_milestone ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/legal/cases/${c.id}` })}
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
