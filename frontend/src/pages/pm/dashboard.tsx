import { useCustom, useGetIdentity } from "@refinedev/core";
import {
  Briefcase,
  ClipboardList,
  DollarSign,
  LayoutDashboard,
  Scale,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import type { AuthUser } from "../../providers/auth-provider";

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

export function PMDashboardPage() {
  const { data: identity, isLoading: identityLoading } =
    useGetIdentity<AuthUser>();
  const role = identity?.role ?? "";

  const isProperty = role === "project_manager_property" || role === "admin";
  const isProvider = role === "project_manager_provider";

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
        <h3 className="font-semibold text-sm mb-3">合作租户 Top 5（按通话量）</h3>
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
                  暂无合作租户
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
