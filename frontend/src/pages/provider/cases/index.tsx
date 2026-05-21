// v0.5.6 — 服务商管理员案件列表页
//
// 数据源:GET /api/v1/provider/cases(后端按 Project.provider_id == 本服务商过滤)
// 操作:只读 + 分配/重新分配(右侧 ReassignDrawer)+ 释放回公海(详情页里);本期不开放
// 修改 stage / 跟进备注 / 发缴费链接 等(产品决策见 PRD §13.x 服务商 admin 范围)
import { useCustom, useGetIdentity, useGo } from "@refinedev/core";
import { Briefcase, Filter, Inbox, KanbanSquare, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import type { AuthUser } from "../../../providers/auth-provider";
import { ProviderAssignDrawer } from "./ProviderAssignDrawer";
import { PriorityBadge } from "../../../components/ui/PriorityBadge";  // v0.7.0
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
  project_id: number | null;
  project_name: string | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  assigned_to_name?: string | null;  // v0.7.0 后端 JOIN user.name
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at: string | null;
  status: string;
  tenant_id: number;
  provider_id: number | null;
  provider_name: string | null;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待联系",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级中",
  closed: "已关闭",
};

const STAGE_BADGE: Record<string, string> = {
  new: "ds-badge ds-badge-gray",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-orange",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-red",
  closed: "ds-badge ds-badge-gray",
};

interface Props {
  /** v0.5.6 — true 时强制 pool_type=public,作为「公海」视图复用本组件 */
  poolViewOnly?: boolean;
}

export function ProviderCasesPage({ poolViewOnly = false }: Props = {}) {
  const go = useGo();
  const { data: identity } = useGetIdentity<AuthUser>();
  const [stage, setStage] = useState<string>("");
  const [poolType, setPoolType] = useState<string>(poolViewOnly ? "public" : "");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [assignCase, setAssignCase] = useState<CaseItem | null>(null);

  const { query } = useCustom<PaginatedResponse<CaseItem>>({
    url: "provider/cases",
    method: "get",
    config: {
      query: {
        stage: stage || undefined,
        pool_type: poolViewOnly ? "public" : (poolType || undefined),
        keyword: keyword || undefined,
        page,
        page_size: 30,
      },
    },
  });

  const items = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        {poolViewOnly ? (
          <Inbox className="w-6 h-6 text-[var(--color-primary)]" />
        ) : (
          <Briefcase className="w-6 h-6 text-[var(--color-primary)]" />
        )}
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          {poolViewOnly ? "服务商公海(本服务商接手项目)" : "案件管理(本服务商接手项目)"}
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">共 {total} 单</span>
        {!poolViewOnly && (
          <button
            type="button"
            className="ml-auto ds-btn ds-btn-secondary ds-btn-sm"
            onClick={() => go({ to: "/provider/cases/kanban" })}
          >
            <KanbanSquare className="w-3.5 h-3.5" />
            看板视图
          </button>
        )}
      </div>

      {/* 过滤区 */}
      <div className="flex flex-wrap items-center gap-2 bg-white border border-[var(--color-neutral-200)] rounded-lg px-4 py-3">
        <Filter className="w-4 h-4 text-[var(--color-neutral-500)]" />
        <span className="text-sm text-[var(--color-neutral-700)]">阶段:</span>
        {Object.entries(STAGE_LABELS).map(([val, label]) => (
          <button
            key={val}
            type="button"
            onClick={() => setStage(stage === val ? "" : val)}
            className={`px-3 py-1 text-xs rounded transition ${
              stage === val
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-neutral-50)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]"
            }`}
          >
            {label}
          </button>
        ))}

        {!poolViewOnly && (
          <>
            <span className="text-sm text-[var(--color-neutral-700)] ml-3">归属:</span>
            <button
              type="button"
              onClick={() => setPoolType(poolType === "public" ? "" : "public")}
              className={`px-3 py-1 text-xs rounded transition ${
                poolType === "public"
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-neutral-50)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]"
              }`}
            >
              公海
            </button>
            <button
              type="button"
              onClick={() => setPoolType(poolType === "private" ? "" : "private")}
              className={`px-3 py-1 text-xs rounded transition ${
                poolType === "private"
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-neutral-50)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]"
              }`}
            >
              已分配
            </button>
          </>
        )}

        <div className="ml-auto flex items-center gap-2">
          <Search className="w-4 h-4 text-[var(--color-neutral-500)]" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="按业主姓名 / 房号搜索"
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-300)] rounded"
          />
        </div>
      </div>

      {/* 表格 */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            加载中…
          </div>
        )}
        {!query.isLoading && items.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            暂无案件
          </div>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-[var(--color-neutral-600)] text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">业主 / 房号</th>
                <th className="px-4 py-3 text-left">欠费 / 月数</th>
                <th className="px-4 py-3 text-left">阶段</th>
                <th className="px-4 py-3 text-left">归属</th>
                <th className="px-4 py-3 text-left">分配给</th>
                <th className="px-4 py-3 text-left">优先级</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {items.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-[var(--color-neutral-50)] cursor-pointer"
                  onClick={() => go({ to: `/provider/cases/${c.id}` })}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium">{c.owner.name}</div>
                    <div className="text-xs text-[var(--color-neutral-500)]">
                      {[c.owner.building, c.owner.room].filter(Boolean).join(" ")}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-mono">¥{c.amount_owed ?? "0"}</div>
                    <div className="text-xs text-[var(--color-neutral-500)]">
                      欠 {c.months_overdue ?? 0} 个月
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={STAGE_BADGE[c.stage] ?? "ds-badge ds-badge-gray"}>
                      {STAGE_LABELS[c.stage] ?? c.stage}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {c.pool_type === "public" ? (
                      <span className="text-[var(--color-warning)]">公海</span>
                    ) : (
                      <span className="text-[var(--color-success)]">私海</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {c.assigned_to_name
                      ? <span title={`user #${c.assigned_to}`}>{c.assigned_to_name}</span>
                      : c.assigned_to
                        ? <span title={`user #${c.assigned_to}`}>已分配</span>
                        : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <PriorityBadge score={c.priority_score} />
                  </td>
                  <td
                    className="px-4 py-3"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={() => setAssignCase(c)}
                      className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] rounded hover:bg-[var(--color-neutral-50)]"
                    >
                      <UserCheck className="w-3 h-3" />
                      {c.assigned_to ? "重新分配" : "分配"}
                    </button>
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

      {assignCase && (
        <ProviderAssignDrawer
          caseId={assignCase.id}
          ownerName={assignCase.owner.name}
          currentAssignedTo={assignCase.assigned_to}
          onClose={() => setAssignCase(null)}
          onDone={() => {
            setAssignCase(null);
            query.refetch();
          }}
        />
      )}
      {identity?.role !== "admin" && null /* 防止 react warning,实际本页守卫 require_provider_roles */}
    </div>
  );
}

export function ProviderPoolPage() {
  return <ProviderCasesPage poolViewOnly />;
}

export default ProviderCasesPage;
