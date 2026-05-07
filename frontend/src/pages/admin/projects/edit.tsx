// 物业项目 — 编辑页（v1.4 S0）
import { useGo, useList, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
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

interface ProjectDetail {
  id: number;
  tenant_id: number;
  name: string;
  provider_id: number | null;
  property_pm_user_id: number | null;
  provider_pm_user_id: number | null;
  description: string | null;
  status: string;
  allow_internal_assist: boolean;
}

export function AdminProjectEditPage() {
  const go = useGo();
  const { id } = useParams<{ id: string }>();
  const projectId = id ? Number(id) : null;

  const [propertyPmId, setPropertyPmId] = useState<number | "">("");
  const [providerId, setProviderId] = useState<number | "">("");
  const [providerPmId, setProviderPmId] = useState<number | "">("");
  const [description, setDescription] = useState("");
  const [allowInternalAssist, setAllowInternalAssist] = useState(false);
  const [status, setStatus] = useState<"active" | "paused" | "closed">(
    "active",
  );
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // 拉项目详情
  const { query: projectQuery } = useOne<ProjectDetail>({
    resource: "admin/projects",
    id: projectId ?? "",
    queryOptions: { enabled: projectId !== null },
  });
  const project = projectQuery.data?.data;

  // 拉用户和服务商下拉
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

  const { query: providerQuery } = useList<ProviderItem>({
    resource: "admin/providers",
    pagination: { currentPage: 1, pageSize: 50 },
  });
  const providersRaw = providerQuery.data?.data;
  const providers: ProviderItem[] =
    (providersRaw as unknown as PaginatedResponse<ProviderItem>)?.items ??
    (providersRaw as ProviderItem[] | undefined) ??
    [];

  // 初始化表单
  useEffect(() => {
    if (project && !initialized) {
      setPropertyPmId(project.property_pm_user_id ?? "");
      setProviderId(project.provider_id ?? "");
      setProviderPmId(project.provider_pm_user_id ?? "");
      setDescription(project.description ?? "");
      setAllowInternalAssist(project.allow_internal_assist);
      setStatus((project.status as "active" | "paused" | "closed") ?? "active");
      setInitialized(true);
    }
  }, [project, initialized]);

  // provider_id 切到 null 时自动取消协助开关
  useEffect(() => {
    if (providerId === "" && allowInternalAssist) {
      setAllowInternalAssist(false);
    }
  }, [providerId, allowInternalAssist]);

  const { mutate: update, mutation } = useUpdate();

  function submit() {
    setError(null);
    if (propertyPmId === "") {
      setError("请选择项目负责人(物业)");
      return;
    }
    if (projectId === null) return;

    update(
      {
        resource: "admin/projects",
        id: projectId,
        values: {
          property_pm_user_id: propertyPmId,
          provider_id: providerId === "" ? null : providerId,
          provider_pm_user_id: providerPmId === "" ? null : providerPmId,
          description: description.trim() || null,
          allow_internal_assist: allowInternalAssist,
          status,
        },
      },
      {
        onSuccess: () => go({ to: "/admin/projects" }),
        onError: (e) => {
          const detail =
            (e as { response?: { data?: { detail?: { message?: string } } } })
              ?.response?.data?.detail?.message ?? "保存失败";
          setError(detail);
        },
      },
    );
  }

  if (projectQuery.isLoading || !project) {
    return (
      <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>
        加载中…
      </div>
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
          <h1 className="page-title">编辑项目 · {project.name}</h1>
        </div>
      </div>

      <div className="ds-card">
        <div className="card-body" style={{ maxWidth: 640 }}>
          <div className="form-group">
            <label className="form-label">项目名称</label>
            <input
              className="form-control"
              value={project.name}
              disabled
            />
            <div className="form-hint">名称创建后不可改</div>
          </div>

          <div className="two-col">
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
            </div>
            <div className="form-group">
              <label className="form-label">状态</label>
              <select
                className="form-control"
                value={status}
                onChange={(e) =>
                  setStatus(e.target.value as "active" | "paused" | "closed")
                }
              >
                <option value="active">进行中</option>
                <option value="paused">暂停</option>
                <option value="closed">已结束</option>
              </select>
            </div>
          </div>

          <div className="two-col">
            <div className="form-group">
              <label className="form-label">合作服务商</label>
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
              <label className="form-label">项目负责人(服务商)</label>
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
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  cursor: "pointer",
                }}
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
                    勾选后，本项目下的公海案件物业内勤也能看到 / 接单（与服务商外勤共享公海）
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
              {mutation.isPending ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
