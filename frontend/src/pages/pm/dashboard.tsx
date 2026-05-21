import { useCustom, useGetIdentity } from "@refinedev/core";
import {
  Briefcase,
  ClipboardList,
  DollarSign,
  FolderKanban,
  LayoutDashboard,
  Scale,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
// v0.7.0 — PmAlertsSection 抽到独立文件,与服务商 dashboard 共享
import { PmAlertsSection } from "../../components/dashboard/PmAlertsSection";

interface PmProjectCard {
  project_id: number;
  project_name: string;
  role_in_project: string;
  case_count: number;
  receivable: number;
  received: number;
  promised_count: number;
  new_count: number;
  in_progress_count: number;
  escalated_count: number;
  provider_name: string | null;
}

interface TopOverdueItem {
  case_id: number;
  owner_name: string;
  amount_owed: string | null;
  months_overdue: number | null;
  stage: string;
}

interface PMPropertyStats {
  active_cases_count: number;
  recovered_amount_month: number;
  pending_workorders: number;
  escalated_legal_cases: number;
  agent_count: number;
  top_overdue: TopOverdueItem[];
}

interface TopTenantItem {
  tenant_id: number;
  tenant_name: string;
  total_minutes: number;
  contract_status: string | null;
}

interface PMProviderStats {
  active_contracts_count: number;
  total_revenue_month: number;
  agent_count: number;
  pending_settlements: number;
  top_tenants_by_volume: TopTenantItem[];
}

function formatCurrency(n: number | null | undefined): string {
  return `¥${(n ?? 0).toLocaleString()}`;
}

function MyProjectsSection() {
  const navigate = useNavigate();
  const { query } = useCustom<PmProjectCard[]>({
    url: "pm/projects",
    method: "get",
  });
  const cardsRaw = query.data?.data;
  const cards: PmProjectCard[] = Array.isArray(cardsRaw)
    ? cardsRaw
    : ((cardsRaw as unknown as { items?: PmProjectCard[] })?.items ?? []);

  if (query.isLoading) return null;
  if (cards.length === 0) {
    return (
      <div
        style={{
          background: "#f9fafb",
          border: "1px dashed #d1d5db",
          borderRadius: 8,
          padding: 24,
          textAlign: "center",
          color: "#9ca3af",
        }}
      >
        <FolderKanban size={32} style={{ margin: "0 auto 8px" }} />
        <div>当前没有指派给您的项目</div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          请联系物业管理员将您指定为项目负责人
        </div>
      </div>
    );
  }
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <h2
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--color-neutral-700)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <FolderKanban size={14} />
          我管理的项目（共 {cards.length} 个）
        </h2>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
        }}
      >
        {cards.map((p) => {
          const recoveryRate =
            p.receivable > 0 ? (p.received / p.receivable) * 100 : 0;
          return (
            <div
              key={p.project_id}
              className="ds-card"
              style={{ cursor: "pointer", transition: "border-color .15s" }}
              onClick={() =>
                navigate(`/admin/cases?project_id=${p.project_id}`)
              }
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor = "var(--color-primary)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor =
                  "var(--color-neutral-200)")
              }
            >
              <div className="card-body">
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--color-neutral-900)",
                    marginBottom: 4,
                  }}
                >
                  {p.project_name}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--color-neutral-500)",
                    marginBottom: 12,
                  }}
                >
                  {p.provider_name ? (
                    <span>合作服务商：{p.provider_name}</span>
                  ) : (
                    <span>自营</span>
                  )}
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 8,
                    fontSize: 12,
                  }}
                >
                  <div>
                    <div style={{ color: "#6b7280" }}>案件数</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>
                      {p.case_count}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: "#6b7280" }}>回款率</div>
                    <div
                      style={{
                        fontSize: 18,
                        fontWeight: 700,
                        color:
                          recoveryRate > 50
                            ? "#057a55"
                            : recoveryRate > 20
                              ? "#d97706"
                              : "var(--color-neutral-700)",
                      }}
                    >
                      {recoveryRate.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div style={{ color: "#6b7280" }}>应收</div>
                    <div style={{ fontWeight: 600 }}>
                      ¥{p.receivable.toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: "#6b7280" }}>已收</div>
                    <div style={{ fontWeight: 600, color: "#057a55" }}>
                      ¥{p.received.toLocaleString()}
                    </div>
                  </div>
                </div>
                <div
                  style={{
                    marginTop: 10,
                    paddingTop: 10,
                    borderTop: "1px solid #f3f4f6",
                    fontSize: 11,
                    color: "#6b7280",
                  }}
                >
                  新 {p.new_count} · 跟进 {p.in_progress_count} · 承诺{" "}
                  {p.promised_count} · 升级 {p.escalated_count}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PMDashboardPage() {
  const { data: identity, isLoading: identityLoading } =
    useGetIdentity<AuthUser>();
  const role = identity?.role ?? "";
  const scope = identity?.scope ?? "";

  // project_manager on provider-side (scope=provider:{id}) → ProviderView
  // project_manager on property-side (scope=tenant:{id}) → PropertyView
  // admin also has access to PropertyView
  const isProvider =
    role === "project_manager" && scope.startsWith("provider:");
  const isProperty =
    (role === "project_manager" && !scope.startsWith("provider:")) ||
    role === "admin";

  if (identityLoading) {
    return <div className="p-6 text-neutral-500">加载中…</div>;
  }

  if (isProperty) {
    return <PropertyView />;
  }
  if (isProvider) {
    return <ProviderView />;
  }
  return (
    <div className="p-6 text-sm text-[var(--color-danger)]">
      角色 ({role}) 无项目看板权限
    </div>
  );
}

