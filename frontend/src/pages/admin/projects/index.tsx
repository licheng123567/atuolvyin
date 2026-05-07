// 物业项目管理 — v1.4 Project 一等公民
import { useGo, useList } from "@refinedev/core";
import { Pencil, Plus } from "lucide-react";
import { useState } from "react";
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
  allow_internal_assist: boolean;
  case_count: number;
  created_at: string;
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
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">项目管理</h1>
          <div className="page-subtitle">共 {total} 个项目</div>
        </div>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          onClick={() => go({ to: "/admin/projects/new" })}
        >
          <Plus className="w-3.5 h-3.5" />
          新建项目
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>项目名称</th>
              <th>项目负责人(物业)</th>
              <th>合作服务商</th>
              <th>项目负责人(服务商)</th>
              <th>案件数</th>
              <th>状态</th>
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
                  {p.provider_id && p.allow_internal_assist && (
                    <span
                      className="ds-badge ds-badge-blue"
                      style={{ marginLeft: 6, fontSize: 10 }}
                      title="本项目允许物业内勤协助"
                    >
                      内勤协助
                    </span>
                  )}
                </td>
                <td>{p.provider_pm_name ?? "—"}</td>
                <td>{p.case_count}</td>
                <td>
                  <span className={STATUS_BADGE[p.status] ?? "ds-badge ds-badge-gray"}>
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
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

        {totalPages > 1 && (
          <div className="ds-pagination">
            <span className="pagination-info">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((x) => x - 1)}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div className="page-btn" onClick={() => setPage((x) => x + 1)}>
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
