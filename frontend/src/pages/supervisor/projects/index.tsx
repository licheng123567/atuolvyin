// v1.5 S18.5 — 督导项目卡片视图（自己被加入的项目）
import { useCustom, useGo } from "@refinedev/core";
import { ChevronRight, FolderOpen } from "lucide-react";
import type { PaginatedResponse } from "../../../types";

interface ProjectItem {
  id: number;
  name: string;
  status: string;
  case_count: number;
  provider_name: string | null;
  description: string | null;
}

const STATUS_LABELS: Record<string, string> = {
  active: "进行中",
  paused: "暂停",
  closed: "已结束",
};

const STATUS_BADGE: Record<string, string> = {
  active: "ds-badge ds-badge-green",
  paused: "ds-badge ds-badge-orange",
  closed: "ds-badge ds-badge-gray",
};

export function SupervisorProjectsPage() {
  const go = useGo();
  // 通过 admin/projects 列表（supervisor 当前没有专属端点；权限上后端不区分项目读取）
  // 但 supervisor 看的范围由后端 admin/cases supervisor 守卫保证；此处展示所有项目+
  // 高亮自己被加入的（通过逐项目调 members 查询太重，改为后端 list 时按角色过滤）。
  // MVP：直接展示所有项目，配合提示文案；v1.6 加 GET /supervisor/projects 专属端点。
  const { query } = useCustom<PaginatedResponse<ProjectItem>>({
    url: "admin/projects",
    method: "get",
    config: { query: { page_size: 100 } },
  });
  const projects = query.data?.data?.items ?? [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">我的项目</h1>
          <div className="page-subtitle">
            督导可见自己被加入项目的所有案件 / 通话 / 工单
          </div>
        </div>
      </div>

      {query.isLoading && (
        <div style={{ textAlign: "center", padding: 48, color: "#9ca3af" }}>
          加载中…
        </div>
      )}

      {!query.isLoading && projects.length === 0 && (
        <div className="ds-card">
          <div
            className="card-body"
            style={{ textAlign: "center", padding: 48, color: "#9ca3af" }}
          >
            <FolderOpen
              className="w-10 h-10"
              style={{ display: "inline-block", marginBottom: 12 }}
            />
            <div>还没有任何项目</div>
            <div style={{ fontSize: 13, marginTop: 8 }}>
              请联系物业管理员把您加入项目督导组
            </div>
          </div>
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          gap: 16,
        }}
      >
        {projects.map((p) => (
          <div
            key={p.id}
            className="ds-card"
            style={{ cursor: "pointer", transition: "transform .15s" }}
            onClick={() => go({ to: `/admin/cases?project_id=${p.id}` })}
            onMouseEnter={(e) =>
              (e.currentTarget.style.transform = "translateY(-2px)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.transform = "translateY(0)")
            }
          >
            <div
              className="card-body"
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: "#111827" }}>
                    {p.name}
                  </div>
                  {p.description && (
                    <div
                      style={{
                        fontSize: 12,
                        color: "#6b7280",
                        marginTop: 4,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}
                    >
                      {p.description}
                    </div>
                  )}
                </div>
                <span
                  className={STATUS_BADGE[p.status] ?? "ds-badge ds-badge-gray"}
                >
                  {STATUS_LABELS[p.status] ?? p.status}
                </span>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 16,
                  fontSize: 13,
                  color: "#374151",
                }}
              >
                <div>
                  <span style={{ color: "#9ca3af" }}>案件</span>{" "}
                  <strong>{p.case_count}</strong>
                </div>
                <div>
                  <span style={{ color: "#9ca3af" }}>服务商</span>{" "}
                  {p.provider_name ?? <span style={{ color: "#9ca3af" }}>自营</span>}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 12,
                  color: "var(--color-primary)",
                  marginTop: "auto",
                }}
              >
                查看案件
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

