// 物业管理员 - 服务商详情：成员配置 / 配额调整 / 合同状态（PRD §3.9）
// v1.5.6 — 加合作项目 + 合作案件下钻
import { useCustom, useCustomMutation, useGo, useInvalidate, useList } from "@refinedev/core";
import { AlertTriangle, ArrowLeft, Briefcase, FileStack, Save, ToggleLeft, ToggleRight, Users, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import type { PaginatedResponse } from "../../../types";

interface ProviderMember {
  user_id: number;
  name: string;
  phone_masked: string;
  role: string;
  quota: number | null;
  expire_at: string | null;
  access_hours: string | null;
  is_active: boolean;
}

interface SignedProvider {
  provider_id: number;
  provider_name: string;
  provider_type: string;
  contract_id: number;
  signed_at: string;
  expires_at: string | null;
  service_types: string[];
  status: "active" | "paused" | "terminated";
  member_count: number;
}

interface TerminationStatus {
  contract_id: number;
  status: string;
  termination_requested_by: number | null;
  termination_requested_at: string | null;
  termination_reason: string | null;
  termination_confirmed_at: string | null;
  terminated_at: string | null;
  timeout_days_remaining: number | null;
}

const ROLE_LABEL: Record<string, string> = {
  // agent covers both internal and external; work_mode distinguishes them
  agent: "催收员",
  legal: "法务专员",
};

const PROJECT_STATUS_LABEL: Record<string, string> = {
  active: "进行中",
  paused: "暂停",
  closed: "已结束",
};

const PROJECT_STATUS_BADGE: Record<string, string> = {
  active: "ds-badge ds-badge-green",
  paused: "ds-badge ds-badge-orange",
  closed: "ds-badge ds-badge-gray",
};

const STAGE_LABEL: Record<string, string> = {
  new: "新单",
  contacting: "联系中",
  promised: "已承诺",
  paid: "已结清",
  legal: "已转法务",
  closed: "已关闭",
  unreachable: "失联",
};

interface ProjectRow {
  id: number;
  name: string;
  status: string;
  case_count: number;
  plan_end: string | null;
  property_pm_name: string | null;
}

interface CaseRow {
  id: number;
  project_id: number | null;
  owner: { name: string; phone_masked: string; building: string | null; room: string | null };
  stage: string;
  amount_owed: number | string;
  months_overdue: number | null;
  assigned_to: number | null;
}

export function AdminProviderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const providerId = Number(id);
  const go = useGo();
  const invalidate = useInvalidate();

  const { query: signedQuery } = useCustom<SignedProvider[]>({
    url: "admin/providers",
    method: "get",
  });
  const provider =
    signedQuery.data?.data?.find((p) => p.provider_id === providerId) ?? null;

  const { query: membersQuery } = useCustom<ProviderMember[]>({
    url: `admin/providers/${providerId}/members`,
    method: "get",
  });
  const members = membersQuery.data?.data ?? [];

  // v1.5.6 — 合作项目（按 provider_id 过滤）
  const { query: projectsQuery } = useList<ProjectRow>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
    filters: [{ field: "provider_id", operator: "eq", value: providerId }],
    queryOptions: { enabled: Number.isFinite(providerId) },
  });
  const projectsRaw = projectsQuery.data?.data;
  const projects: ProjectRow[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectRow>)?.items ??
    (projectsRaw as ProjectRow[] | undefined) ??
    [];

  // v1.5.6 — 合作案件（按 provider_id 过滤，预览取前 10 条）
  const CASE_PREVIEW_SIZE = 10;
  const { query: casesQuery } = useList<CaseRow>({
    resource: "admin/cases",
    pagination: { currentPage: 1, pageSize: CASE_PREVIEW_SIZE },
    filters: [{ field: "provider_id", operator: "eq", value: providerId }],
    queryOptions: { enabled: Number.isFinite(providerId) },
  });
  const casesRaw = casesQuery.data?.data;
  const cases: CaseRow[] =
    (casesRaw as unknown as PaginatedResponse<CaseRow>)?.items ??
    (casesRaw as CaseRow[] | undefined) ??
    [];
  const totalCases = casesQuery.data?.total ?? 0;
  const totalCaseAmount = cases.reduce(
    (sum, c) => sum + Number(c.amount_owed ?? 0),
    0,
  );

  const [contractStatus, setContractStatus] = useState<string>(provider?.status ?? "active");
  const [contractExpires, setContractExpires] = useState<string>(
    provider?.expires_at?.slice(0, 10) ?? "",
  );
  // v1.5.6 — tab 化
  type TabKey = "overview" | "projects" | "cases" | "members" | "contract";
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  // Sync server-provided values into form once on first load only
  // (subsequent edits live in local state until "保存"); ref-based init flag
  // avoids set-state-in-effect cascading.
  const initRef = useRef(false);
  useEffect(() => {
    if (provider && !initRef.current) {
      initRef.current = true;
      setContractStatus(provider.status);
      setContractExpires(provider.expires_at?.slice(0, 10) ?? "");
    }
  }, [provider]);

  const { mutate: patchContract, mutation: contractMutation } = useCustomMutation();
  const { mutate: patchMember } = useCustomMutation();

  // v1.4 S16.4 — 双向解约握手
  const { query: termQuery } = useCustom<TerminationStatus>({
    url: `admin/providers/${providerId}/termination-status`,
    method: "get",
  });
  const term = termQuery.data?.data;
  const { mutate: termAction, mutation: termMutation } = useCustomMutation();
  const [showTermDialog, setShowTermDialog] = useState(false);
  const [termReason, setTermReason] = useState("");

  function refreshTerm() {
    void termQuery.refetch();
    void invalidate({ resource: "admin/providers", invalidates: ["all"] });
  }

  const requestTerminate = () => {
    termAction(
      {
        url: `admin/providers/${providerId}/terminate-request`,
        method: "post",
        values: { reason: termReason.trim() || null },
      },
      {
        onSuccess: () => {
          setShowTermDialog(false);
          setTermReason("");
          refreshTerm();
        },
      },
    );
  };

  const confirmTerminate = () => {
    termAction(
      {
        url: `admin/providers/${providerId}/terminate-confirm`,
        method: "post",
        values: {},
      },
      {
        onSuccess: refreshTerm,
      },
    );
  };

  const saveContract = () => {
    patchContract(
      {
        url: `admin/providers/${providerId}/contract`,
        method: "patch",
        values: {
          status: contractStatus,
          expires_at: contractExpires
            ? new Date(contractExpires).toISOString()
            : null,
        },
      },
      {
        onSuccess: () => {
          invalidate({ resource: "admin/providers", invalidates: ["all"] });
        },
      },
    );
  };

  const updateMember = (
    userId: number,
    patch: Partial<{ quota: number; access_hours: string; is_active: boolean }>,
  ) => {
    patchMember(
      {
        url: `admin/providers/${providerId}/members/${userId}`,
        method: "patch",
        values: patch,
      },
      {
        onSuccess: () => membersQuery.refetch(),
      },
    );
  };

  if (signedQuery.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!provider) {
    return (
      <div className="p-6">
        <p className="text-sm text-red-600">未与该服务商签约或服务商不存在</p>
        <button
          type="button"
          className="mt-3 text-sm text-[var(--color-primary)]"
          onClick={() => go({ to: "/admin/providers" })}
        >
          ← 返回列表
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <button
        type="button"
        onClick={() => go({ to: "/admin/providers" })}
        className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)]"
      >
        <ArrowLeft className="w-4 h-4" /> 返回服务商列表
      </button>

      <header>
        <h1 className="text-2xl font-semibold text-[var(--color-neutral-900)]">
          {provider.provider_name}
        </h1>
        <p className="text-sm text-[var(--color-neutral-500)] mt-1">
          签约于 {provider.signed_at?.slice(0, 10)} · 服务范围：
          {provider.service_types.join(" / ")}
        </p>
      </header>

      {/* v1.5.6 — KPI 概览条 */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}
      >
        <KpiTile
          label="合作项目"
          value={projects.length}
          unit="个"
          tone={projects.length === 0 ? "muted" : "primary"}
        />
        <KpiTile
          label="承接案件"
          value={totalCases}
          unit="单"
          tone={totalCases === 0 ? "muted" : "primary"}
        />
        <KpiTile
          label="服务商成员"
          value={members.length}
          unit="人"
          tone={members.length === 0 ? "muted" : "primary"}
        />
        <KpiTile
          label="合同状态"
          value={
            provider.status === "active"
              ? "合作中"
              : provider.status === "paused"
                ? "已暂停"
                : "已终止"
          }
          tone={
            provider.status === "active"
              ? "success"
              : provider.status === "paused"
                ? "warning"
                : "danger"
          }
        />
        <KpiTile
          label="服务期到"
          value={
            provider.expires_at
              ? provider.expires_at.slice(0, 10)
              : "长期"
          }
          tone="muted"
        />
      </div>

      {/* v1.5.6 — 解约 pending 时的全局横幅（任何 tab 都看见）*/}
      {term &&
        term.status !== "terminated" &&
        term.termination_requested_at &&
        !term.termination_confirmed_at && (
          <button
            type="button"
            onClick={() => setActiveTab("contract")}
            className="w-full text-left flex items-center gap-2 p-3 text-sm"
            style={{
              background: "var(--color-warning-light, #fef3c7)",
              border: "1px solid var(--color-warning, #f59e0b)",
              borderRadius: "var(--radius-md)",
              color: "#92400e",
            }}
          >
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>
              {term.termination_requested_by === 1 ? (
                <>解约请求已发出，等待服务商确认（剩 {term.timeout_days_remaining ?? 0} 天）</>
              ) : (
                <>服务商已申请解约，请在剩余 {term.timeout_days_remaining ?? 0} 天内确认</>
              )}
              <span className="ml-2 underline">→ 处理</span>
            </span>
          </button>
        )}

      {/* v1.5.6 — Tab bar */}
      <div
        className="flex gap-1 border-b border-[var(--color-neutral-200)]"
        style={{ paddingBottom: 0 }}
      >
        {(
          [
            { key: "overview", label: "概览" },
            { key: "projects", label: `合作项目 (${projects.length})` },
            { key: "cases", label: `合作案件 (${totalCases})` },
            { key: "members", label: `成员 (${members.length})` },
            { key: "contract", label: "合同 / 解约" },
          ] as { key: TabKey; label: string }[]
        ).map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            className="px-4 py-2 text-sm"
            style={{
              borderBottom:
                activeTab === t.key
                  ? "2px solid var(--color-primary)"
                  : "2px solid transparent",
              color:
                activeTab === t.key
                  ? "var(--color-primary)"
                  : "var(--color-neutral-600)",
              fontWeight: activeTab === t.key ? 600 : 400,
              background: "transparent",
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 概览 tab：简易 README + 引导到各 tab */}
      {activeTab === "overview" && (
        <section
          className="bg-white p-5 border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <h2 className="text-base font-semibold mb-3">概览</h2>
          <div className="text-sm text-[var(--color-neutral-700)] space-y-2">
            <p>
              <strong>{provider.provider_name}</strong> 为本租户承接{" "}
              <button type="button" onClick={() => setActiveTab("projects")} className="text-[var(--color-primary)] underline">
                {projects.length} 个项目
              </button>，共{" "}
              <button type="button" onClick={() => setActiveTab("cases")} className="text-[var(--color-primary)] underline">
                {totalCases} 单案件
              </button>，{" "}
              <button type="button" onClick={() => setActiveTab("members")} className="text-[var(--color-primary)] underline">
                {members.length} 名成员
              </button>{" "}
              在本公司活跃。
            </p>
            <p className="text-xs text-[var(--color-neutral-500)]">
              切换上方 tab 进入对应详情。需要终止合作请到「合同 / 解约」tab。
            </p>
          </div>
        </section>
      )}

      {activeTab === "contract" && (
      <>
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <h2 className="text-base font-semibold mb-3">合同设置</h2>
        <div className="grid grid-cols-2 gap-4 max-w-xl">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              合同状态
            </label>
            <select
              value={contractStatus}
              onChange={(e) => setContractStatus(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
              disabled={provider.status === "terminated"}
            >
              <option value="active">合作中</option>
              <option value="paused">暂停</option>
              {provider.status === "terminated" && (
                <option value="terminated">已终止</option>
              )}
            </select>
            <p style={{ fontSize: 11, color: "var(--color-neutral-400)", marginTop: 4 }}>
              终止合作请使用下方「申请解约」流程（双向握手 + 7 天超时）
            </p>
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              到期日期
            </label>
            <input
              type="date"
              value={contractExpires}
              onChange={(e) => setContractExpires(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        </div>
        <div className="mt-4">
          <button
            type="button"
            onClick={saveContract}
            disabled={contractMutation.isPending || provider.status === "terminated"}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Save className="w-4 h-4" />
            {contractMutation.isPending ? "保存中…" : "保存合同变更"}
          </button>
        </div>
      </section>

      {/* v1.4 S16.4 — 解约状态机 */}
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-4 h-4 text-[var(--color-warning, #f59e0b)]" />
          <h2 className="text-base font-semibold">解约管理</h2>
        </div>

        {!term && termQuery.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
        )}

        {term && term.status === "terminated" && (
          <div
            style={{
              background: "var(--color-danger-light, #fee2e2)",
              border: "1px solid var(--color-danger, #ef4444)",
              borderRadius: "var(--radius-md)",
              padding: "10px 14px",
              fontSize: 13,
            }}
          >
            合作已于 {term.terminated_at?.slice(0, 10)} 终止。服务商在 30
            天内对历史数据只读，60 天后自动软删；业主姓名/手机号已对服务商不可见。
          </div>
        )}

        {term && term.status !== "terminated" && term.termination_requested_at === null && (
          <div className="space-y-3">
            <p className="text-sm text-[var(--color-neutral-600)]">
              服务商可见业主信息，可拨打、查阅本租户案件。如需结束合作，
              请发起解约 — 服务商需在 7 天内确认，逾期自动终止。
            </p>
            <button
              type="button"
              onClick={() => setShowTermDialog(true)}
              className="px-3 py-2 text-sm font-medium border"
              style={{
                borderColor: "var(--color-danger, #ef4444)",
                color: "var(--color-danger, #ef4444)",
                background: "white",
                borderRadius: "var(--radius-md)",
              }}
            >
              申请解约
            </button>
          </div>
        )}

        {term &&
          term.status !== "terminated" &&
          term.termination_requested_at &&
          !term.termination_confirmed_at && (
            <div
              style={{
                background: "var(--color-warning-light, #fef3c7)",
                border: "1px solid var(--color-warning, #f59e0b)",
                borderRadius: "var(--radius-md)",
                padding: "12px 14px",
                fontSize: 13,
              }}
            >
              <p style={{ marginBottom: 8 }}>
                {term.termination_requested_by === 1 ? (
                  <>
                    <strong>解约请求已发出</strong>，等待服务商确认（剩余{" "}
                    {term.timeout_days_remaining ?? 0} 天，超时自动终止）。
                  </>
                ) : (
                  <>
                    <strong>服务商已申请解约</strong>，请在 7 天内确认（剩余{" "}
                    {term.timeout_days_remaining ?? 0} 天）。
                  </>
                )}
              </p>
              {term.termination_reason && (
                <p style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
                  理由：{term.termination_reason}
                </p>
              )}
              {term.termination_requested_by === 2 && (
                <button
                  type="button"
                  disabled={termMutation.isPending}
                  onClick={confirmTerminate}
                  className="mt-2 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  style={{
                    background: "var(--color-danger, #ef4444)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  {termMutation.isPending ? "处理中…" : "确认解约"}
                </button>
              )}
            </div>
          )}
      </section>
      </>
      )}

      {showTermDialog && (
        <div className="modal-overlay" onClick={() => setShowTermDialog(false)}>
          <div
            className="bg-white p-6 w-[480px]"
            style={{ borderRadius: "var(--radius-lg)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">申请解约</h3>
              <button
                type="button"
                onClick={() => setShowTermDialog(false)}
                className="text-[var(--color-neutral-400)]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <p style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 12 }}>
              发出后服务商需在 7 天内确认；逾期自动转「已终止」。终止后服务商
              30 天内可查看历史，60 天后数据软删。
            </p>
            <textarea
              value={termReason}
              onChange={(e) => setTermReason(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="解约理由（可选，对方可见）"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => setShowTermDialog(false)}
                className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={requestTerminate}
                disabled={termMutation.isPending}
                className="px-3 py-2 text-sm text-white disabled:opacity-50"
                style={{
                  background: "var(--color-danger, #ef4444)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                {termMutation.isPending ? "提交中…" : "确认申请解约"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* v1.5.6 — 合作项目 */}
      {activeTab === "projects" && (
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Briefcase className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">合作项目</h2>
          <span className="text-xs text-[var(--color-neutral-400)]">
            共 {projects.length} 个
          </span>
        </div>
        {projectsQuery.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
        )}
        {!projectsQuery.isLoading && projects.length === 0 && (
          <p className="text-sm text-[var(--color-neutral-400)]">
            暂无项目外包给该服务商
          </p>
        )}
        {projects.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-[var(--color-neutral-500)]">
              <tr>
                <th className="py-2 font-medium">项目名称</th>
                <th className="py-2 font-medium">物业项目负责人</th>
                <th className="py-2 font-medium">案件数</th>
                <th className="py-2 font-medium">服务期到</th>
                <th className="py-2 font-medium">状态</th>
                <th className="py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {projects.map((p) => (
                <tr key={p.id} className="text-[var(--color-neutral-700)]">
                  <td className="py-2 font-medium">{p.name}</td>
                  <td className="py-2">{p.property_pm_name ?? "—"}</td>
                  <td className="py-2">{p.case_count}</td>
                  <td className="py-2 text-[var(--color-neutral-500)]">
                    {p.plan_end ? p.plan_end.slice(0, 10) : "长期"}
                  </td>
                  <td className="py-2">
                    <span className={PROJECT_STATUS_BADGE[p.status] ?? "ds-badge"}>
                      {PROJECT_STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </td>
                  <td className="py-2">
                    <button
                      type="button"
                      className="text-xs text-[var(--color-primary)] hover:underline"
                      onClick={() => go({ to: `/admin/projects/${p.id}/edit` })}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="ml-3 text-xs text-[var(--color-primary)] hover:underline"
                      onClick={() => go({ to: `/admin/cases?project_id=${p.id}` })}
                    >
                      查看案件
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      )}

      {/* v1.5.6 — 合作案件预览 */}
      {activeTab === "cases" && (
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <FileStack className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">合作案件</h2>
          <span className="text-xs text-[var(--color-neutral-400)]">
            共 {totalCases} 单 · 预览金额合计 ¥{totalCaseAmount.toLocaleString("zh-CN")}
          </span>
          <button
            type="button"
            onClick={() => go({ to: `/admin/cases?provider_id=${providerId}` })}
            className="ml-auto text-xs text-[var(--color-primary)] hover:underline"
          >
            查看全部 →
          </button>
        </div>
        {casesQuery.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
        )}
        {!casesQuery.isLoading && cases.length === 0 && (
          <p className="text-sm text-[var(--color-neutral-400)]">
            该服务商当前没有承接案件
          </p>
        )}
        {cases.length > 0 && (
          <>
            <table className="w-full text-sm">
              <thead className="text-left text-[var(--color-neutral-500)]">
                <tr>
                  <th className="py-2 font-medium">业主</th>
                  <th className="py-2 font-medium">楼栋/房号</th>
                  <th className="py-2 font-medium">欠费金额</th>
                  <th className="py-2 font-medium">欠费月数</th>
                  <th className="py-2 font-medium">阶段</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-neutral-100)]">
                {cases.map((c) => (
                  <tr key={c.id} className="text-[var(--color-neutral-700)]">
                    <td className="py-2">
                      <div className="font-medium">{c.owner.name}</div>
                      <div className="text-xs text-[var(--color-neutral-500)]">
                        {c.owner.phone_masked}
                      </div>
                    </td>
                    <td className="py-2 text-[var(--color-neutral-500)]">
                      {c.owner.building ?? "—"}
                      {c.owner.room ? `-${c.owner.room}` : ""}
                    </td>
                    <td className="py-2">¥{Number(c.amount_owed).toLocaleString("zh-CN")}</td>
                    <td className="py-2">{c.months_overdue ?? "—"} 月</td>
                    <td className="py-2">
                      <span className="ds-badge ds-badge-gray" style={{ fontSize: 11 }}>
                        {STAGE_LABEL[c.stage] ?? c.stage}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {totalCases > CASE_PREVIEW_SIZE && (
              <p className="text-xs text-[var(--color-neutral-400)] mt-3">
                仅显示前 {CASE_PREVIEW_SIZE} 条 · 还有 {totalCases - CASE_PREVIEW_SIZE} 条
                <button
                  type="button"
                  className="ml-2 text-[var(--color-primary)] hover:underline"
                  onClick={() => go({ to: `/admin/cases?provider_id=${providerId}` })}
                >
                  查看全部
                </button>
              </p>
            )}
          </>
        )}
      </section>
      )}

      {activeTab === "members" && (
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">服务商成员（在本公司）</h2>
          <span className="text-xs text-[var(--color-neutral-400)]">
            共 {members.length} 人
          </span>
        </div>

        {membersQuery.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
        )}
        {!membersQuery.isLoading && members.length === 0 && (
          <p className="text-sm text-[var(--color-neutral-400)]">
            暂无该服务商的成员被分配到本公司
          </p>
        )}

        {members.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-[var(--color-neutral-500)]">
              <tr>
                <th className="py-2 font-medium">姓名</th>
                <th className="py-2 font-medium">手机</th>
                <th className="py-2 font-medium">角色</th>
                <th className="py-2 font-medium">配额（分钟/月）</th>
                <th className="py-2 font-medium">访问时段</th>
                <th className="py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {members.map((m) => (
                <MemberRow
                  key={m.user_id}
                  member={m}
                  onSave={(patch) => updateMember(m.user_id, patch)}
                />
              ))}
            </tbody>
          </table>
        )}
      </section>
      )}
    </div>
  );
}

function KpiTile({
  label,
  value,
  unit,
  tone = "muted",
}: {
  label: string;
  value: number | string;
  unit?: string;
  tone?: "primary" | "success" | "warning" | "danger" | "muted";
}) {
  const toneColors: Record<string, string> = {
    primary: "var(--color-primary)",
    success: "#16a34a",
    warning: "#d97706",
    danger: "#dc2626",
    muted: "var(--color-neutral-700)",
  };
  return (
    <div
      className="bg-white p-3 border border-[var(--color-neutral-200)]"
      style={{ borderRadius: "var(--radius-lg)" }}
    >
      <div className="text-xs text-[var(--color-neutral-500)]">{label}</div>
      <div
        className="mt-1 font-semibold"
        style={{ fontSize: 18, color: toneColors[tone] }}
      >
        {value}
        {unit && <span style={{ fontSize: 12, marginLeft: 2, fontWeight: 400 }}>{unit}</span>}
      </div>
    </div>
  );
}

function MemberRow({
  member,
  onSave,
}: {
  member: ProviderMember;
  onSave: (patch: { quota?: number; access_hours?: string; is_active?: boolean }) => void;
}) {
  const [quota, setQuota] = useState(member.quota ?? 0);
  const [accessHours, setAccessHours] = useState(member.access_hours ?? "");
  const dirty =
    quota !== (member.quota ?? 0) || accessHours !== (member.access_hours ?? "");

  return (
    <tr className="text-[var(--color-neutral-700)]">
      <td className="py-2 font-medium">{member.name}</td>
      <td className="py-2 text-[var(--color-neutral-500)]">{member.phone_masked}</td>
      <td className="py-2">{ROLE_LABEL[member.role] ?? member.role}</td>
      <td className="py-2">
        <input
          type="number"
          min={0}
          value={quota}
          onChange={(e) => setQuota(Number(e.target.value))}
          className="w-24 px-2 py-1 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </td>
      <td className="py-2">
        <input
          type="text"
          placeholder="09:00-18:00"
          value={accessHours}
          onChange={(e) => setAccessHours(e.target.value)}
          className="w-32 px-2 py-1 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </td>
      <td className="py-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onSave({ is_active: !member.is_active })}
          className="text-[var(--color-primary)]"
          aria-label={member.is_active ? "停用" : "启用"}
        >
          {member.is_active ? (
            <ToggleRight className="w-6 h-6 text-[var(--color-success)]" />
          ) : (
            <ToggleLeft className="w-6 h-6 text-[var(--color-neutral-400)]" />
          )}
        </button>
        {dirty && (
          <button
            type="button"
            onClick={() => onSave({ quota, access_hours: accessHours })}
            className="text-xs px-2 py-1 text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            保存
          </button>
        )}
      </td>
    </tr>
  );
}
