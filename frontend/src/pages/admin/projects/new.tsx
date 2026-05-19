// 物业项目 — 新建页（v1.5.6 重构：自办 / 外包 二选一）
import { useApiUrl, useCreate, useGo, useList } from "@refinedev/core";
import { ArrowLeft, Info, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";
import { SearchableMultiSelect } from "../../../components/ui/SearchableMultiSelect";
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

type ProjectMode = "self" | "outsourced";

export function AdminProjectNewPage() {
  const go = useGo();
  const [name, setName] = useState("");
  const [mode, setMode] = useState<ProjectMode>("self");
  const [propertyPmId, setPropertyPmId] = useState<number | "">("");
  const [providerId, setProviderId] = useState<number | "">("");
  const [coordinatorId, setCoordinatorId] = useState<number | "">("");
  const [legalId, setLegalId] = useState<number | "">("");
  const [description, setDescription] = useState("");
  const [supervisorIds, setSupervisorIds] = useState<number[]>([]);
  const [agentIds, setAgentIds] = useState<number[]>([]);
  const [planStart, setPlanStart] = useState("");
  const [planEnd, setPlanEnd] = useState("");
  // v1.6 — 收费 + 合同
  // v1.6.2 — 收费标准改为自由文本（多行；不同物业类型可以一并描述）
  const [chargeRateText, setChargeRateText] = useState("");
  const [chargePeriod, setChargePeriod] = useState<"monthly" | "quarterly" | "semiannual" | "annual" | "">("monthly");
  const [contractType, setContractType] = useState<"preliminary_service" | "elected" | "re_elected" | "interim_management" | "">("");
  const [contractStart, setContractStart] = useState("");
  const [contractEnd, setContractEnd] = useState("");
  const [contractAttachment, setContractAttachment] = useState("");
  const [contractFilename, setContractFilename] = useState("");
  const [uploadingContract, setUploadingContract] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const apiUrl = useApiUrl();
  const [chargeNotes, setChargeNotes] = useState("");
  // v1.6.1 — 项目级「本金打折」阈值覆盖（留空表示继承租户默认）
  const [discountAutoThreshold, setDiscountAutoThreshold] = useState("");
  const [discountSupervisorMax, setDiscountSupervisorMax] = useState("");
  const [discountDisabled, setDiscountDisabled] = useState<"" | "true" | "false">("");
  // v1.6.2 — 项目级「滞纳金减免」阈值覆盖（独立策略）
  const [lateFeeAutoThreshold, setLateFeeAutoThreshold] = useState("");
  const [lateFeeSupervisorMax, setLateFeeSupervisorMax] = useState("");
  const [lateFeeDisabled, setLateFeeDisabled] = useState<"" | "true" | "false">("");
  // §9.2-D1 — 内勤催收员佣金率（百分比录入，提交时除以 100 转为 0-1 小数）
  const [internalCommRate, setInternalCommRate] = useState("");
  // §9.2-D2 — 外包项目的服务商佣金率初始值（百分比录入，提交时除以 100）
  const [providerCommRate, setProviderCommRate] = useState("");
  // v2.2 — 项目收款信息
  const [payeeName, setPayeeName] = useState("");
  const [payeeAccount, setPayeeAccount] = useState("");
  const [paymentInstructions, setPaymentInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);

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

  function fromDateInput(d: string): string | null {
    if (!d) return null;
    return new Date(`${d}T23:59:59Z`).toISOString();
  }

  // 拉物业内部用户（用于各角色下拉）
  const { query: userQuery } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const usersRaw = userQuery.data?.data;
  const allUsers: UserItem[] =
    (usersRaw as unknown as PaginatedResponse<UserItem>)?.items ??
    (usersRaw as UserItem[] | undefined) ??
    [];
  // project_manager on property-side (scope=tenant:{id}) is the "property PM"
  // The backend /admin/users endpoint filters by tenant, so all project_managers here are property-side
  const propertyPMs = allUsers.filter((u) => u.role === "project_manager");
  const supervisors = allUsers.filter((u) => u.role === "supervisor");
  const agents = allUsers.filter((u) => u.role === "agent");
  const coordinators = allUsers.filter((u) => u.role === "coordinator" || u.role === "workorder");
  const legals = allUsers.filter((u) => u.role === "legal");

  // 服务商列表
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
      setError("请选择物业项目负责人");
      return;
    }
    if (coordinatorId === "") {
      setError("请指定 1 名物业协调员（接此项目的工单）");
      return;
    }
    if (legalId === "") {
      setError("请指定 1 名法务对接人（处理此项目的法务转化）");
      return;
    }
    if (mode === "outsourced" && providerId === "") {
      setError("外包项目必须选择合作服务商");
      return;
    }

    const values: Record<string, unknown> = {
      name: name.trim(),
      property_pm_user_id: propertyPmId,
      description: description.trim() || null,
      plan_start: fromDateInput(planStart),
      plan_end: fromDateInput(planEnd),
      coordinator_user_id: coordinatorId,
      legal_user_id: legalId,
      // v1.6 — 收费 + 合同（可选）
      // v1.6.2 — 收费标准从 numeric 改为自由文本
      charge_rate_text: chargeRateText.trim() || null,
      charge_period: chargePeriod || null,
      contract_type: contractType || null,
      contract_start_date: contractStart || null,
      contract_end_date: contractEnd || null,
      contract_attachment_key: contractAttachment.trim() || null,
      contract_attachment_filename: contractFilename.trim() || null,
      charge_notes: chargeNotes.trim() || null,
      // v1.6.1 — 本金打折覆盖；留空 = NULL = 继承租户默认
      discount_auto_approve_threshold_pct: discountAutoThreshold === "" ? null : Number(discountAutoThreshold),
      discount_supervisor_max_pct: discountSupervisorMax === "" ? null : Number(discountSupervisorMax),
      discount_disabled: discountDisabled === "" ? null : discountDisabled === "true",
      // v1.6.2 — 滞纳金减免覆盖（独立策略）
      late_fee_waive_auto_approve_threshold_pct: lateFeeAutoThreshold === "" ? null : Number(lateFeeAutoThreshold),
      late_fee_waive_supervisor_max_pct: lateFeeSupervisorMax === "" ? null : Number(lateFeeSupervisorMax),
      late_fee_waive_disabled: lateFeeDisabled === "" ? null : lateFeeDisabled === "true",
      // v2.2 — 项目收款信息
      payee_name: payeeName.trim() || null,
      payee_account: payeeAccount.trim() || null,
      payment_instructions: paymentInstructions.trim() || null,
    };
    if (mode === "outsourced") {
      values.provider_id = providerId;
      // §9.2-D2 — 服务商佣金率初始值（÷100 转为 0-1 小数）
      values.provider_agent_commission_rate =
        providerCommRate === "" ? null : Number(providerCommRate) / 100;
    } else {
      values.provider_id = null;
      values.supervisor_user_ids = supervisorIds;
      values.agent_user_ids = agentIds;
      // §9.2-D1 — 内勤催收员佣金率（÷100 转为 0-1 小数）
      values.internal_agent_commission_rate =
        internalCommRate === "" ? null : Number(internalCommRate) / 100;
    }

    create(
      { resource: "admin/projects", values },
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

          <div className="form-group">
            <label className="form-label">
              物业项目负责人<span className="req">*</span>
            </label>
            <SearchableSelect
              value={propertyPmId}
              placeholder="— 请选择 —"
              onChange={(v) => setPropertyPmId(v === "" ? "" : Number(v))}
              options={propertyPMs.map((u) => ({ value: u.id, label: u.name }))}
            />
            {propertyPMs.length === 0 && (
              <div className="form-hint" style={{ color: "#d97706" }}>
                ⚠ 还没有项目经理(物业) 角色用户，请先去「用户管理」创建
              </div>
            )}
          </div>

          <div className="two-col">
            <div className="form-group">
              <label className="form-label">服务期开始（可选）</label>
              <input
                className="form-control"
                type="date"
                value={planStart}
                onChange={(e) => setPlanStart(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">服务期结束（可选）</label>
              <input
                className="form-control"
                type="date"
                value={planEnd}
                onChange={(e) => setPlanEnd(e.target.value)}
              />
              <div className="form-hint">
                {mode === "outsourced"
                  ? "服务商按本期合作；到期自动失去访问权（保留 30 天只读）"
                  : "可选；留空表示长期"}
              </div>
            </div>
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
                  <span style={{ color: "#d97706" }}>⚠ 没有协调员角色用户，请先到「用户管理」创建</span>
                ) : (
                  "接此项目跨职能工单（电梯/绿化/客服等）"
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
                  <span style={{ color: "#d97706" }}>⚠ 没有法务对接人，请先到「用户管理」创建</span>
                ) : (
                  "处理此项目转法务流程 + 跟律所沟通"
                )}
              </div>
            </div>
          </div>

          {/* 项目模式选择 */}
          <div className="form-group">
            <label className="form-label">
              催收方式<span className="req">*</span>
            </label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <ModeRadio
                checked={mode === "self"}
                label="物业自办"
                desc="由物业内部催收员负责"
                onClick={() => setMode("self")}
              />
              <ModeRadio
                checked={mode === "outsourced"}
                label="外包给服务商"
                desc="服务商外勤负责，物业协调员接对接工单"
                onClick={() => setMode("outsourced")}
              />
            </div>
          </div>

          {/* 自办：督导 + 催收团队 */}
          {mode === "self" && (
            <div
              className="form-group"
              style={{
                background: "#f9fafb",
                padding: 12,
                borderRadius: 6,
                border: "1px solid #e5e7eb",
              }}
            >
              <div className="setting-label" style={{ marginBottom: 8 }}>
                项目团队（自办）
              </div>
              <div className="setting-hint" style={{ marginBottom: 12 }}>
                指定督导组和默认催收员后，导入案件时按团队 round-robin 自动分配；督导只看自己加入项目下的案件。
              </div>

              <div style={{ marginBottom: 10 }}>
                <label className="form-label">督导组（可多选）</label>
                <SearchableMultiSelect
                  value={supervisorIds}
                  onChange={(v) => setSupervisorIds(v.map(Number))}
                  options={supervisors.map((u) => ({ value: u.id, label: u.name }))}
                  placeholder="搜索并选择督导"
                />
                {supervisors.length === 0 && (
                  <div className="form-hint" style={{ color: "#d97706" }}>
                    ⚠ 还没有督导角色用户，请先到「用户管理」创建
                  </div>
                )}
              </div>

              <div>
                <label className="form-label">默认催收团队（可多选）</label>
                <SearchableMultiSelect
                  value={agentIds}
                  onChange={(v) => setAgentIds(v.map(Number))}
                  options={agents.map((u) => ({ value: u.id, label: u.name }))}
                  placeholder="搜索并选择催收员"
                />
                {agents.length === 0 && (
                  <div className="form-hint" style={{ color: "#d97706" }}>
                    ⚠ 还没有内部催收员，请先到「用户管理」创建
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 外包：服务商 + 协调员 */}
          {mode === "outsourced" && (
            <div
              className="form-group"
              style={{
                background: "#f9fafb",
                padding: 12,
                borderRadius: 6,
                border: "1px solid #e5e7eb",
              }}
            >
              <div className="setting-label" style={{ marginBottom: 12 }}>
                外包配置
              </div>

              <div style={{ marginBottom: 10 }}>
                <label className="form-label">
                  合作服务商<span className="req">*</span>
                </label>
                <SearchableSelect
                  value={providerId}
                  placeholder="— 请选择 —"
                  onChange={(v) => setProviderId(v === "" ? "" : Number(v))}
                  options={providers.map((p) => ({
                    value: p.provider_id,
                    label: p.provider_name,
                    subtitle: p.contract_status,
                  }))}
                />
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 8,
                  padding: "8px 10px",
                  background: "#eff6ff",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#1e40af",
                  alignItems: "flex-start",
                }}
              >
                <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  服务商项目经理（PM）和外勤团队由服务商管理员在其工作台「我的项目」自行指派，物业 admin 不需在此选择。
                </span>
              </div>
            </div>
          )}

          {/* v1.6 — 收费 + 合同 */}
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
            <div className="setting-label" style={{ marginBottom: 4 }}>
              💰 收费标准 + 合同（建议填写）
            </div>
            <div className="setting-hint" style={{ marginBottom: 12 }}>
              用于按月推算欠费明细 + 法务转化时律师函引用合同条款
            </div>

            <div className="form-group">
              <label className="form-label">收费标准（自由文本，支持多行）</label>
              <textarea
                className="form-control"
                value={chargeRateText}
                onChange={(e) => setChargeRateText(e.target.value)}
                placeholder={"例：\n住宅 1.5 元/㎡/月\n商铺 3.0 元/㎡/月\n车位 80 元/位/月"}
                style={{ minHeight: 80, fontFamily: "inherit" }}
              />
              <div className="form-hint">不同物业类型 / 区域不同费率，可分行列出</div>
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
                <option value="preliminary_service">前期物业服务合同（开发商签）</option>
                <option value="elected">选聘合同（业委会首次聘任）</option>
                <option value="re_elected">续聘合同（任期届满续约）</option>
                <option value="interim_management">临时管理合同（业委会未成立）</option>
              </select>
            </div>

            <div className="two-col">
              <div className="form-group">
                <label className="form-label">合同起始日</label>
                <input
                  className="form-control"
                  type="date"
                  value={contractStart}
                  onChange={(e) => setContractStart(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">合同终止日</label>
                <input
                  className="form-control"
                  type="date"
                  value={contractEnd}
                  onChange={(e) => setContractEnd(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">合同附件（PDF / Word / 图片）</label>
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
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 12px",
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  <span style={{ color: "#065f46", flex: 1 }}>
                    ✓ {contractFilename || "已上传"}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setContractAttachment("");
                      setContractFilename("");
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#065f46",
                      cursor: "pointer",
                      padding: 4,
                    }}
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
                placeholder="例：商铺 3.0 元/㎡/月，住宅 1.5 元/㎡/月；逾期按日加收 0.5‰ 滞纳金"
                style={{ minHeight: 60 }}
              />
            </div>
          </div>

          {/* v2.2 — 项目收款信息 */}
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
            <div className="setting-label" style={{ marginBottom: 4 }}>
              🏦 收款信息（业主缴费链接展示）
            </div>
            <div className="setting-hint" style={{ marginBottom: 12 }}>
              业主扫描缴费二维码后看到的收款账户与缴费说明，按项目分别配置。
            </div>
            <div className="form-group">
              <label className="form-label">收款户名</label>
              <input
                className="form-control"
                value={payeeName}
                onChange={(e) => setPayeeName(e.target.value)}
                placeholder="例：金桂物业管理有限公司"
              />
            </div>
            <div className="form-group">
              <label className="form-label">收款账户</label>
              <input
                className="form-control"
                value={payeeAccount}
                onChange={(e) => setPayeeAccount(e.target.value)}
                placeholder="例：工行 6222 0000 0000 1234"
              />
            </div>
            <div className="form-group">
              <label className="form-label">缴费说明</label>
              <textarea
                className="form-control"
                value={paymentInstructions}
                onChange={(e) => setPaymentInstructions(e.target.value)}
                placeholder="例：工作日 9:00-17:00 到物业服务中心缴费；银行转账请注明房号"
                style={{ minHeight: 60 }}
              />
            </div>
          </div>

          {/* §9.2 — 催收佣金率（按催收方式区分：自办→内勤率；外包→服务商率）*/}
          {mode === "self" ? (
            <div className="form-group">
              <label className="form-label">内勤催收员佣金率 (%)</label>
              <input
                className="form-control"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={internalCommRate}
                onChange={(e) => setInternalCommRate(e.target.value)}
                placeholder="例：5"
              />
              <div className="form-hint">留空 = 继承系统默认 5%</div>
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">服务商佣金率 (%)</label>
              <input
                className="form-control"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={providerCommRate}
                onChange={(e) => setProviderCommRate(e.target.value)}
                placeholder="例：8"
              />
              <div className="form-hint">
                外包项目按此初始佣金率结算；留空 = 继承系统默认 5%，服务商后续可自行调整
              </div>
            </div>
          )}

          {/* v1.6.1 / 1.6.2 — 项目级减免策略覆盖（拆分为两类） */}
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
              本金打折 与 滞纳金减免 可分别设置（多数物业愿意减免滞纳金，但本金打折通常更严格）。<b>留空</b>则继承租户默认。
            </div>

            {/* 本金打折 */}
            <div style={{ marginBottom: 14, padding: 10, background: "white", borderRadius: 6, border: "1px solid #e5e7eb" }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#7c2d12" }}>
                💰 本金打折策略
              </div>
              <div className="two-col">
                <div className="form-group">
                  <label className="form-label">自动批准阈值 (%)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max="100"
                    value={discountAutoThreshold}
                    onChange={(e) => setDiscountAutoThreshold(e.target.value)}
                    placeholder="租户默认 10"
                  />
                  <div className="form-hint">本金打折 &lt; X% 自动批准</div>
                </div>
                <div className="form-group">
                  <label className="form-label">督导可批上限 (%)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max="100"
                    value={discountSupervisorMax}
                    onChange={(e) => setDiscountSupervisorMax(e.target.value)}
                    placeholder="租户默认 30"
                  />
                  <div className="form-hint">本金打折 ≤ X% 督导批；&gt; X% 转 admin</div>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">本项目是否禁用本金打折</label>
                <select
                  className="form-control"
                  value={discountDisabled}
                  onChange={(e) => setDiscountDisabled(e.target.value as typeof discountDisabled)}
                >
                  <option value="">— 继承租户默认 —</option>
                  <option value="false">允许本金打折</option>
                  <option value="true">禁用本金打折</option>
                </select>
              </div>
            </div>

            {/* 滞纳金减免 */}
            <div style={{ padding: 10, background: "white", borderRadius: 6, border: "1px solid #e5e7eb" }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#0e7490" }}>
                ⏰ 滞纳金减免策略
              </div>
              <div className="form-hint" style={{ marginBottom: 8 }}>
                多数物业愿意减免滞纳金以换取本金回收；默认更宽松（50% 自动 / 100% 督导可批）
              </div>
              <div className="two-col">
                <div className="form-group">
                  <label className="form-label">自动批准阈值 (%)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max="100"
                    value={lateFeeAutoThreshold}
                    onChange={(e) => setLateFeeAutoThreshold(e.target.value)}
                    placeholder="租户默认 50"
                  />
                  <div className="form-hint">滞纳金减免 &lt; X% 自动批准</div>
                </div>
                <div className="form-group">
                  <label className="form-label">督导可批上限 (%)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    max="100"
                    value={lateFeeSupervisorMax}
                    onChange={(e) => setLateFeeSupervisorMax(e.target.value)}
                    placeholder="租户默认 100"
                  />
                  <div className="form-hint">滞纳金减免 ≤ X% 督导批；&gt; X% 转 admin</div>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">本项目是否禁用滞纳金减免</label>
                <select
                  className="form-control"
                  value={lateFeeDisabled}
                  onChange={(e) => setLateFeeDisabled(e.target.value as typeof lateFeeDisabled)}
                >
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
              placeholder="可选：项目背景、目标、关键节点等"
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
              {mutation.isPending ? "创建中…" : "创建项目"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModeRadio({
  checked,
  label,
  desc,
  onClick,
}: {
  checked: boolean;
  label: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <label
      onClick={onClick}
      style={{
        flex: "1 1 200px",
        cursor: "pointer",
        padding: 12,
        border: checked
          ? "1px solid var(--color-primary)"
          : "1px solid var(--color-neutral-200)",
        borderRadius: 6,
        background: checked ? "var(--color-primary-light, #eff6ff)" : "white",
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
      }}
    >
      <input
        type="radio"
        checked={checked}
        readOnly
        style={{ marginTop: 4 }}
      />
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: checked ? "var(--color-primary)" : "var(--color-neutral-700)" }}>
          {label}
        </div>
        <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
          {desc}
        </div>
      </div>
    </label>
  );
}
