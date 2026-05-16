// 物业 admin 审计日志中心 — v1.5.7
import { useCustom } from "@refinedev/core";
import { Search, X } from "lucide-react";
import { useState } from "react";
import { exportToCsv } from "../../../lib/csv";

interface AuditLogItem {
  id: number;
  actor_user_id: number | null;
  actor_role: string | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

interface AuditLogList {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

const ACTION_LABEL: Record<string, string> = {
  "user.created": "创建用户",
  "user.updated": "更新用户",
  "user.deactivated": "停用用户",
  "project.created": "创建项目",
  "project.updated": "更新项目",
  "project.provider.assigned": "项目-绑定/解除服务商",
  "project.plan_end.changed": "服务期变更",
  "case.assigned": "案件分配",
  "case.released": "案件释放",
  "case.imported": "导入案件",
  "provider.recommended": "推荐服务商",
  "provider.contract.terminate_requested": "申请解约",
  "provider.contract.terminate_confirmed": "确认解约",
  "provider.contract.terminated": "解约生效",
  "settlement.created": "生成结算单",
  "settlement.confirmed": "确认结算",
  "settlement.paid": "标记已付",
  "workorder.auto_assigned": "工单自动派单",
  "script.created": "新建话术",
  "script.updated": "更新话术",
};

const ROLE_LABEL: Record<string, string> = {
  admin: "管理员",
  supervisor: "督导",
  agent: "催收员",
  legal: "法务",
  coordinator: "协调员",
  workorder: "协调员",
  project_manager: "项目经理",
  superadmin: "平台超管",
  ops: "平台运营",
};

export function AdminAuditLogPage() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 30;
  const [actionFilter, setActionFilter] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const queryParams: Record<string, string | number> = {
    page,
    page_size: PAGE_SIZE,
  };
  if (actionFilter) queryParams.action = actionFilter;
  if (targetTypeFilter) queryParams.target_type = targetTypeFilter;
  if (since) queryParams.since = `${since}T00:00:00Z`;
  if (until) queryParams.until = `${until}T23:59:59Z`;

  const { query } = useCustom<AuditLogList>({
    url: "admin/audit-logs",
    method: "get",
    config: { query: queryParams },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function handleExport() {
    exportToCsv(
      `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`,
      [
        { key: "created_at", label: "时间" },
        { key: "actor", label: "操作人" },
        { key: "action_label", label: "动作" },
        { key: "action", label: "原始动作" },
        { key: "target", label: "对象" },
        { key: "payload_text", label: "数据" },
      ],
      items.map((it) => ({
        created_at: new Date(it.created_at).toLocaleString("zh-CN"),
        actor: it.actor_user_id
          ? `${ROLE_LABEL[it.actor_role ?? ""] ?? it.actor_role ?? ""} #${it.actor_user_id}`
          : "—",
        action_label: ACTION_LABEL[it.action] ?? it.action,
        action: it.action,
        target: it.target_type ? `${it.target_type}#${it.target_id ?? ""}` : "—",
        payload_text: it.payload ? JSON.stringify(it.payload) : "",
      })),
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">审计日志</h1>
          <div className="page-subtitle">本租户所有关键操作事件，按时间倒序 · 共 {total} 条</div>
        </div>
        <button
          type="button"
          onClick={handleExport}
          className="ds-btn ds-btn-secondary"
          disabled={items.length === 0}
        >
          导出 CSV
        </button>
      </div>

      <div className="table-wrap">
        <div className="table-toolbar" style={{ flexWrap: "wrap", gap: 8 }}>
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              type="text"
              className="form-control"
              placeholder="动作关键词，如：project / settlement / terminate"
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              style={{ minWidth: 240 }}
            />
          </div>
          <select
            className="form-control"
            style={{ width: 140 }}
            value={targetTypeFilter}
            onChange={(e) => {
              setTargetTypeFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部对象类型</option>
            <option value="project">项目</option>
            <option value="case">案件</option>
            <option value="user">用户</option>
            <option value="service_provider">服务商</option>
            <option value="provider_tenant_contract">合同</option>
            <option value="settlement">结算</option>
            <option value="work_order">工单</option>
          </select>
          <input
            type="date"
            className="form-control"
            style={{ width: 150 }}
            value={since}
            onChange={(e) => {
              setSince(e.target.value);
              setPage(1);
            }}
            placeholder="起始日期"
          />
          <span style={{ fontSize: 12, color: "#9ca3af" }}>至</span>
          <input
            type="date"
            className="form-control"
            style={{ width: 150 }}
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              setPage(1);
            }}
            placeholder="结束日期"
          />
          {(actionFilter || targetTypeFilter || since || until) && (
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={() => {
                setActionFilter("");
                setTargetTypeFilter("");
                setSince("");
                setUntil("");
                setPage(1);
              }}
            >
              <X className="w-3.5 h-3.5" />
              清除筛选
            </button>
          )}
        </div>

        <table>
          <thead>
            <tr>
              <th style={{ width: 160 }}>时间</th>
              <th style={{ width: 140 }}>操作人</th>
              <th style={{ width: 200 }}>动作</th>
              <th style={{ width: 180 }}>对象</th>
              <th>数据</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无审计事件
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.id}>
                <td style={{ fontSize: 12, color: "#6b7280" }}>
                  {new Date(it.created_at).toLocaleString("zh-CN")}
                </td>
                <td style={{ fontSize: 12 }}>
                  {it.actor_user_id ? (
                    <>
                      <span className="ds-badge ds-badge-blue" style={{ fontSize: 10 }}>
                        {ROLE_LABEL[it.actor_role ?? ""] ?? it.actor_role ?? "未知"}
                      </span>
                      <span style={{ marginLeft: 4, color: "#9ca3af" }}>#{it.actor_user_id}</span>
                    </>
                  ) : (
                    <span style={{ color: "#9ca3af" }}>系统</span>
                  )}
                </td>
                <td>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>
                    {ACTION_LABEL[it.action] ?? it.action}
                  </div>
                  <div style={{ fontSize: 11, color: "#9ca3af", fontFamily: "monospace" }}>
                    {it.action}
                  </div>
                </td>
                <td style={{ fontSize: 12, color: "#374151" }}>
                  {it.target_type ? (
                    <code style={{ background: "#f3f4f6", padding: "1px 6px", borderRadius: 3 }}>
                      {it.target_type}#{it.target_id ?? ""}
                    </code>
                  ) : (
                    "—"
                  )}
                </td>
                <td style={{ fontSize: 12 }}>
                  {it.payload && Object.keys(it.payload).length > 0 ? (
                    <details>
                      <summary style={{ cursor: "pointer", color: "#6366f1" }}>展开</summary>
                      <pre
                        style={{
                          background: "#f9fafb",
                          padding: 8,
                          borderRadius: 4,
                          fontSize: 11,
                          marginTop: 4,
                          maxWidth: 480,
                          overflow: "auto",
                        }}
                      >
                        {JSON.stringify(it.payload, null, 2)}
                      </pre>
                    </details>
                  ) : (
                    <span style={{ color: "#9ca3af" }}>—</span>
                  )}
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
