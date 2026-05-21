// v0.7.0 — 服务商「我的项目」独立详情页(只读)
//
// 数据源:
//   GET /api/v1/provider/projects/{id}          项目卡 + 收费 + 合同 + KPI
//   GET /api/v1/provider/projects/{id}/team-stats 本服务商在该项目的员工绩效
//
// 设计原则:**只读**,服务商不能改项目本身(创建/编辑是物业 admin 的权限)。
// 唯一可操作:已分配案件管理 → 「跳到完整案件列表」link 到 /provider/cases?project_id=X
import { useCustom } from "@refinedev/core";
import {
  ArrowLeft, Briefcase, Building2, Calendar, DollarSign,
  FileText, FolderKanban, List, Percent, TrendingUp, UserCheck, Users,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

interface ProjectDetail {
  project_id: number;
  project_name: string;
  status: string;
  description: string | null;
  tenant_name: string;
  plan_start: string | null;
  plan_end: string | null;
  charge_rate_text: string | null;
  charge_period: string | null;
  charge_notes: string | null;
  contract_type: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  contract_attachment_filename: string | null;
  provider_pm_user_id: number | null;
  provider_pm_name: string | null;
  provider_agent_commission_rate: string | null;
  case_count: number;
  paid_count: number;
  recovered_amount: string;
  receivable_amount: string;
  estimated_commission: string | null;
}

interface TeamStatItem {
  user_id: number;
  name: string;
  case_count: number;
  paid_count: number;
  recovered_amount: string;
}

const CHARGE_PERIOD_LABEL: Record<string, string> = {
  monthly: "按月",
  quarterly: "按季",
  semiannual: "按半年",
  annual: "按年",
};

const CONTRACT_TYPE_LABEL: Record<string, string> = {
  preliminary_service: "前期物业服务",
  elected: "业主大会选聘",
  re_elected: "续聘",
  interim_management: "临时管理",
};

function dateOnly(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function daysFromNow(iso: string | null): number | null {
  if (!iso) return null;
  const target = new Date(iso).getTime();
  const now = Date.now();
  return Math.floor((target - now) / (24 * 3600 * 1000));
}

function servicePeriodBadge(plan_end: string | null): { label: string; color: string } {
  if (!plan_end) return { label: "长期合作", color: "var(--color-success)" };
  const days = daysFromNow(plan_end);
  if (days == null) return { label: "—", color: "var(--color-neutral-400)" };
  if (days < 0) return { label: `已到期 ${-days} 天`, color: "var(--color-neutral-500)" };
  if (days < 7) return { label: `剩余 ${days} 天 ⚠`, color: "var(--color-danger)" };
  if (days < 30) return { label: `剩余 ${days} 天`, color: "var(--color-warning)" };
  return { label: `剩余 ${days} 天`, color: "var(--color-success)" };
}

export function ProviderProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = Number(id);

  const { query: detailQ } = useCustom<ProjectDetail>({
    url: `provider/projects/${projectId}`,
    method: "get",
    queryOptions: { enabled: !!projectId, retry: false },
  });
  const { query: teamQ } = useCustom<{ items: TeamStatItem[] }>({
    url: `provider/projects/${projectId}/team-stats`,
    method: "get",
    queryOptions: { enabled: !!projectId, retry: false },
  });

  const d = detailQ.data?.data;
  const team = teamQ.data?.data?.items ?? [];

  if (detailQ.isLoading) {
    return <div style={{ padding: 32, color: "#9ca3af" }}>加载中…</div>;
  }
  if (!d) {
    return (
      <div style={{ padding: 32, color: "var(--color-danger)" }}>
        项目不存在或不在本服务商范围
      </div>
    );
  }

  const period = servicePeriodBadge(d.plan_end);

  return (
    <div style={{ padding: 16, maxWidth: 1280, margin: "0 auto" }}>
      {/* Breadcrumb + 顶栏 */}
      <div className="breadcrumb" style={{ marginBottom: 12 }}>
        <button
          type="button"
          onClick={() => navigate("/provider/projects")}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          返回项目列表
        </button>
        <span className="sep">›</span>
        <span className="current">{d.project_name}</span>
      </div>

      <div
        style={{
          display: "flex", alignItems: "center", gap: 12, marginBottom: 16,
          padding: "12px 16px", background: "white",
          border: "1px solid #e5e7eb", borderRadius: 8,
        }}
      >
        <FolderKanban className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          {d.project_name}
        </h1>
        <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
          <Building2 className="inline w-3 h-3" style={{ marginRight: 2 }} />
          {d.tenant_name}
        </span>
        <span
          className="ds-badge"
          style={{ fontSize: 11, background: period.color + "20", color: period.color }}
        >
          <Calendar className="inline w-3 h-3" style={{ marginRight: 2 }} />
          {period.label}
        </span>
        <span
          className={`ds-badge ${d.status === "active" ? "ds-badge-green" : "ds-badge-gray"}`}
          style={{ fontSize: 11 }}
        >
          {d.status === "active" ? "进行中" : d.status}
        </span>

        <button
          type="button"
          className="ds-btn ds-btn-primary ds-btn-sm"
          onClick={() => navigate(`/provider/cases?project_id=${d.project_id}`)}
          style={{ marginLeft: "auto" }}
        >
          <List className="w-3.5 h-3.5" />
          完整案件列表
        </button>
      </div>

      {/* KPI 3 卡 */}
      <div
        style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12, marginBottom: 16,
        }}
      >
        <KpiCard
          icon={<Briefcase className="w-4 h-4 text-[var(--color-primary)]" />}
          label="总户数"
          value={d.case_count}
          sub={`本月缴清 ${d.paid_count} 户`}
        />
        <KpiCard
          icon={<DollarSign className="w-4 h-4 text-[var(--color-success)]" />}
          label="本月已回款"
          value={`¥${d.recovered_amount}`}
          sub={`应收 ¥${d.receivable_amount} / 回款率 ${
            Number(d.receivable_amount) > 0
              ? ((Number(d.recovered_amount) / Number(d.receivable_amount)) * 100).toFixed(1)
              : "—"
          }%`}
          highlight
        />
        <KpiCard
          icon={<TrendingUp className="w-4 h-4 text-[var(--color-warning)]" />}
          label="预估佣金"
          value={d.estimated_commission ? `¥${d.estimated_commission}` : "—"}
          sub={
            d.provider_agent_commission_rate
              ? `按 ${(Number(d.provider_agent_commission_rate) * 100).toFixed(1)}% 估算`
              : "佣金率未设(继承系统默认 5%)"
          }
        />
      </div>

      {/* 2 列布局:左收费/合同;右团队 */}
      <div
        style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: 16, marginBottom: 16,
        }}
      >
        <Section title="收费与合同" icon={<FileText className="w-4 h-4 text-[var(--color-primary)]" />}>
          <RowField label="收费标准" value={d.charge_rate_text ?? "—"} multiline />
          <RowField
            label="收费周期"
            value={d.charge_period ? CHARGE_PERIOD_LABEL[d.charge_period] ?? d.charge_period : "—"}
          />
          <RowField
            label="合同类型"
            value={d.contract_type ? CONTRACT_TYPE_LABEL[d.contract_type] ?? d.contract_type : "—"}
          />
          <RowField
            label="合同期"
            value={`${dateOnly(d.contract_start_date)} → ${dateOnly(d.contract_end_date)}`}
          />
          {d.contract_attachment_filename && (
            <RowField label="合同附件" value={d.contract_attachment_filename} />
          )}
          {d.charge_notes && <RowField label="收费备注" value={d.charge_notes} multiline />}
          {d.description && <RowField label="项目说明" value={d.description} multiline />}
        </Section>

        <Section title="团队与佣金" icon={<Users className="w-4 h-4 text-[var(--color-primary)]" />}>
          <RowField
            label="项目经理"
            value={
              d.provider_pm_name ? (
                <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
                  <UserCheck className="inline w-3 h-3" style={{ marginRight: 2 }} />
                  {d.provider_pm_name}
                </span>
              ) : (
                <span style={{ color: "var(--color-danger)" }}>未指派</span>
              )
            }
          />
          <RowField
            label="服务商佣金率"
            value={
              d.provider_agent_commission_rate ? (
                <span style={{ fontWeight: 500 }}>
                  <Percent className="inline w-3 h-3" style={{ marginRight: 2 }} />
                  {(Number(d.provider_agent_commission_rate) * 100).toFixed(1)}%
                </span>
              ) : (
                <span style={{ color: "#9ca3af" }}>继承默认 5%</span>
              )
            }
          />

          <div style={{ marginTop: 12, fontSize: 12, fontWeight: 600, color: "#374151" }}>
            本项目接案员工({team.length})
          </div>
          {teamQ.isLoading ? (
            <div style={{ padding: 8, fontSize: 12, color: "#9ca3af" }}>加载中…</div>
          ) : team.length === 0 ? (
            <div style={{ padding: 8, fontSize: 12, color: "#9ca3af" }}>
              本项目暂无本服务商员工接案
            </div>
          ) : (
            <table style={{ width: "100%", fontSize: 12, marginTop: 6 }}>
              <thead>
                <tr style={{ background: "#f9fafb" }}>
                  <th style={{ padding: 6, textAlign: "left" }}>员工</th>
                  <th style={{ padding: 6, textAlign: "right" }}>案件数</th>
                  <th style={{ padding: 6, textAlign: "right" }}>缴清数</th>
                  <th style={{ padding: 6, textAlign: "right" }}>本月回款</th>
                </tr>
              </thead>
              <tbody>
                {team.map((m) => (
                  <tr key={m.user_id} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: 6 }}>{m.name}</td>
                    <td style={{ padding: 6, textAlign: "right", fontFamily: "monospace" }}>
                      {m.case_count}
                    </td>
                    <td
                      style={{
                        padding: 6, textAlign: "right", fontFamily: "monospace",
                        color: "var(--color-success)",
                      }}
                    >
                      {m.paid_count}
                    </td>
                    <td
                      style={{
                        padding: 6, textAlign: "right", fontFamily: "monospace",
                        color: "var(--color-success)",
                      }}
                    >
                      ¥{m.recovered_amount}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      </div>

      {/* 嵌入「项目案件简表」— 5 条预览 + 跳完整列表链接 */}
      <Section
        title={`案件预览(共 ${d.case_count} 户 · 已缴清 ${d.paid_count})`}
        icon={<List className="w-4 h-4 text-[var(--color-primary)]" />}
      >
        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
          仅展示前 5 条简表,完整列表请走顶部「完整案件列表」按钮。
        </div>
        <Link
          to={`/provider/cases?project_id=${d.project_id}`}
          style={{ fontSize: 13, color: "var(--color-primary)" }}
        >
          → 查看本项目所有案件(过滤 project_id={d.project_id})
        </Link>
      </Section>

      <div
        style={{
          marginTop: 16, padding: 10, background: "#f9fafb",
          borderRadius: 6, fontSize: 11, color: "#6b7280", textAlign: "center",
        }}
      >
        本页面为<strong>只读</strong>视图。项目创建、收费配置、合同管理由<strong>物业管理员</strong>负责,
        服务商无法修改项目本身;可通过「指派项目经理」「设置佣金率」管理本服务商在该项目的人员/财务配置(详项目列表)。
      </div>
    </div>
  );
}

function KpiCard({
  icon, label, value, sub, highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  sub: string;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        background: "white", border: "1px solid #e5e7eb",
        borderRadius: 8, padding: 14,
        borderLeft: highlight ? "3px solid var(--color-success)" : "1px solid #e5e7eb",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        {icon}
        <span style={{ fontSize: 12, color: "#6b7280", fontWeight: 500 }}>{label}</span>
      </div>
      <div
        style={{
          fontSize: 22, fontWeight: 700,
          color: highlight ? "var(--color-success)" : "#111827",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function Section({
  title, icon, children,
}: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "white", border: "1px solid #e5e7eb",
        borderRadius: 8, padding: 14,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        {icon}
        <strong style={{ fontSize: 14, color: "#111827" }}>{title}</strong>
      </div>
      {children}
    </div>
  );
}

function RowField({
  label, value, multiline,
}: { label: string; value: React.ReactNode; multiline?: boolean }) {
  return (
    <div style={{ display: "flex", marginBottom: 8, fontSize: 13 }}>
      <span style={{ width: 100, color: "#6b7280", flexShrink: 0 }}>{label}</span>
      <span
        style={{
          flex: 1, color: "#111827",
          whiteSpace: multiline ? "pre-wrap" : "normal",
        }}
      >
        {value}
      </span>
    </div>
  );
}

export default ProviderProjectDetailPage;
