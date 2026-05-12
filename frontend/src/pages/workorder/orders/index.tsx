// v1.9.6 — 工单列表（协调员/物业管理员）UI 统一到法务列表范式：
//   page-header + KPI 卡 + ds-tabs（状态）+ table-toolbar（搜索/类型/优先级）+ table-wrap
import { useCustom, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Eye, Inbox, RotateCcw } from "lucide-react";
import { useState } from "react";
import { SearchInput } from "../../../components/ui/SearchInput";
import type { PaginatedResponse } from "../../../types";
import {
  WORK_ORDER_PRIORITIES,
  WORK_ORDER_TYPES,
  formatPriority,
  formatStatus,
  formatType,
  getPriorityColor,
  getStatusColor,
} from "./helpers";

interface WorkOrderItem {
  id: number;
  case_id: number | null;
  call_id: number | null;
  order_type: string;
  description: string;
  assigned_to: number | null;
  status: string;
  priority: string;
  resolution: string | null;
  assignee_name: string | null;
  created_at: string;
  // v1.9.7 — 列表行内案件上下文
  owner_name: string | null;
  owner_room: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
}

interface ProjectOption {
  id: number;
  name: string;
}

interface KpiData {
  open_count: number;
  in_progress_count: number;
  closed_this_month: number;
  avg_processing_days: number | null;
}

type TabValue = "open" | "in_progress" | "closed" | "all";

const TABS: { v: TabValue; label: string; statusFilter: string[] }[] = [
  { v: "open", label: "待处理", statusFilter: ["open"] },
  { v: "in_progress", label: "处理中", statusFilter: ["in_progress"] },
  { v: "closed", label: "已完成", statusFilter: ["resolved", "closed"] },
  { v: "all", label: "全部", statusFilter: [] },
];

const PAGE_SIZE = 20;