function PropertyView() {
  const { query } = useCustom<PMPropertyStats>({
    url: "pm/dashboard/property",
    method: "get",
  });
  const raw = query.data?.data;

  if (query.isLoading) return <div className="p-6 text-neutral-500">加载中…</div>;
  if (query.isError || !raw)
    return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;

  // 防御 server response 部分字段缺失
  const stats: PMPropertyStats = {
    active_cases_count: raw.active_cases_count ?? 0,
    recovered_amount_month: raw.recovered_amount_month ?? 0,
    pending_workorders: raw.pending_workorders ?? 0,
    escalated_legal_cases: raw.escalated_legal_cases ?? 0,
    agent_count: raw.agent_count ?? 0,
    top_overdue: raw.top_overdue ?? [],
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <LayoutDashboard className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          物业项目经理看板
        </h1>
      </div>

      {/* v0.6.0 — 运营提醒(5 类) */}
      <PmAlertsSection />

      {/* v1.4 — 我管理的项目（多项目卡片） */}
      <MyProjectsSection />

      {/* 4 KPI cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
        }}
      >
        <KpiCard
          label="进行中案件"
          value={stats.active_cases_count}
          icon={<Briefcase size={14} />}
        />
        <KpiCard
          label="本月已回款"
          value={formatCurrency(stats.recovered_amount_month)}
          icon={<DollarSign size={14} />}
        />
        <KpiCard
          label="待处理工单"
          value={stats.pending_workorders}
          icon={<ClipboardList size={14} />}
          warn={stats.pending_workorders > 0}
        />
        <KpiCard
          label="进行中法务案"
          value={stats.escalated_legal_cases}
          icon={<Scale size={14} />}
        />
      </div>

      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: 16,
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm">高额欠费 Top 5</h3>
          <span className="text-xs text-[var(--color-neutral-400)]">
            <Users className="inline w-3 h-3 mr-1" />
            团队规模 {stats.agent_count} 人
          </span>
        </div>
        <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "#6b7280", textAlign: "left" }}>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>业主</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>欠费(元)</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>逾期月数</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>阶段</th>
            </tr>
          </thead>
          <tbody>
            {stats.top_overdue.map((item) => (
              <tr
                key={item.case_id}
                style={{ borderTop: "1px solid #f3f4f6" }}
              >
                <td style={{ padding: "8px 10px" }}>{item.owner_name}</td>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>
                  {item.amount_owed ?? "—"}
                </td>
                <td style={{ padding: "8px 10px" }}>
                  {item.months_overdue ?? "—"}
                </td>
                <td style={{ padding: "8px 10px" }}>{item.stage}</td>
              </tr>
            ))}
            {stats.top_overdue.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}
                >
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProviderView() {
  const { query } = useCustom<PMProviderStats>({
    url: "pm/dashboard/provider",
    method: "get",
  });
  const raw = query.data?.data;

  if (query.isLoading) return <div className="p-6 text-neutral-500">加载中…</div>;
  if (query.isError || !raw)
    return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;

  const stats: PMProviderStats = {
    active_contracts_count: raw.active_contracts_count ?? 0,
    total_revenue_month: raw.total_revenue_month ?? 0,
    agent_count: raw.agent_count ?? 0,
    pending_settlements: raw.pending_settlements ?? 0,
    top_tenants_by_volume: raw.top_tenants_by_volume ?? [],
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <LayoutDashboard className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          服务商项目经理看板
        </h1>
      </div>

      {/* v0.6.0 — 运营提醒(5 类) */}
      <PmAlertsSection />

      {/* v1.4 — 我管理的项目（多项目卡片） */}
      <MyProjectsSection />

      {/* 4 KPI cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
        }}
      >
        <KpiCard
          label="活跃合同数"
          value={stats.active_contracts_count}
          icon={<Briefcase size={14} />}
        />
        <KpiCard
          label="本月营收"
          value={formatCurrency(stats.total_revenue_month)}
          icon={<DollarSign size={14} />}
        />
        <KpiCard
          label="团队规模"
          value={stats.agent_count}
          icon={<Users size={14} />}
        />
        <KpiCard
          label="待结算账单"
          value={stats.pending_settlements}
          icon={<ClipboardList size={14} />}
          warn={stats.pending_settlements > 0}
        />
      </div>

      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: 16,
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        <h3 className="font-semibold text-sm mb-3">合作物业 Top 5（按通话量）</h3>
        <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "#6b7280", textAlign: "left" }}>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>租户</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>累计通话</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>合同状态</th>
            </tr>
          </thead>
          <tbody>
            {stats.top_tenants_by_volume.map((item) => (
              <tr
                key={item.tenant_id}
                style={{ borderTop: "1px solid #f3f4f6" }}
              >
                <td style={{ padding: "8px 10px" }}>{item.tenant_name}</td>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>
                  {item.total_minutes}
                </td>
                <td style={{ padding: "8px 10px" }}>
                  {item.contract_status ?? "—"}
                </td>
              </tr>
            ))}
            {stats.top_tenants_by_volume.length === 0 && (
              <tr>
                <td
                  colSpan={3}
                  style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}
                >
                  暂无合作物业
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface KpiCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  warn?: boolean;
}

function KpiCard({ label, value, icon, warn = false }: KpiCardProps) {
  return (
    <div
      style={{
        background: warn ? "#fffbeb" : "#fff",
        borderRadius: 8,
        padding: 16,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        border: warn ? "1px solid #fed7aa" : "1px solid #f3f4f6",
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: warn ? "#92400e" : "#6b7280",
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        {icon}
        {label}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 600,
          marginTop: 6,
          color: warn ? "#d97706" : "#111827",
        }}
      >
        {value}
      </div>
    </div>
  );
}

// v0.7.0 — PmAlertsSection 已抽到 components/dashboard/PmAlertsSection.tsx,
//          PM dashboard 和服务商 admin dashboard 共享同一份。原 inline 实现已移除。
