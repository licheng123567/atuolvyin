// 物业项目 — 编辑页（v1.4 S0 / v1.6.2 加合同上传 + 滞纳金减免）
import { useApiUrl, useGo, useList, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";
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
  provider_name: string | null;
  property_pm_user_id: number | null;
  provider_pm_user_id: number | null;
  provider_pm_name: string | null;
  description: string | null;
  status: string;
  plan_start: string | null;
  plan_end: string | null;
  // v1.5.6
  coordinator_user_id: number | null;
  coordinator_name: string | null;
  legal_user_id: number | null;
  legal_name: string | null;
  // v1.6 收费 + 合同
  charge_rate_text: string | null;
  charge_period: string | null;
  contract_type: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  contract_attachment_key: string | null;
  contract_attachment_filename: string | null;
  charge_notes: string | null;
  // v1.6.1 — 项目级「本金打折」覆盖
  discount_auto_approve_threshold_pct: number | null;
  discount_supervisor_max_pct: number | null;
  discount_disabled: boolean | null;
  // v1.6.2 — 项目级「滞纳金减免」覆盖（独立策略）
  late_fee_waive_auto_approve_threshold_pct: number | null;
  late_fee_waive_supervisor_max_pct: number | null;
  late_fee_waive_disabled: boolean | null;
}

function toDateInput(iso: string | null): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function fromDateInput(d: string): string | null {
  if (!d) return null;
  // 转 ISO 时间（当天 23:59:59 UTC）以保持服务期一直到当天结束
  return new Date(`${d}T23:59:59Z`).toISOString();
}

