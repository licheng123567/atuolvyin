// 物业管理员 - 服务商合作管理（PRD §3.9 / L2044）
import { useCustom, useCustomMutation, useGo, useInvalidate } from "@refinedev/core";
import { Building2, MailPlus, Plus, Search, UserPlus, X } from "lucide-react";
import { useMemo, useState } from "react";

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

interface AvailableProvider {
  id: number;
  name: string;
  provider_type: string;
  description: string | null;
  contact_email: string | null;
}

const PROVIDER_TYPE_LABEL: Record<string, string> = {
  legal: "法务",
  collection: "催收",
  both: "法务+催收",
};

const STATUS_LABEL: Record<string, string> = {
  active: "合作中",
  paused: "已暂停",
  terminated: "已终止",
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  active: { bg: "var(--color-success-light)", color: "var(--color-success)" },
  paused: { bg: "var(--color-warning-light)", color: "var(--color-warning)" },
  terminated: { bg: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function AdminProvidersPage() {
  const go = useGo();
  const [q, setQ] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [showRecommend, setShowRecommend] = useState(false);

  const { query: signedQuery } = useCustom<SignedProvider[]>({
    url: "admin/providers",
    method: "get",
    config: q ? { query: { q } } : undefined,
  });

  const items = signedQuery.data?.data ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            服务商合作管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {items.length} 家
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRecommend(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium border"
            style={{
              borderColor: "var(--color-neutral-200)",
              color: "var(--color-neutral-700)",
              borderRadius: "var(--radius-md)",
              background: "white",
            }}
            title="平台尚未收录的服务商，可推荐其入驻（需 ops 审批）"
          >
            <MailPlus className="w-4 h-4" />
            推荐入驻
          </button>
          <button
            type="button"
            onClick={() => setShowInvite(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <UserPlus className="w-4 h-4" />
            邀请新服务商
          </button>
        </div>
      </div>

      <div className="relative mb-4 max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          placeholder="按名称搜索…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">服务商</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">类型</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">服务范围</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">签约时间</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">到期时间</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">成员数</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">状态</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {signedQuery.isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!signedQuery.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  尚未签约任何服务商
                </td>
              </tr>
            )}
            {items.map((p) => {
              const style = STATUS_STYLE[p.status] ?? STATUS_STYLE.active;
              return (
                <tr
                  key={p.provider_id}
                  className="hover:bg-[var(--color-neutral-50)] cursor-pointer"
                  onClick={() => go({ to: `/admin/providers/${p.provider_id}` })}
                >
                  <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                    {p.provider_name}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {PROVIDER_TYPE_LABEL[p.provider_type] ?? p.provider_type}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {p.service_types.join(" / ")}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {p.signed_at?.slice(0, 10)}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {p.expires_at ? p.expires_at.slice(0, 10) : "—"}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">{p.member_count}</td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                      style={{ background: style.bg, color: style.color }}
                    >
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showInvite && <InviteDialog onClose={() => setShowInvite(false)} />}
      {showRecommend && <RecommendDialog onClose={() => setShowRecommend(false)} />}
    </div>
  );
}

function RecommendDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [providerType, setProviderType] = useState<"collection" | "legal" | "both">(
    "collection",
  );
  const [adminPhone, setAdminPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const { mutate: recommend, mutation } = useCustomMutation();

  const submit = () => {
    setError(null);
    if (!name.trim()) {
      setError("请填写服务商名称");
      return;
    }
    if (!/^1[3-9]\d{9}$/.test(adminPhone)) {
      setError("请填写有效的 11 位手机号");
      return;
    }
    recommend(
      {
        url: "admin/providers/recommend",
        method: "post",
        values: {
          name: name.trim(),
          provider_type: providerType,
          admin_phone: adminPhone,
          contact_email: contactEmail.trim() || null,
          description: description.trim() || null,
        },
      },
      {
        onSuccess: () => {
          setSubmitted(true);
        },
        onError: () => {
          setError("提交失败，请稍后重试");
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="bg-white p-6 w-[480px] max-h-[80vh] overflow-auto"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">推荐服务商入驻</h2>
          <button type="button" onClick={onClose} className="text-[var(--color-neutral-400)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        {submitted ? (
          <div className="space-y-3">
            <p className="text-sm text-[var(--color-neutral-700)]">
              ✅ 推荐已提交，平台 ops 审批通过后您可在「邀请新服务商」中选中并签约。
            </p>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 text-sm text-white"
                style={{
                  background: "var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                好
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-[var(--color-neutral-500)]">
              如果意向合作的服务商尚未在平台收录，可在此处推荐。提交后平台 ops
              将审核其资质（一般 1-3 工作日）。
            </p>

            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                服务商名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：聚英催收团队"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>

            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                业务类型 <span className="text-red-500">*</span>
              </label>
              <select
                value={providerType}
                onChange={(e) =>
                  setProviderType(e.target.value as "collection" | "legal" | "both")
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                <option value="collection">催收</option>
                <option value="legal">法务</option>
                <option value="both">法务+催收</option>
              </select>
            </div>

            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                联系人手机号 <span className="text-red-500">*</span>
              </label>
              <input
                type="tel"
                value={adminPhone}
                onChange={(e) => setAdminPhone(e.target.value)}
                placeholder="11 位手机号"
                maxLength={11}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>

            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                联系邮箱（选填）
              </label>
              <input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>

            <div>
              <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
                简介 / 资质（选填）
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="经营年限、主要案例、营业执照编号等"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                取消
              </button>
              <button
                type="button"
                disabled={mutation.isPending}
                onClick={submit}
                className="flex items-center gap-1.5 px-3 py-2 text-sm text-white disabled:opacity-50"
                style={{
                  background: "var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <MailPlus className="w-4 h-4" />
                {mutation.isPending ? "提交中…" : "提交推荐"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InviteDialog({ onClose }: { onClose: () => void }) {
  const invalidate = useInvalidate();
  const [providerId, setProviderId] = useState<number | null>(null);
  const [serviceTypes, setServiceTypes] = useState<string[]>([]);
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { query: availableQuery } = useCustom<AvailableProvider[]>({
    url: "admin/providers/available",
    method: "get",
  });
  const available = availableQuery.data?.data ?? [];

  const { mutate: invite, mutation: inviteMutation } = useCustomMutation();

  const selected = useMemo(
    () => available.find((p) => p.id === providerId) ?? null,
    [available, providerId],
  );

  const submit = () => {
    setError(null);
    if (!providerId) {
      setError("请选择一家服务商");
      return;
    }
    if (serviceTypes.length === 0) {
      setError("至少选择一项服务类型");
      return;
    }
    invite(
      {
        url: "admin/providers/invite",
        method: "post",
        values: {
          provider_id: providerId,
          service_types: serviceTypes,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        },
      },
      {
        onSuccess: () => {
          invalidate({ resource: "admin/providers", invalidates: ["all"] });
          onClose();
        },
        onError: (err) => {
          const code =
            (err as { response?: { data?: { code?: string } } }).response?.data?.code;
          if (code === "ERR_DUPLICATE_CONTRACT") setError("已与该服务商存在有效合作");
          else if (code === "ERR_PROVIDER_NOT_AVAILABLE")
            setError("该服务商当前不可邀请");
          else setError("邀请失败，请稍后重试");
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="bg-white p-6 w-[480px] max-h-[80vh] overflow-auto"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">邀请服务商</h2>
          <button type="button" onClick={onClose} className="text-[var(--color-neutral-400)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              选择已审核服务商
            </label>
            {availableQuery.isLoading ? (
              <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
            ) : available.length === 0 ? (
              <p className="text-sm text-[var(--color-neutral-400)]">
                暂无可邀请的已审核服务商
              </p>
            ) : (
              <select
                value={providerId ?? ""}
                onChange={(e) => setProviderId(Number(e.target.value) || null)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                <option value="">请选择…</option>
                {available.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}（{PROVIDER_TYPE_LABEL[p.provider_type] ?? p.provider_type}）
                  </option>
                ))}
              </select>
            )}
            {selected?.description && (
              <p className="mt-2 text-xs text-[var(--color-neutral-500)]">
                {selected.description}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              服务类型（可多选）
            </label>
            <div className="flex flex-wrap gap-2">
              {["legal_letter", "litigation", "collection", "consulting"].map((t) => {
                const checked = serviceTypes.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() =>
                      setServiceTypes((prev) =>
                        checked ? prev.filter((x) => x !== t) : [...prev, t],
                      )
                    }
                    className="px-2.5 py-1 text-xs border"
                    style={{
                      borderRadius: "var(--radius-md)",
                      borderColor: checked
                        ? "var(--color-primary)"
                        : "var(--color-neutral-200)",
                      background: checked ? "var(--color-primary-light)" : "white",
                      color: checked ? "var(--color-primary)" : "var(--color-neutral-600)",
                    }}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              到期日期（可选）
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              取消
            </button>
            <button
              type="button"
              disabled={inviteMutation.isPending}
              onClick={submit}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <Plus className="w-4 h-4" />
              {inviteMutation.isPending ? "提交中…" : "建立合作"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
