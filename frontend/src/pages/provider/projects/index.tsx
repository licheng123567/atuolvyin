// v1.5.7 — 服务商工作台「我的项目」：列表 + 指派项目经理 + 设置佣金率
// v0.7.0 — 加「详情」按钮跳 /provider/projects/{id}(只读详情页)
import { useCustom, useCustomMutation, useList } from "@refinedev/core";
import { Building2, Eye, FolderKanban, Percent, UserCheck, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";
import type { PaginatedResponse } from "../../../types";

interface ProviderProjectItem {
  project_id: number;
  project_name: string;
  tenant_name: string;
  plan_start: string | null;
  plan_end: string | null;
  provider_pm_user_id: number | null;
  provider_pm_name: string | null;
  provider_agent_commission_rate: string | null;
}

interface ProviderProjectsResp {
  items: ProviderProjectItem[];
}

interface TeamMember {
  user_id: number;
  name: string;
  phone_masked: string;
  role: string;
}

function dateOnly(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

// v0.7.0 — 服务期 badge(对齐物业 admin/projects 风格:剩余 <7 天红 / 30 天橙 / 长期绿)
function servicePeriodBadge(plan_end: string | null): { cls: string; label: string } {
  if (!plan_end) return { cls: "ds-badge ds-badge-green", label: "长期合作" };
  const days = Math.floor((new Date(plan_end).getTime() - Date.now()) / (24 * 3600 * 1000));
  if (days < 0) return { cls: "ds-badge ds-badge-gray", label: `已到期 ${-days} 天` };
  if (days < 7) return { cls: "ds-badge ds-badge-red", label: `剩余 ${days} 天 ⚠` };
  if (days < 30) return { cls: "ds-badge ds-badge-orange", label: `剩余 ${days} 天` };
  return { cls: "ds-badge ds-badge-green", label: `剩余 ${days} 天` };
}

export function ProviderProjectsPage() {
  const navigate = useNavigate();
  const customResult = useCustom<ProviderProjectsResp>({
    url: "provider/projects",
    method: "get",
  });
  const query = customResult.query;
  const refetch = () => customResult.query.refetch();
  const items = query.data?.data?.items ?? [];

  const [assignFor, setAssignFor] = useState<ProviderProjectItem | null>(null);
  const [rateFor, setRateFor] = useState<ProviderProjectItem | null>(null);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <FolderKanban className="inline w-4 h-4 mr-1" style={{ verticalAlign: "-3px" }} />
            我的项目
          </h1>
          <div className="page-subtitle">
            物业方派发的项目；由您指派本家项目经理（PM）跟进
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>项目名称</th>
              <th>合作物业</th>
              <th>服务期</th>
              <th>项目经理</th>
              <th>服务商佣金率</th>
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
                  暂无合作项目
                </td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.project_id}>
                <td>
                  <strong>{p.project_name}</strong>
                </td>
                <td>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <Building2 className="w-3.5 h-3.5" style={{ color: "#9ca3af" }} />
                    {p.tenant_name}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: "#6b7280" }}>
                  <div>{dateOnly(p.plan_start)} → {dateOnly(p.plan_end)}</div>
                  {(() => {
                    const meta = servicePeriodBadge(p.plan_end);
                    return (
                      <span className={meta.cls} style={{ fontSize: 10, marginTop: 2, display: "inline-block" }}>
                        {meta.label}
                      </span>
                    );
                  })()}
                </td>
                <td>
                  {p.provider_pm_name ? (
                    <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
                      <UserCheck className="inline w-3 h-3" style={{ verticalAlign: "-2px", marginRight: 2 }} />
                      {p.provider_pm_name}
                    </span>
                  ) : (
                    <span style={{ color: "#e02424", fontSize: 12 }}>未指派</span>
                  )}
                </td>
                <td style={{ fontSize: 13 }}>
                  {p.provider_agent_commission_rate == null ? (
                    <span style={{ color: "#9ca3af", fontSize: 12 }}>继承默认 5%</span>
                  ) : (
                    <span style={{ fontWeight: 500 }}>
                      {(Number(p.provider_agent_commission_rate) * 100).toFixed(1)}%
                    </span>
                  )}
                </td>
                <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {/* v0.7.0 — 详情(只读)放最前,最常用 */}
                  <button
                    type="button"
                    className="ds-btn ds-btn-primary ds-btn-sm"
                    onClick={() => navigate(`/provider/projects/${p.project_id}`)}
                    title="查看项目详情:KPI / 收费 / 合同 / 团队 / 案件列表(只读)"
                  >
                    <Eye className="inline w-3 h-3" style={{ verticalAlign: "-2px", marginRight: 2 }} />
                    详情
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => setAssignFor(p)}
                  >
                    {p.provider_pm_user_id ? "重新指派" : "指派项目经理"}
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    onClick={() => setRateFor(p)}
                  >
                    <Percent className="inline w-3 h-3" style={{ verticalAlign: "-2px", marginRight: 2 }} />
                    设置佣金率
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {assignFor && (
        <AssignPmModal
          project={assignFor}
          onClose={() => setAssignFor(null)}
          onSuccess={() => {
            setAssignFor(null);
            refetch();
          }}
        />
      )}
      {rateFor && (
        <CommissionRateModal
          project={rateFor}
          onClose={() => setRateFor(null)}
          onSuccess={() => {
            setRateFor(null);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function AssignPmModal({
  project,
  onClose,
  onSuccess,
}: {
  project: ProviderProjectItem;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [pmId, setPmId] = useState<number | "">(project.provider_pm_user_id ?? "");
  const [errMsg, setErrMsg] = useState("");
  const { mutate: assign, mutation } = useCustomMutation();

  // 拉本服务商的 pm_provider 角色员工
  const { query: teamQuery } = useList<TeamMember>({
    resource: "provider/team",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const rawTeam = teamQuery.data?.data;
  const teamItems: TeamMember[] =
    (rawTeam as unknown as PaginatedResponse<TeamMember>)?.items ??
    (rawTeam as TeamMember[] | undefined) ??
    [];
  // project_manager on provider-side (scope=provider:{id}); backend /provider/team filters by provider
  const pmCandidates = teamItems.filter((m) => m.role === "project_manager");

  const handleSave = () => {
    if (pmId === "") {
      setErrMsg("请选择项目经理");
      return;
    }
    setErrMsg("");
    assign(
      {
        url: `provider/projects/${project.project_id}/pm`,
        method: "patch",
        values: { user_id: pmId },
      },
      {
        onSuccess: () => onSuccess(),
        onError: (e) => {
          const msg = (e as { response?: { data?: { message?: string } } }).response?.data?.message;
          setErrMsg(msg ?? "指派失败");
        },
      },
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="ds-modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">指派项目经理</span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ fontSize: 13, color: "#6b7280" }}>
            项目：<strong style={{ color: "#374151" }}>{project.project_name}</strong>
          </div>
          <div>
            <label className="form-label">选择项目经理（本服务商）*</label>
            <SearchableSelect
              value={pmId}
              placeholder="请选择"
              onChange={(v) => setPmId(v === "" ? "" : Number(v))}
              options={pmCandidates.map((m) => ({
                value: m.user_id,
                label: m.name,
                subtitle: m.phone_masked,
              }))}
            />
            {pmCandidates.length === 0 && (
              <div className="form-hint" style={{ color: "#d97706" }}>
                ⚠ 您还没有「项目经理」角色的员工。请先到「团队管理」创建。
              </div>
            )}
          </div>
          {errMsg && <div style={{ color: "#e02424", fontSize: 13 }}>{errMsg}</div>}
        </div>
        <div className="modal-footer">
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            disabled={mutation.isPending || pmId === ""}
            onClick={handleSave}
          >
            {mutation.isPending ? "保存中…" : "确认指派"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CommissionRateModal({
  project,
  onClose,
  onSuccess,
}: {
  project: ProviderProjectItem;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const initialPct =
    project.provider_agent_commission_rate != null
      ? (Number(project.provider_agent_commission_rate) * 100).toFixed(2)
      : "";
  const [pct, setPct] = useState<string>(initialPct);
  const [errMsg, setErrMsg] = useState("");
  const { mutate: save, mutation } = useCustomMutation();

  const handleSave = () => {
    if (pct !== "" && !Number.isFinite(Number(pct))) {
      setErrMsg("请输入有效数字");
      return;
    }
    if (pct !== "" && (Number(pct) < 0 || Number(pct) > 100)) {
      setErrMsg("佣金率须在 0–100% 之间");
      return;
    }
    setErrMsg("");
    save(
      {
        url: `provider/projects/${project.project_id}/commission-rate`,
        method: "patch",
        values: {
          provider_agent_commission_rate:
            pct === "" ? null : Number(pct) / 100,
        },
      },
      {
        onSuccess: () => onSuccess(),
        onError: (e) => {
          const msg = (
            e as { response?: { data?: { message?: string } } }
          ).response?.data?.message;
          setErrMsg(msg ?? "设置失败");
        },
      },
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="ds-modal"
        style={{ maxWidth: 400 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span className="modal-title">设置服务商佣金率</span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div
          className="modal-body"
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <div style={{ fontSize: 13, color: "#6b7280" }}>
            项目：<strong style={{ color: "#374151" }}>{project.project_name}</strong>
          </div>
          <div>
            <label className="form-label">服务商催收员佣金率（%）</label>
            <input
              type="number"
              className="form-control"
              min={0}
              max={100}
              step={0.01}
              value={pct}
              placeholder="留空则继承默认 5%"
              onChange={(e) => setPct(e.target.value)}
              style={{ width: "100%" }}
            />
            <div className="form-hint" style={{ color: "#9ca3af" }}>
              填写百分比数值，如 10 表示 10%。留空则使用系统默认（5%）。
            </div>
          </div>
          {errMsg && (
            <div style={{ color: "#e02424", fontSize: 13 }}>{errMsg}</div>
          )}
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            onClick={onClose}
          >
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            disabled={mutation.isPending}
            onClick={handleSave}
          >
            {mutation.isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