export function AdminProjectEditPage() {
  const go = useGo();
  const { id } = useParams<{ id: string }>();
  const projectId = id ? Number(id) : null;

  const [propertyPmId, setPropertyPmId] = useState<number | "">("");
  const [providerId, setProviderId] = useState<number | "">("");
  const [coordinatorId, setCoordinatorId] = useState<number | "">("");
  const [legalId, setLegalId] = useState<number | "">("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<"active" | "paused" | "closed">(
    "active",
  );
  const [planStart, setPlanStart] = useState("");
  const [planEnd, setPlanEnd] = useState("");
  // v1.6 收费 + 合同
  const [chargeRateText, setChargeRateText] = useState("");
  const [chargePeriod, setChargePeriod] = useState<"monthly" | "quarterly" | "semiannual" | "annual" | "">("");
  const [contractType, setContractType] = useState<"preliminary_service" | "elected" | "re_elected" | "interim_management" | "">("");
  const [contractStart, setContractStart] = useState("");
  const [contractEnd, setContractEnd] = useState("");
  const [contractAttachment, setContractAttachment] = useState("");
  const [contractFilename, setContractFilename] = useState("");
  const [uploadingContract, setUploadingContract] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const apiUrl = useApiUrl();
  const [chargeNotes, setChargeNotes] = useState("");
  // v1.6.1 — 项目级「本金打折」覆盖
  const [discountAutoThreshold, setDiscountAutoThreshold] = useState("");
  const [discountSupervisorMax, setDiscountSupervisorMax] = useState("");
  const [discountDisabled, setDiscountDisabled] = useState<"" | "true" | "false">("");
  // v1.6.2 — 项目级「滞纳金减免」覆盖
  const [lateFeeAutoThreshold, setLateFeeAutoThreshold] = useState("");
  const [lateFeeSupervisorMax, setLateFeeSupervisorMax] = useState("");
  const [lateFeeDisabled, setLateFeeDisabled] = useState<"" | "true" | "false">("");
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [confirmRelease, setConfirmRelease] = useState(false);

  async function uploadContract(file: File) {
    setError(null);
    setUploadingContract(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const token = localStorage.getItem("autoluyin_token");
      const resp = await fetch(`${apiUrl}/admin/projects/contract/upload`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err?.detail?.message ?? `上传失败 (HTTP ${resp.status})`);
      }
      const data = (await resp.json()) as { object_key: string; filename: string };
      setContractAttachment(data.object_key);
      setContractFilename(data.filename);
    } catch (e) {
      setError((e as Error).message ?? "上传失败");
    } finally {
      setUploadingContract(false);
    }
  }

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
  // project_manager on property-side (scope=tenant:{id}); backend /admin/users filters by tenant
  const propertyPMs = allUsers.filter(
    (u) => u.role === "project_manager",
  );
  const coordinators = allUsers.filter(
    (u) => u.role === "coordinator" || u.role === "workorder",
  );
  const legals = allUsers.filter((u) => u.role === "legal");

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
      setCoordinatorId(project.coordinator_user_id ?? "");
      setLegalId(project.legal_user_id ?? "");
      setDescription(project.description ?? "");
      setStatus((project.status as "active" | "paused" | "closed") ?? "active");
      setPlanStart(toDateInput(project.plan_start));
      setPlanEnd(toDateInput(project.plan_end));
      // v1.6 收费 + 合同
      setChargeRateText(project.charge_rate_text ?? "");
      setChargePeriod((project.charge_period ?? "") as typeof chargePeriod);
      setContractType((project.contract_type ?? "") as typeof contractType);
      setContractStart(project.contract_start_date ? project.contract_start_date.slice(0, 10) : "");
      setContractEnd(project.contract_end_date ? project.contract_end_date.slice(0, 10) : "");
      setContractAttachment(project.contract_attachment_key ?? "");
      setContractFilename(project.contract_attachment_filename ?? "");
      setChargeNotes(project.charge_notes ?? "");
      // v1.6.1 本金打折
      setDiscountAutoThreshold(
        project.discount_auto_approve_threshold_pct == null
          ? ""
          : String(project.discount_auto_approve_threshold_pct),
      );
      setDiscountSupervisorMax(
        project.discount_supervisor_max_pct == null
          ? ""
          : String(project.discount_supervisor_max_pct),
      );
      setDiscountDisabled(
        project.discount_disabled == null
          ? ""
          : project.discount_disabled
            ? "true"
            : "false",
      );
      // v1.6.2 滞纳金减免
      setLateFeeAutoThreshold(
        project.late_fee_waive_auto_approve_threshold_pct == null
          ? ""
          : String(project.late_fee_waive_auto_approve_threshold_pct),
      );
      setLateFeeSupervisorMax(
        project.late_fee_waive_supervisor_max_pct == null
          ? ""
          : String(project.late_fee_waive_supervisor_max_pct),
      );
      setLateFeeDisabled(
        project.late_fee_waive_disabled == null
          ? ""
          : project.late_fee_waive_disabled
            ? "true"
            : "false",
      );
      setInitialized(true);
    }
  }, [project, initialized]);

  const { mutate: update, mutation } = useUpdate();

  function submit() {
    setError(null);
    if (propertyPmId === "") {
      setError("请选择项目负责人(物业)");
      return;
    }
    if (projectId === null) return;

    // v1.5.6 — 任意项目都必须指定协调员 + 法务对接人
    if (coordinatorId === "") {
      setError("请指定 1 名物业协调员");
      return;
    }
    if (legalId === "") {
      setError("请指定 1 名法务对接人");
      return;
    }

    update(
      {
        resource: "admin/projects",
        id: projectId,
        values: {
          property_pm_user_id: propertyPmId,
          provider_id: providerId === "" ? null : providerId,
          coordinator_user_id: coordinatorId,
          legal_user_id: legalId,
          description: description.trim() || null,
          status,
          plan_start: fromDateInput(planStart),
          plan_end: fromDateInput(planEnd),
          // v1.6 收费 + 合同
          charge_rate_text: chargeRateText.trim() || null,
          charge_period: chargePeriod || null,
          contract_type: contractType || null,
          contract_start_date: contractStart || null,
          contract_end_date: contractEnd || null,
          contract_attachment_key: contractAttachment.trim() || null,
          contract_attachment_filename: contractFilename.trim() || null,
          charge_notes: chargeNotes.trim() || null,
          // v1.6.1 — 项目级「本金打折」覆盖（留空 = NULL = 继承租户默认）
          discount_auto_approve_threshold_pct:
            discountAutoThreshold === "" ? null : Number(discountAutoThreshold),
          discount_supervisor_max_pct:
            discountSupervisorMax === "" ? null : Number(discountSupervisorMax),
          discount_disabled:
            discountDisabled === "" ? null : discountDisabled === "true",
          // v1.6.2 — 项目级「滞纳金减免」覆盖
          late_fee_waive_auto_approve_threshold_pct:
            lateFeeAutoThreshold === "" ? null : Number(lateFeeAutoThreshold),
          late_fee_waive_supervisor_max_pct:
            lateFeeSupervisorMax === "" ? null : Number(lateFeeSupervisorMax),
          late_fee_waive_disabled:
            lateFeeDisabled === "" ? null : lateFeeDisabled === "true",
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
              <SearchableSelect
                value={propertyPmId}
                placeholder="— 请选择 —"
                onChange={(v) => setPropertyPmId(v === "" ? "" : Number(v))}
                options={propertyPMs.map((u) => ({ value: u.id, label: u.name }))}
              />
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

          <div className="form-group">
            <label className="form-label">合作服务商</label>
            <SearchableSelect
              value={providerId}
              placeholder="— 不指派（自营）—"
              onChange={(v) => setProviderId(v === "" ? "" : Number(v))}
              options={providers.map((p) => ({
                value: p.provider_id,
                label: p.provider_name,
                subtitle: p.contract_status,
              }))}
              disabled={confirmRelease}
            />
            <div className="form-hint" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span>
                {providerId !== ""
                  ? "外包模式 — 服务商 PM 由对方在自家工作台指派"
                  : "留空 = 自营模式（物业内部催收员负责）"}
              </span>
              {/* v1.5.6 — 解除外包：仅当当前已绑定服务商时显示 */}
              {project?.provider_id && providerId !== "" && !confirmRelease && (
                <button
                  type="button"
                  className="ds-btn ds-btn-ghost ds-btn-sm"
                  onClick={() => setConfirmRelease(true)}
                  style={{ padding: "2px 8px", fontSize: 11, color: "#dc2626" }}
                >
                  解除外包 →
                </button>
              )}
            </div>
            {confirmRelease && (
              <div
                style={{
                  marginTop: 8,
                  padding: 12,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: 6,
                  fontSize: 13,
                  color: "#991b1b",
                }}
              >
                <div style={{ marginBottom: 8, fontWeight: 600 }}>⚠ 确认解除外包</div>
                <ul style={{ marginBottom: 8, paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                  <li>服务商及其外勤将立即失去本项目案件可见性</li>
                  <li>本项目案件保留，但需重新指派给物业内部催收员</li>
                  <li>历史通话/录音/工单不会丢失</li>
                  <li>合同（如有效）不会自动解约，仅断开本项目；其他项目不受影响</li>
                </ul>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    type="button"
                    className="ds-btn ds-btn-sm"
                    style={{ background: "#dc2626", color: "white", padding: "4px 10px", fontSize: 12 }}
                    onClick={() => {
                      setProviderId("");
                      setConfirmRelease(false);
                    }}
                  >
                    确认解除（保存后生效）
                  </button>
                  <button
                    type="button"
                    className="ds-btn ds-btn-ghost ds-btn-sm"
                    style={{ padding: "4px 10px", fontSize: 12 }}
                    onClick={() => setConfirmRelease(false)}
                  >
                    取消
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* v1.5.6 — 协调员 + 法务对接人（任意项目都必填）*/}
          <div className="two-col">
            <div className="form-group">
              <label className="form-label">
                物业协调员<span className="req">*</span>
              </label>
              <SearchableSelect
                value={coordinatorId}
                placeholder="— 请选择 —"
                onChange={(v) => setCoordinatorId(v === "" ? "" : Number(v))}
                options={coordinators.map((u) => ({ value: u.id, label: u.name }))}
              />
              <div className="form-hint">
                {coordinators.length === 0 ? (
                  <span style={{ color: "#d97706" }}>⚠ 没有协调员，请先创建</span>
                ) : (
                  "接此项目跨职能工单"
                )}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">
                法务对接人<span className="req">*</span>
              </label>
              <SearchableSelect
                value={legalId}
                placeholder="— 请选择 —"
                onChange={(v) => setLegalId(v === "" ? "" : Number(v))}
                options={legals.map((u) => ({ value: u.id, label: u.name }))}
              />
              <div className="form-hint">
                {legals.length === 0 ? (
                  <span style={{ color: "#d97706" }}>⚠ 没有法务对接人，请先创建</span>
                ) : (
                  "处理此项目转法务流程"
                )}
              </div>
            </div>
          </div>

          <div className="two-col">
            <div className="form-group">
              <label className="form-label">服务期开始</label>
              <input
                className="form-control"
                type="date"
                value={planStart}
                onChange={(e) => setPlanStart(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">服务期结束</label>
              <input
                className="form-control"
                type="date"
                value={planEnd}
                onChange={(e) => setPlanEnd(e.target.value)}
              />
              <div className="form-hint" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span>到期后服务商将自动失去访问权（保留 30 天只读历史）</span>
                <button
                  type="button"
                  className="ds-btn ds-btn-ghost ds-btn-sm"
                  onClick={() => {
                    const base = planEnd ? new Date(planEnd) : new Date();
                    base.setDate(base.getDate() + 90);
                    setPlanEnd(base.toISOString().slice(0, 10));
                  }}
                  style={{ padding: "2px 8px", fontSize: 11 }}
                >
                  延长 90 天
                </button>
              </div>
            </div>
          </div>

          {/* v1.6 收费 + 合同 */}
          <div
            className="form-group"
            style={{
              background: "#f9fafb",
              padding: 12,
              borderRadius: 6,
              border: "1px solid #e5e7eb",
              marginBottom: 16,
            }}
          >
            <div className="setting-label" style={{ marginBottom: 4 }}>💰 收费标准 + 合同</div>

            <div className="form-group">
              <label className="form-label">收费标准（自由文本，支持多行）</label>
              <textarea
                className="form-control"
                value={chargeRateText}
                onChange={(e) => setChargeRateText(e.target.value)}
                placeholder={"例：\n住宅 1.5 元/㎡/月\n商铺 3.0 元/㎡/月"}
                style={{ minHeight: 80, fontFamily: "inherit" }}
              />
            </div>

            <div className="form-group">
              <label className="form-label">收费周期</label>
              <select
                className="form-control"
                value={chargePeriod}
                onChange={(e) => setChargePeriod(e.target.value as typeof chargePeriod)}
              >
                <option value="">— 不限 —</option>
                <option value="monthly">按月</option>
                <option value="quarterly">按季</option>
                <option value="semiannual">按半年</option>
                <option value="annual">按年</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">合同类型</label>
              <select
                className="form-control"
                value={contractType}
                onChange={(e) => setContractType(e.target.value as typeof contractType)}
              >
                <option value="">— 请选择 —</option>
                <option value="preliminary_service">前期物业服务合同</option>
                <option value="elected">选聘合同</option>
                <option value="re_elected">续聘合同</option>
                <option value="interim_management">临时管理合同</option>
              </select>
            </div>

            <div className="two-col">
              <div className="form-group">
                <label className="form-label">合同起始日</label>
                <input className="form-control" type="date" value={contractStart} onChange={(e) => setContractStart(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">合同终止日</label>
                <input className="form-control" type="date" value={contractEnd} onChange={(e) => setContractEnd(e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">合同附件</label>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,image/*,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void uploadContract(f);
                  e.target.value = "";
                }}
              />
              {!contractAttachment ? (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingContract}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Upload className="w-4 h-4" />
                  {uploadingContract ? "上传中…" : "选择文件上传"}
                </button>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 6, fontSize: 13 }}>
                  <span style={{ color: "#065f46", flex: 1 }}>✓ {contractFilename || "已上传"}</span>
                  <button
                    type="button"
                    onClick={() => { setContractAttachment(""); setContractFilename(""); }}
                    style={{ background: "none", border: "none", color: "#065f46", cursor: "pointer", padding: 4 }}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              <div className="form-hint">支持 PDF / Word / 图片，单个文件 ≤ 20MB</div>
            </div>

            <div className="form-group">
              <label className="form-label">收费备注</label>
              <textarea
                className="form-control"
                value={chargeNotes}
                onChange={(e) => setChargeNotes(e.target.value)}
                style={{ minHeight: 60 }}
              />
            </div>
          </div>

          {/* v1.6.1 / 1.6.2 — 项目级减免策略覆盖（拆分为本金打折 + 滞纳金减免） */}
          <div
            className="form-group"
            style={{
              background: "#fef9f3",
              padding: 12,
              borderRadius: 6,
              border: "1px solid #fde7c7",
              marginBottom: 16,
            }}
          >
            <div className="setting-label" style={{ marginBottom: 4 }}>
              🏷 减免审批策略（项目级覆盖）
            </div>
            <div className="setting-hint" style={{ marginBottom: 12 }}>
              本金打折 与 滞纳金减免 可分别设置；<b>留空</b>则继承租户默认。
            </div>

            {/* 本金打折 */}
            <div style={{ marginBottom: 14, padding: 10, background: "white", borderRadius: 6, border: "1px solid #e5e7eb" }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#7c2d12" }}>💰 本金打折策略</div>
              <div className="two-col">
                <div className="form-group">
                  <label className="form-label">自动批准阈值 (%)</label>
                  <input className="form-control" type="number" min="0" max="100" value={discountAutoThreshold} onChange={(e) => setDiscountAutoThreshold(e.target.value)} placeholder="租户默认 10" />
                </div>
                <div className="form-group">
                  <label className="form-label">督导可批上限 (%)</label>
                  <input className="form-control" type="number" min="0" max="100" value={discountSupervisorMax} onChange={(e) => setDiscountSupervisorMax(e.target.value)} placeholder="租户默认 30" />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">本项目是否禁用本金打折</label>
                <select className="form-control" value={discountDisabled} onChange={(e) => setDiscountDisabled(e.target.value as typeof discountDisabled)}>
                  <option value="">— 继承租户默认 —</option>
                  <option value="false">允许本金打折</option>
                  <option value="true">禁用本金打折</option>
                </select>
              </div>
            </div>

            {/* 滞纳金减免 */}
            <div style={{ padding: 10, background: "white", borderRadius: 6, border: "1px solid #e5e7eb" }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#0e7490" }}>⏰ 滞纳金减免策略</div>
              <div className="form-hint" style={{ marginBottom: 8 }}>多数物业愿意减免滞纳金以换取本金回收</div>
              <div className="two-col">
                <div className="form-group">
                  <label className="form-label">自动批准阈值 (%)</label>
                  <input className="form-control" type="number" min="0" max="100" value={lateFeeAutoThreshold} onChange={(e) => setLateFeeAutoThreshold(e.target.value)} placeholder="租户默认 50" />
                </div>
                <div className="form-group">
                  <label className="form-label">督导可批上限 (%)</label>
                  <input className="form-control" type="number" min="0" max="100" value={lateFeeSupervisorMax} onChange={(e) => setLateFeeSupervisorMax(e.target.value)} placeholder="租户默认 100" />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">本项目是否禁用滞纳金减免</label>
                <select className="form-control" value={lateFeeDisabled} onChange={(e) => setLateFeeDisabled(e.target.value as typeof lateFeeDisabled)}>
                  <option value="">— 继承租户默认 —</option>
                  <option value="false">允许滞纳金减免</option>
                  <option value="true">禁用滞纳金减免</option>
                </select>
              </div>
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
