import { useCreate, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Phone } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

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
}

const STAGE_LABELS: Record<string, string> = {
  new: "待处理",
  in_progress: "处理中",
  promised: "已承诺",
  paid: "已缴费",
  escalated: "已上报",
  closed: "已关闭",
};

const STAGE_COLORS: Record<string, React.CSSProperties> = {
  new: { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  in_progress: { background: "var(--color-primary-light)", color: "var(--color-primary)" },
  promised: { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  paid: { background: "var(--color-success-light)", color: "var(--color-success)" },
  escalated: { background: "var(--color-danger-light)", color: "var(--color-danger)" },
  closed: { background: "var(--color-neutral-100)", color: "var(--color-neutral-400)" },
};

export function AgentCaseListPage() {
  const [page, setPage] = useState(1);
  const [stage, setStage] = useState("");
  const [poolType, setPoolType] = useState("");
  const [claimingId, setClaimingId] = useState<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });
  if (poolType) filters.push({ field: "pool_type", operator: "eq", value: poolType });

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
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const { mutate: claimCase } = useCreate();

  function handleClaim(caseId: number) {
    setClaimingId(caseId);
    claimCase(
      {
        resource: `agent/cases/${caseId}/claim`,
        values: {},
      },
      {
        onSuccess: () => {
          setClaimingId(null);
          query.refetch();
        },
        onError: () => {
          setClaimingId(null);
        },
      }
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Phone className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            我的案件
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 件
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={poolType}
          onChange={(e) => {
            setPoolType(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部（公池+专属）</option>
          <option value="public">公池</option>
          <option value="private">我的专属</option>
        </select>
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
          {Object.entries(STAGE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
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
                业主
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                房间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                欠费(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                逾期月数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                阶段
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                来源
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
                  暂无案件
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
                    {c.owner.name}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-400)]">
                    {c.owner.phone_masked}
                  </div>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.owner.building && c.owner.room
                    ? `${c.owner.building} ${c.owner.room}`
                    : (c.owner.building ?? c.owner.room ?? "—")}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_owed ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.months_overdue ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={STAGE_COLORS[c.stage] ?? {}}
                  >
                    {STAGE_LABELS[c.stage] ?? c.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {c.pool_type === "public" ? "公池" : "专属"}
                </td>
                <td className="px-4 py-3">
                  {c.pool_type === "public" && c.assigned_to === null ? (
                    <button
                      type="button"
                      disabled={claimingId === c.id}
                      onClick={() => handleClaim(c.id)}
                      className="text-xs font-medium text-white px-2 py-1 disabled:opacity-40"
                      style={{
                        background: "var(--color-primary)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      {claimingId === c.id ? "认领中…" : "认领"}
                    </button>
                  ) : (
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {c.assigned_to !== null ? "已认领" : "—"}
                    </span>
                  )}
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
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
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
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
