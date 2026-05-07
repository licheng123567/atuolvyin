// 物业项目 — 新建页
import { useCreate, useGo, useList } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface UserItem {
  id: number;
  name: string;
  role: string;
}

interface ProviderItem {
  provider_id: number;
  provider_name: string;
  contract_status: string;
}

export function AdminProjectNewPage() {
  const go = useGo();
  const [name, setName] = useState("");
  const [projectType, setProjectType] = useState<"collection" | "vote">(
    "collection",
  );
  const [propertyPmId, setPropertyPmId] = useState<number | "">("");
  const [providerId, setProviderId] = useState<number | "">("");
  const [providerPmId, setProviderPmId] = useState<number | "">("");
  const [description, setDescription] = useState("");
  const [allowInternalAssist, setAllowInternalAssist] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取物业项目经理 + 服务商项目经理
  const { query: userQuery } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const usersRaw = userQuery.data?.data;
  const allUsers: UserItem[] =
    (usersRaw as unknown as PaginatedResponse<UserItem>)?.items ??
    (usersRaw as UserItem[] | undefined) ??
    [];
  const propertyPMs = allUsers.filter(
    (u) => u.role === "project_manager_property",
  );
  const providerPMs = allUsers.filter(
    (u) => u.role === "project_manager_provider",
  );

  // 服务商列表（已签约的）
  const { query: providerQuery } = useList<ProviderItem>({
    resource: "admin/providers",
    pagination: { currentPage: 1, pageSize: 50 },
  });
  const providersRaw = providerQuery.data?.data;
  const providers: ProviderItem[] =
    (providersRaw as unknown as PaginatedResponse<ProviderItem>)?.items ??
    (providersRaw as ProviderItem[] | undefined) ??
    [];

  const { mutate: create, mutation } = useCreate();

  function submit() {
    setError(null);
    if (!name.trim()) {
      setError("请输入项目名称");
      return;
    }
    if (propertyPmId === "") {
      setError("请选择项目负责人(物业)");
      return;
    }
    create(
      {
        resource: "admin/projects",
        values: {
          name: name.trim(),
          project_type: projectType,
          property_pm_user_id: propertyPmId,
          provider_id: providerId === "" ? null : providerId,
          provider_pm_user_id: providerPmId === "" ? null : providerPmId,
          description: description.trim() || null,
          allow_internal_assist: allowInternalAssist,
        },
      },
      {
        onSuccess: () => go({ to: "/admin/projects" }),
        onError: (e) => {
          const detail =
            (e as { response?: { data?: { detail?: { message?: string } } } })
              ?.response?.data?.detail?.message ?? "创建失败";
          setError(detail);
        },
      },
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <button
            type="button"
            className="ds-btn ds-btn-ghost"
            onClick={() => go({ to: "/admin/projects" })}
            style={{ marginBottom: 8 }}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            返回
          </button>
          <h1 className="page-title">新建项目</h1>
        </div>
      </div>

      <div className="ds-card">
        <div className="card-body" style={{ maxWidth: 640 }}>
          <div className="form-group">
            <label className="form-label">
              项目名称<span className="req">*</span>
            </label>
            <input
              className="form-control"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例：金桂园 2026 年欠费催收"
            />
          </div>

          <div className="two-col">
            <div className="form-group">
              <label className="form-label">
                项目类型<span className="req">*</span>
              </label>
              <select
                className="form-control"
                value={projectType}
                onChange={(e) =>
                  setProjectType(e.target.value as "collection" | "vote")
                }
              >
                <option value="collection">物业费催收</option>
                <option value="vote">业委会投票邀请</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">
                项目负责人(物业)<span className="req">*</span>
              </label>
              <select
                className="form-control"
                value={propertyPmId}
                onChange={(e) =>
                  setPropertyPmId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
              >
                <option value="">— 请选择 —</option>
                {propertyPMs.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </select>
              {propertyPMs.length === 0 && (
                <div className="form-hint" style={{ color: "#d97706" }}>
                  ⚠ 还没有项目经理(物业) 角色用户，请先去「用户管理」创建
                </div>
              )}
            </div>
          </div>

          <div className="two-col">
            <div className="form-group">
              <label className="form-label">合作服务商（可选）</label>
              <select
                className="form-control"
                value={providerId}
                onChange={(e) =>
                  setProviderId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
              >
                <option value="">— 不指派（自营）—</option>
                {providers.map((p) => (
                  <option key={p.provider_id} value={p.provider_id}>
                    {p.provider_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">项目负责人(服务商)（可选）</label>
              <select
                className="form-control"
                value={providerPmId}
                onChange={(e) =>
                  setProviderPmId(
                    e.target.value === "" ? "" : Number(e.target.value),
                  )
                }
              >
                <option value="">— 暂不指派 —</option>
                {providerPMs.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">项目描述</label>
            <textarea
              className="form-control"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="可选：项目背景、目标、关键节点等"
              style={{ minHeight: 80 }}
            />
          </div>

          {providerId !== "" && (
            <div
              className="form-group"
              style={{
                background: "#f9fafb",
                padding: 12,
                borderRadius: 6,
                border: "1px solid #e5e7eb",
              }}
            >
              <label
                style={{ display: "flex", alignItems: "flex-start", gap: 8, cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  checked={allowInternalAssist}
                  onChange={(e) => setAllowInternalAssist(e.target.checked)}
                  style={{ marginTop: 2 }}
                />
                <div>
                  <div className="setting-label">允许物业内勤协助催收</div>
                  <div className="setting-hint">
                    勾选后，本项目下的公海案件物业内勤也能看到 / 接单（与服务商外勤共享公海，谁先认领谁负责）
                  </div>
                </div>
              </label>
            </div>
          )}

          {error && (
            <div
              style={{
                background: "var(--color-danger-light)",
                color: "var(--color-danger)",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
                marginBottom: 12,
              }}
            >
              {error}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button
              type="button"
              className="ds-btn ds-btn-secondary"
              onClick={() => go({ to: "/admin/projects" })}
            >
              取消
            </button>
            <button
              type="button"
              className="ds-btn ds-btn-primary"
              onClick={submit}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "创建中…" : "创建项目"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
