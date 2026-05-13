// 物业项目管理 — v1.4 Project 一等公民
// v1.6.5 — 复用统一 PaginationBar 组件
import { useGo, useList } from "@refinedev/core";
import { Download, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { exportToCsv } from "../../../lib/csv";
import type { PaginatedResponse } from "../../../types";

interface ProjectItem {
  id: number;
  name: string;
  provider_id: number | null;
  provider_name: string | null;
  property_pm_user_id: number | null;
  property_pm_name: string | null;
  provider_pm_user_id: number | null;
  provider_pm_name: string | null;
  status: string;
  case_count: number;
  created_at: string;
  plan_start?: string | null;
  plan_end?: string | null;
}

function servicePeriodBadge(planEnd: string | null | undefined, status: string): { label: string; cls: string; tooltip: string } {
  if (status === "closed") return { label: "已结束", cls: "ds-badge ds-badge-gray", tooltip: "项目已关闭" };
  if (!planEnd) return { label: "长期合作", cls: "ds-badge ds-badge-green", tooltip: "未设服务期，按长期合作处理" };
  const end = new Date(planEnd).getTime();
  const now = Date.now();
  const days = Math.ceil((end - now) / (1000 * 60 * 60 * 24));
  if (days < 0) return { label: "已到期", cls: "ds-badge ds-badge-gray", tooltip: `服务期 ${planEnd.slice(0, 10)} 已到期` };
  if (days <= 7) return { label: `剩 ${days} 天`, cls: "ds-badge ds-badge-red", tooltip: "即将到期，请提前续约" };
  if (days <= 30) return { label: `剩 ${days} 天`, cls: "ds-badge ds-badge-orange", tooltip: "服务期 30 天内到期" };
  return { label: `剩 ${days} 天`, cls: "ds-badge ds-badge-green", tooltip: `服务期至 ${planEnd.slice(0, 10)}` };
}

const STATUS_BADGE: Record<string, string> = {
  active: "ds-badge ds-badge-green",
  paused: "ds-badge ds-badge-orange",
  closed: "ds-badge ds-badge-gray",
};

const STATUS_LABELS: Record<string, string> = {
  active: "进行中",
  paused: "暂停",
  closed: "已结束",
};

export function AdminProjectListPage() {
  const go = useGo();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { query } = useList<ProjectItem>({
    resource: "admin/projects",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: ProjectItem[] =
    (rawData as unknown as PaginatedResponse<ProjectItem>)?.items ??
    (rawData as ProjectItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">项目管理</h1>
          <div className="page-subtitle">共 {total} 个项目</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            disabled={items.length === 0}
            onClick={() =>
              exportToCsv(
                `projects-${new Date().toISOString().slice(0, 10)}.csv`,
                [
                  { key: "id", label: "项目ID" },
                  { key: "name", label: "项目名称" },
                  { key: "property_pm_name", label: "物业项目负责人" },
                  { key: "provider_name", label: "服务商" },
                  { key: "case_count", label: "案件数" },
                  { key: "status", label: "状态" },
                  { key: "plan_end", label: "服务期到" },
                ],
                items.map((p) => ({
                  id: p.id,
                  name: p.name,
                  property_pm_name: p.property_pm_name ?? "",
                  provider_name: p.provider_name ?? "",
                  case_count: p.case_count,
                  status: STATUS_LABELS[p.status] ?? p.status,
                  plan_end: p.plan_end ?? "",
                })),
              )
            }
          >
            <Download className="w-3.5 h-3.5" />
            导出 CSV
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={() => go({ to: "/admin/projects/new" })}
          >
            <Plus className="w-3.5 h-3.5" />
            新建项目
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>项目名称</th>
              <th>项目负责人(物业)</th>
              <th>合作服务商</th>
              <th>案件数</th>
              <th>状态</th>
              <th>服务期</th>
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
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  还没有项目，点击右上角「新建项目」开始
                </td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.name}</strong>
                </td>
                <td>{p.property_pm_name ?? "—"}</td>
                <td>
                  {p.provider_name ?? <span style={{ color: "#9ca3af" }}>未指派</span>}
                </td>
                <td>{p.case_count}</td>
                <td>
                  <span className={STATUS_BADGE[p.status] ?? "ds-badge ds-badge-gray"}>
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
                </td>
                <td>
                  {(() => {
                    const b = servicePeriodBadge(p.plan_end, p.status);
                    return (
                      <span className={b.cls} title={b.tooltip} style={{ fontSize: 11 }}>
                        {b.label}
                      </span>
                    );
                  })()}
                </td>
                <td>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => go({ to: `/admin/cases?project_id=${p.id}` })}
                  >
                    查看案件
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => go({ to: `/admin/projects/${p.id}/edit` })}
                    style={{ marginLeft: 4 }}
                  >
                    <Pencil className="w-3 h-3" />
                    编辑
                  </button>
                </td>
              </tr>
            ))}
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
