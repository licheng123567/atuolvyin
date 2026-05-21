// v0.5.6 — 服务商案件看板视图(按 stage 分列)
//
// 6 列对应 6 stage:待联系 / 跟进中 / 承诺缴费 / 已缴费 / 升级中 / 已关闭
// 每张卡片:业主名 + 房号 + 金额 + 月数 + 分配状态 + 点击进详情
// 数据源:GET /provider/cases?page_size=200(不分页,一次拿够;后续若超 200 加分页)
// v0.7.0:加按项目过滤;卡片显项目名小标签
import { useCustom, useGo, useList } from "@refinedev/core";
import { ArrowLeft, FolderKanban, KanbanSquare } from "lucide-react";
import { useState } from "react";
import { PriorityBadge } from "../../../components/ui/PriorityBadge";  // v0.7.0
import type { PaginatedResponse } from "../../../types";

interface CaseItem {
  id: number;
  project_id: number | null;  // v0.7.0
  project_name: string | null;  // v0.7.0
  owner: { name: string; building: string | null; room: string | null };
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  assigned_to_name?: string | null;  // v0.7.0 A.3 后端补
  assigned_to: number | null;
  pool_type: string;
  priority_score: number;
}

interface ProviderProjectOption {
  project_id: number;
  project_name: string;
}

const STAGES: Array<{ key: string; label: string; color: string }> = [
  { key: "new", label: "待联系", color: "#6b7280" },
  { key: "in_progress", label: "跟进中", color: "#2563eb" },
  { key: "promised", label: "承诺缴费", color: "#d97706" },
  { key: "paid", label: "已缴费", color: "#16a34a" },
  { key: "escalated", label: "升级中", color: "#dc2626" },
  { key: "closed", label: "已关闭", color: "#9ca3af" },
];

export function ProviderCasesKanbanPage() {
  const go = useGo();
  const [projectId, setProjectId] = useState<number | "">("");  // v0.7.0

  const { query: projectsQuery } = useList<ProviderProjectOption>({
    resource: "provider/projects",
    queryOptions: { staleTime: 10 * 60 * 1000 },
  });
  const projectsRaw = projectsQuery.data?.data;
  const projectOptions: ProviderProjectOption[] =
    (projectsRaw as unknown as { items?: ProviderProjectOption[] })?.items
    ?? (projectsRaw as ProviderProjectOption[] | undefined)
    ?? [];

  const { query } = useCustom<PaginatedResponse<CaseItem>>({
    url: "provider/cases",
    method: "get",
    config: {
      query: {
        page: 1,
        page_size: 200,
        project_id: projectId !== "" ? projectId : undefined,
      },
    },
  });
  const items = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  // 按 stage 分组
  const grouped: Record<string, CaseItem[]> = {};
  for (const s of STAGES) grouped[s.key] = [];
  for (const c of items) {
    if (grouped[c.stage]) grouped[c.stage].push(c);
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => go({ to: "/provider/cases" })}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          列表视图
        </button>
        <span style={{ margin: "0 6px", color: "var(--color-neutral-400)" }}>›</span>
        <KanbanSquare className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          案件看板
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">共 {total} 单</span>
        {total > 200 && (
          <span className="text-xs text-[var(--color-warning)]">
            (仅展示前 200 单;完整请回列表视图按阶段筛选)
          </span>
        )}
        {/* v0.7.0 — 按项目过滤 */}
        <span className="ml-auto text-sm text-[var(--color-neutral-700)] flex items-center gap-1">
          <FolderKanban className="w-3.5 h-3.5" />项目:
        </span>
        <select
          value={projectId}
          onChange={(e) =>
            setProjectId(e.target.value === "" ? "" : Number(e.target.value))
          }
          className="px-3 py-1 text-xs border border-[var(--color-neutral-300)] rounded bg-white"
          style={{ maxWidth: 240 }}
        >
          <option value="">全部项目</option>
          {projectOptions.map((p) => (
            <option key={p.project_id} value={p.project_id}>
              {p.project_name}
            </option>
          ))}
        </select>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${STAGES.length}, minmax(180px, 1fr))`,
          gap: 12,
          overflowX: "auto",
        }}
      >
        {STAGES.map((s) => (
          <div
            key={s.key}
            style={{
              background: "var(--color-neutral-50)",
              border: "1px solid var(--color-neutral-200)",
              borderRadius: 8,
              padding: 10,
              minHeight: 200,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 8,
                paddingBottom: 8,
                borderBottom: `2px solid ${s.color}`,
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 600, color: s.color }}>
                {s.label}
              </span>
              <span style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
                {grouped[s.key].length}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {grouped[s.key].length === 0 ? (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--color-neutral-400)",
                    padding: "12px 0",
                    textAlign: "center",
                  }}
                >
                  暂无
                </div>
              ) : (
                grouped[s.key].map((c) => (
                  <div
                    key={c.id}
                    onClick={() => go({ to: `/provider/cases/${c.id}` })}
                    style={{
                      background: "white",
                      border: "1px solid var(--color-neutral-200)",
                      borderRadius: 6,
                      padding: 10,
                      cursor: "pointer",
                      fontSize: 12.5,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--color-neutral-50)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "white";
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{c.owner.name}</div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--color-neutral-500)",
                        marginTop: 2,
                      }}
                    >
                      {[c.owner.building, c.owner.room].filter(Boolean).join(" ")}
                    </div>
                    {/* v0.7.0 — 项目名小标签(切项目快捷) */}
                    {c.project_name && (
                      <div
                        style={{
                          fontSize: 10,
                          color: "var(--color-primary)",
                          marginTop: 2,
                        }}
                        title={`项目:${c.project_name}`}
                      >
                        📁 {c.project_name}
                      </div>
                    )}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginTop: 6,
                      }}
                    >
                      <span style={{ fontFamily: "monospace", color: "#dc2626", fontWeight: 600 }}>
                        ¥{c.amount_owed ?? "0"}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--color-neutral-500)" }}>
                        欠 {c.months_overdue ?? 0} 月
                      </span>
                    </div>
                    {/* v0.7.0 — 加优先级 badge + 分配状态 */}
                    <div
                      style={{
                        marginTop: 6,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        flexWrap: "wrap",
                      }}
                    >
                      <PriorityBadge score={c.priority_score} showScore={false} />
                      <span
                        style={{
                          fontSize: 10,
                          color: c.assigned_to
                            ? "var(--color-success)"
                            : "var(--color-warning)",
                        }}
                      >
                        {c.assigned_to_name
                          ? `已分配:${c.assigned_to_name}`
                          : c.assigned_to
                            ? "已分配"
                            : "未分配"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ProviderCasesKanbanPage;
