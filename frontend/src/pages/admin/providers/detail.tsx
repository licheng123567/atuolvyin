// 物业管理员 - 服务商详情：成员配置 / 配额调整 / 合同状态（PRD §3.9）
import { useCustom, useCustomMutation, useGo, useInvalidate } from "@refinedev/core";
import { AlertTriangle, ArrowLeft, Save, ToggleLeft, ToggleRight, Users, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

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
  agent_external: "外部催收员",
  legal: "法务专员",
};

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

  const [contractStatus, setContractStatus] = useState<string>(provider?.status ?? "active");
  const [contractExpires, setContractExpires] = useState<string>(
    provider?.expires_at?.slice(0, 10) ?? "",
  );

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