export function WorkOrderListPage() {
  const go = useGo();
  const [tab, setTab] = useState<TabValue>("open");
  const [keyword, setKeyword] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [page, setPage] = useState(1);

  const currentTab = TABS.find((t) => t.v === tab) ?? TABS[0];
  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  // tab 决定 status；若 statusFilter 多于 1（e.g. closed = resolved+closed）后端目前只接受单个
  // → 先按 resolved；用户切到 closed 后还可点详情看到所有已结束订单
  if (currentTab.statusFilter.length === 1) {
    filters.push({ field: "status", operator: "eq", value: currentTab.statusFilter[0] });
  }
  if (typeFilter) filters.push({ field: "order_type", operator: "eq", value: typeFilter });
  if (priorityFilter) filters.push({ field: "priority", operator: "eq", value: priorityFilter });
  if (projectFilter) filters.push({ field: "project_id", operator: "eq", value: projectFilter });

  const { query } = useList<WorkOrderItem>({
    resource: "workorders",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const { query: kpiQuery } = useCustom<KpiData>({
    url: "workorders/kpi",
    method: "get",
  });
  const kpi = kpiQuery.data?.data;

  // v1.9.7 — 拉项目列表用于「按项目过滤」下拉
  const { query: projectsQuery } = useCustom<{ items: ProjectOption[] }>({
    url: "admin/projects",
    method: "get",
    config: { query: { page_size: 200 } },
  });
  const projectOptions = projectsQuery.data?.data?.items ?? [];

  const rawData = query.data?.data;
  let items: WorkOrderItem[] =
    (rawData as unknown as PaginatedResponse<WorkOrderItem>)?.items ??
    (rawData as WorkOrderItem[] | undefined) ??
    [];
  // 「已完成」tab 客户端再过滤一次，把 closed 也包进来（后端按单一 status 过滤）
  if (tab === "closed") {
    items = items.filter((wo) => wo.status === "resolved" || wo.status === "closed");
  }
  const total = query.data?.total ?? items.length;
  const isLoading = query.isLoading;

  const filtersDirty = !!keyword || !!typeFilter || !!priorityFilter || !!projectFilter;
  function resetFilters() {
    setKeyword(""); setTypeFilter(""); setPriorityFilter(""); setProjectFilter(""); setPage(1);
  }

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h1 className="page-title">工单管理</h1>
        <p className="page-subtitle">
          催收员从案件发起工单（含工单原因）→ 协调员在此处理（添加跟进 / 解决方案 / 关闭）。处理过程同步到案件活动时间线。
        </p>
      </div>

      {/* KPI 卡 */}
      {kpi && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
          <KpiCard label="待处理" value={kpi.open_count} suffix="单" tone="orange" />
          <KpiCard label="处理中" value={kpi.in_progress_count} suffix="单" tone="primary" />
          <KpiCard label="本月完成" value={kpi.closed_this_month} suffix="单" tone="green" />
          <KpiCard
            label="本月平均处理时长"
            value={kpi.avg_processing_days ?? "—"}
            suffix={kpi.avg_processing_days != null ? "天" : ""}
            tone="neutral"
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
        <div className="table-toolbar">
          <SearchInput
            value={keyword}
            onChange={(v) => { setKeyword(v); setPage(1); }}
            placeholder="搜索业主 / 房号 / 工单原因"
            width={240}
          />
          <select
            className="form-control"
            style={{ width: 180 }}
            value={projectFilter}
            onChange={(e) => { setProjectFilter(e.target.value); setPage(1); }}
          >
            <option value="">全部项目</option>
            {projectOptions.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ width: 130 }}
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          >
            <option value="">全部类型</option>
            {WORK_ORDER_TYPES.map((t) => (
              <option key={t} value={t}>{formatType(t)}</option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ width: 130 }}
            value={priorityFilter}
            onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}
          >
            <option value="">全部优先级</option>
            {WORK_ORDER_PRIORITIES.map((p) => (
              <option key={p} value={p}>{formatPriority(p)}</option>
            ))}
          </select>
          <button
            type="button"
            className="ds-btn ds-btn-ghost ds-btn-sm"
            onClick={resetFilters}
            disabled={!filtersDirty}
          >
            <RotateCcw className="w-3.5 h-3.5" /> 重置
          </button>
        </div>

        <table>
          <thead>
            <tr>
              <th>工单号</th>
              <th>业主</th>
              <th>房号</th>
              <th>项目</th>
              <th>类型</th>
              <th>工单原因</th>
              <th style={{ textAlign: "right" }}>欠费</th>
              <th>状态</th>
              <th>优先级</th>
              <th>负责人</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={11} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>加载中…</td></tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={11} style={{ textAlign: "center", padding: 40, color: "var(--color-neutral-400)" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <Inbox className="w-8 h-8" style={{ color: "var(--color-neutral-300)" }} />
                    <span>暂无工单</span>
                  </div>
                </td>
              </tr>
            )}
            {!isLoading && items.map((wo) => (
              <tr key={wo.id}>
                <td style={{ color: "var(--color-neutral-600)", fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                  #{wo.id}
                </td>
                <td>
                  {wo.owner_name ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                </td>
                <td>{wo.owner_room ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}</td>
                <td style={{ fontSize: 12, color: "var(--color-neutral-600)", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={wo.project_name ?? undefined}>
                  {wo.project_name ?? <span style={{ color: "var(--color-neutral-400)" }}>—</span>}
                </td>
                <td>{formatType(wo.order_type)}</td>
                <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={wo.description}>
                  {wo.description}
                </td>
                <td style={{ textAlign: "right", fontWeight: 600, color: wo.amount_owed ? "#dc2626" : "var(--color-neutral-400)" }}>
                  {wo.amount_owed ? `¥${Number(wo.amount_owed).toLocaleString("zh-CN")}` : "—"}
                </td>
                <td>
                  <span style={{ ...getStatusColor(wo.status), padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 500 }}>
                    {formatStatus(wo.status)}
                  </span>
                </td>
                <td>
                  <span style={{ ...getPriorityColor(wo.priority), padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 500 }}>
                    {formatPriority(wo.priority)}
                  </span>
                </td>
                <td>{wo.assignee_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未分配</span>}</td>
                <td>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => go({ to: `/workorder/orders/${wo.id}` })}
                  >
                    <Eye className="w-3 h-3" /> 处理
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {total > PAGE_SIZE && (
          <div style={{ padding: "10px 16px", borderTop: "1px solid var(--color-neutral-200)", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >上一页</button>
            <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
              第 {page} / {Math.ceil(total / PAGE_SIZE)} 页 · 共 {total} 单
            </span>
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / PAGE_SIZE)}
            >下一页</button>
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
