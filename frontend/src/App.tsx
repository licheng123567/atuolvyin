import { Authenticated, Refine, useGetIdentity } from "@refinedev/core";
import routerBindings from "@refinedev/react-router";
import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { AppIntroModal } from "./components/onboarding/AppIntroModal";
import { LoginPage } from "./pages/login";
import { VerifyPage } from "./pages/verify";
import { HelpAppPage } from "./pages/help/app";
import { PaymentBillPage } from "./pages/public/PaymentBillPage";

const API_BASE_URL = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";
import { TenantListPage } from "./pages/ops/tenants/index";
import { TenantNewPage } from "./pages/ops/tenants/new";
import { TenantDetailPage } from "./pages/ops/tenants/[id]";
import { TenantTrialPage } from "./pages/ops/tenants/trial";
import { ProviderListPage } from "./pages/ops/providers/index";
import { ProviderNewPage } from "./pages/ops/providers/new";
import { ProviderDetailPage } from "./pages/ops/providers/[id]";
import { UserEditPage } from "./pages/admin/users/edit";
import { UserListPage } from "./pages/admin/users/index";
import { UserNewPage } from "./pages/admin/users/new";
import { AdminProjectListPage } from "./pages/admin/projects/index";
import { AdminProjectNewPage } from "./pages/admin/projects/new";
import { AdminProjectEditPage } from "./pages/admin/projects/edit";
import { CaseListPage } from "./pages/admin/cases/index";
import { CaseImportPage } from "./pages/admin/cases/import";
import { CaseKanbanPage } from "./pages/admin/cases/kanban";
import { AgentCaseListPage } from "./pages/agent/cases/index";
import { AdminCaseDetailPage } from "./pages/admin/cases/detail";
import { AgentWorkstationPage } from "./pages/agent/cases/detail";
import { CallDetailPage } from "./pages/calls/detail";
import { AgentLiveWorkstationPage } from "./pages/agent/workstation/live";
import { AgentWorkstationIndexPage } from "./pages/agent/workstation/index";
import { AgentCallHistoryPage } from "./pages/agent/call-history/index";
import { AgentProfilePage } from "./pages/agent/profile/index";
import { AdminLiveWorkstationPage } from "./pages/admin/workstation/live";
import { ScriptListPage } from "./pages/admin/scripts/list";
import { ScriptVersionsPage } from "./pages/admin/scripts/versions";
import { ScriptEffectivenessPage } from "./pages/admin/scripts/effectiveness";
import { AdminReportsPage } from "./pages/admin/reports/index";
import { ComplianceListPage } from "./pages/admin/compliance/index";
import { ComplianceDetailPage } from "./pages/admin/compliance/detail";
import { AdminLegalConversionListPage } from "./pages/admin/legal-conversion/index";
import { AdminLegalConversionDetailPage } from "./pages/admin/legal-conversion/[id]";
import { SupervisorCaseDetailPage } from "./pages/supervisor/cases/detail";
import { TenantLegalOrdersPage, TenantLegalOrderDetailPage } from "./pages/legal-flow/TenantLegalOrdersPage";
import { LawFirmOrdersPage, LawFirmOrderDetailPage } from "./pages/legal-flow/LawFirmOrdersPage";
import { LawyerOrdersPage, LawyerOrderDetailPage } from "./pages/legal-flow/LawyerOrdersPage";
import { SupervisorDiscountApprovalsPage, SupervisorDiscountApprovalDetailPage } from "./pages/discount/SupervisorApprovals";
import { SupervisorLegalConversionApprovalsPage } from "./pages/supervisor/legal-conversion-approvals/index";
import { AdminDiscountApprovalsPage, AdminDiscountApprovalDetailPage } from "./pages/discount/AdminApprovals";
import { AdminSettingsPage } from "./pages/admin/settings/index";
import { AdminDashboardPage } from "./pages/admin/dashboard";
import { AdminPoolPage } from "./pages/admin/pool";
import { AdminSettlementListPage } from "./pages/admin/settlements";
import { AdminSettlementDetailPage } from "./pages/admin/settlements/detail";
import { AdminAuditLogPage } from "./pages/admin/audit-logs";
import { AdminAgentDevicesPage } from "./pages/admin/agent-devices";
import { AdminProvidersPage } from "./pages/admin/providers/index";
import { AdminProviderDetailPage } from "./pages/admin/providers/detail";
import { SupervisorScriptLabelsPage } from "./pages/supervisor/script-labels";
import { SupervisorReviewsPage } from "./pages/supervisor/reviews";
import { SupervisorReviewDetailPage } from "./pages/supervisor/reviews/detail";
import { SupervisorRiskEventsPage } from "./pages/supervisor/risk-events";
import { SupervisorTeamPerformancePage } from "./pages/supervisor/team-performance";
import { OpsSettlementsOverviewPage } from "./pages/ops/settlements";
import { OpsLawFirmsPage } from "./pages/ops/law-firms/index";
import { OpsLegalPackagesPage } from "./pages/ops/legal-packages/index";
import { OpsLegalWorkstationPage } from "./pages/ops/legal-workstation/index";
import { OpsAnnouncementsPage } from "./pages/ops/announcements";
import { OpsMyAuditLogsPage } from "./pages/ops/audit-logs";
import { SuperLlmPromptsPage } from "./pages/super/llm-prompts";
import { SuperBlockchainConfigPage } from "./pages/super/blockchain-config";
import { SuperSmsConfigPage } from "./pages/super/sms-config";
import { ProviderTeamPerformancePage } from "./pages/provider/team-performance";
import { ProviderMemberCommissionPage } from "./pages/provider/commission";
import { OpsCustomerFollowupsPage } from "./pages/ops/customer-followups";
import { authProvider, getToken } from "./providers/auth-provider";
import { dataProvider } from "./providers";
import { AppMobileRoutes } from "./router/appRoutes";
import { useSupervisorAlerts } from "./hooks/useSupervisorAlerts";
import { SupervisorAlertsPage } from "./pages/supervisor/alerts";
import { SupervisorLiveWallPage } from "./pages/supervisor/live-wall";
import { RiskKeywordListPage } from "./pages/admin/risk-keywords/list";
import { RiskKeywordCreatePage } from "./pages/admin/risk-keywords/create";
import { RiskKeywordEditPage } from "./pages/admin/risk-keywords/edit";
import { LegalCaseListPage } from "./pages/legal/cases/index";
import { LegalCaseDetailPage } from "./pages/legal/cases/[id]";
import { LegalInternalOrdersPage } from "./pages/legal/internal-orders/index";
import { LegalInternalOrderDetailPage } from "./pages/legal/internal-orders/[id]";
import { LegalPendingFinalizePage } from "./pages/legal/pending-finalize/index";
import { AdminPartnerLawFirmsPage } from "./pages/admin/partner-law-firms/index";
import { AdminInternalLetterTemplatesPage } from "./pages/admin/internal-letter-templates/index";
import { WorkOrderListPage } from "./pages/workorder/orders/index";
import { WorkOrderNewPage } from "./pages/workorder/orders/new";
import { WorkOrderDetailPage } from "./pages/workorder/orders/[id]";
import { PMDashboardPage } from "./pages/pm/dashboard";
import { MePage } from "./pages/me";
import { SupervisorProjectsPage } from "./pages/supervisor/projects";
import { SupervisorWorkspacePage } from "./pages/supervisor/workspace";
import { SupervisorEscalatedPage } from "./pages/supervisor/escalated";
import { SupervisorStatsPage } from "./pages/supervisor/stats";
import { SupervisorCasesPage } from "./pages/supervisor/cases";
import { SupervisorMyKpiPage } from "./pages/supervisor/my-kpi";
import { SupervisorPromisesPage } from "./pages/supervisor/promises";
import { SupervisorCaseAlertsPage } from "./pages/supervisor/case-alerts";
import { SupervisorShiftsPage } from "./pages/supervisor/shifts";
import { SupervisorTrainingPage } from "./pages/supervisor/training";
import { ProviderDashboardPage } from "./pages/provider/dashboard";
import { ProviderHistoricalReportsPage } from "./pages/provider/historical-reports";
import { ProviderLegalCasesPage } from "./pages/provider/legal/cases";
import { ProviderLegalCaseDetailPage } from "./pages/provider/legal/cases/[id]";
import { ProviderLegalRequestsPage } from "./pages/provider/legal/requests";
import { ProviderLegalRequestDetailPage } from "./pages/provider/legal/requests/[id]";
import { ProviderProjectsPage } from "./pages/provider/projects";
import { ProviderScriptListPage } from "./pages/provider/scripts";
import { ProviderTenantsPage } from "./pages/provider/tenants";
import { ProviderTeamPage } from "./pages/provider/team";
import { ProviderSettlementListPage } from "./pages/provider/settlements";
import { ProviderSettlementDetailPage } from "./pages/provider/settlements/[id]";
import { SuperHealthPage } from "./pages/super/health";
import { SuperAuditPage } from "./pages/super/audit";
import { SuperCostPage } from "./pages/super/cost";
import { SuperPlansPage } from "./pages/super/plans";
import type { AuthUser } from "./providers/auth-provider";

const SUPERVISOR_ROLES = new Set(["supervisor", "admin", "superadmin"]);

// Home redirect: for roles that have scope-dependent home pages,
// RoleHomeRedirect reads scope from identity to decide the correct page.
// admin with scope=provider:{id} → /provider/dashboard
// project_manager with scope=provider:{id} → /pm/dashboard (provider view)
// project_manager with scope=tenant:{id} → /pm/dashboard (property view)
const ROLE_HOME: Record<string, string> = {
  superadmin: "/ops/tenants",
  ops: "/ops/tenants",
  // admin: scope-dependent — handled in RoleHomeRedirect below
  supervisor: "/supervisor/workspace",
  agent: "/agent/cases",
  legal: "/legal/internal-orders",
  workorder: "/workorder/orders",
  coordinator: "/workorder/orders",
  project_manager: "/pm/dashboard",
};

function RoleHomeRedirect() {
  const { data, isLoading } = useGetIdentity<{ role: string; scope?: string }>();
  if (isLoading) return null;
  const role = data?.role;
  const scope = data?.scope ?? "";

  // admin role: property-side (tenant:{id}) → /admin/projects
  //             provider-side (provider:{id}) → /provider/dashboard
  if (role === "admin") {
    const target = scope.startsWith("provider:") ? "/provider/dashboard" : "/admin/projects";
    return <Navigate to={target} replace />;
  }

  const target = role ? ROLE_HOME[role] : null;
  if (!target) {
    return (
      <div className="text-[var(--color-neutral-900)]">
        <h1 className="text-2xl font-semibold mb-2">欢迎使用有证慧催</h1>
        <p className="text-sm text-[var(--color-neutral-600)]">
          未识别到角色（{role ?? "未知"}），请联系管理员。
        </p>
      </div>
    );
  }
  return <Navigate to={target} replace />;
}

function AuthenticatedShell() {
  const { data: identity } = useGetIdentity<AuthUser>();
  const isSupervisor = SUPERVISOR_ROLES.has(identity?.role ?? "");
  useSupervisorAlerts(isSupervisor ? getToken() : null);
  return (
    <AppLayout>
      <Outlet />
      <AppIntroModalGate />
    </AppLayout>
  );
}

// Sprint 14.3 — 首登 App 引导（v1.5.6 — 仅对催收员显示）
const APP_INTRO_ROLES = new Set([
  "agent",
]);

function AppIntroModalGate() {
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);
  const { data: identity } = useGetIdentity<AuthUser>();
  const role = identity?.role;
  const isCallingRole = role !== undefined && APP_INTRO_ROLES.has(role);

  useEffect(() => {
    if (checked) return;
    if (role === undefined) return;  // identity 还没回来
    if (!isCallingRole) {
      setChecked(true);
      return;  // 非催收员：直接静默
    }
    const token = getToken();
    if (!token) return;
    fetch(`${API_BASE_URL}/api/v1/users/me/preferences`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: { preferences?: { app_intro_dismissed?: boolean } }) => {
        if (!d.preferences?.app_intro_dismissed) setOpen(true);
      })
      .catch(() => {
        /* fail silently — modal not shown */
      })
      .finally(() => setChecked(true));
  }, [checked, role, isCallingRole]);

  const dismissPermanent = () => {
    const token = getToken();
    if (!token) return;
    void fetch(`${API_BASE_URL}/api/v1/users/me/preferences`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ preferences: { app_intro_dismissed: true } }),
    });
  };

  return (
    <AppIntroModal
      open={open}
      onDismiss={() => setOpen(false)}
      onPermanentDismiss={dismissPermanent}
    />
  );
}

function App() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        routerProvider={routerBindings}
        resources={[
          {
            name: "ops/tenants",
            list: "/ops/tenants",
            create: "/ops/tenants/new",
            show: "/ops/tenants/:id",
          },
          {
            name: "ops/providers",
            list: "/ops/providers",
            create: "/ops/providers/new",
            show: "/ops/providers/:id",
            meta: { label: "服务商管理" },
          },
          {
            name: "admin/users",
            list: "/admin/users",
            create: "/admin/users/new",
          },
          {
            name: "admin/cases",
            list: "/admin/cases",
            create: "/admin/cases/import",
            show: "/admin/cases/:id",
          },
          {
            name: "agent/cases",
            list: "/agent/cases",
            show: "/agent/cases/:id",
          },
          {
            name: "calls",
            show: "/calls/:id",
          },
          {
            name: "supervisor/alerts",
            list: "/supervisor/alerts",
          },
          {
            name: "admin/risk-keywords",
            list: "/admin/risk-keywords",
            create: "/admin/risk-keywords/new",
            edit: "/admin/risk-keywords/:id/edit",
          },
          {
            name: "admin/scripts",
            list: "/admin/scripts",
            show: "/admin/scripts/:id/versions",
            meta: { label: "话术库" },
          },
          {
            name: "admin/partner-law-firms",
            list: "/admin/partner-law-firms",
            meta: { label: "合作律所" },
          },
          {
            name: "admin/internal-letter-templates",
            list: "/admin/internal-letter-templates",
            meta: { label: "律师函模板" },
          },
          {
            name: "admin/pool",
            list: "/admin/pool",
            meta: { label: "公海管理" },
          },
          {
            name: "admin/settlements",
            list: "/admin/settlements",
            show: "/admin/settlements/:id",
            meta: { label: "结算管理" },
          },
          {
            name: "admin/providers",
            list: "/admin/providers",
            show: "/admin/providers/:id",
            meta: { label: "服务商合作" },
          },
          {
            name: "supervisor/script-labels",
            list: "/supervisor/script-labels",
            meta: { label: "话术标注" },
          },
          {
            name: "supervisor/reviews",
            list: "/supervisor/reviews",
            meta: { label: "质检复核" },
          },
          {
            name: "legal/internal-orders",
            list: "/legal/internal-orders",
            show: "/legal/internal-orders/:id",
            meta: { label: "待内部处理" },
          },
          {
            name: "legal/cases",
            list: "/legal/cases",
            show: "/legal/cases/:id",
            meta: { label: "法务案件" },
          },
          {
            name: "workorders",
            list: "/workorder/orders",
            create: "/workorder/orders/new",
            show: "/workorder/orders/:id",
            meta: { label: "工单管理" },
          },
          {
            name: "provider/tenants",
            list: "/provider/tenants",
            meta: { label: "合作租户" },
          },
          {
            name: "provider/team",
            list: "/provider/team",
            meta: { label: "团队管理" },
          },
          {
            name: "provider/settlements",
            list: "/provider/settlements",
            show: "/provider/settlements/:id",
            meta: { label: "收入结算" },
          },
        ]}
        options={{ syncWithLocation: true, warnWhenUnsavedChanges: false }}
      >
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/verify" element={<VerifyPage />} />
          <Route path="/verify/:tx_hash" element={<VerifyPage />} />
          <Route path="/help/app" element={<HelpAppPage />} />
          <Route path="/pay/:token" element={<PaymentBillPage />} />

          {/* v2.0 — Android WebView 移动路由（独立布局，无 PC 侧边栏） */}
          <Route path="/app/*" element={<AppMobileRoutes />} />

          {/* Protected — wrapped in layout shell */}
          <Route
            element={
              <Authenticated
                key="app"
                fallback={<Navigate to="/login" replace />}
              >
                <AuthenticatedShell />
              </Authenticated>
            }
          >
            <Route path="/" element={<RoleHomeRedirect />} />
            {/* Ops - Tenant Management */}
            <Route path="/ops/tenants" element={<TenantListPage />} />
            <Route path="/ops/tenants/trial" element={<TenantTrialPage />} />
            <Route path="/ops/tenants/new" element={<TenantNewPage />} />
            <Route path="/ops/tenants/:id" element={<TenantDetailPage />} />
            {/* Ops - Service Provider Management */}
            <Route path="/ops/providers" element={<ProviderListPage />} />
            <Route path="/ops/providers/new" element={<ProviderNewPage />} />
            <Route path="/ops/providers/:id" element={<ProviderDetailPage />} />
            {/* Admin - Dashboard */}
            {/* v1.5 — 全角色个人中心 */}
            <Route path="/me" element={<MePage />} />
            <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
            {/* Admin - User Management */}
            <Route path="/admin/users" element={<UserListPage />} />
            <Route path="/admin/users/new" element={<UserNewPage />} />
            <Route path="/admin/users/:id/edit" element={<UserEditPage />} />
            {/* Admin - Project Management (v1.4) */}
            <Route path="/admin/projects" element={<AdminProjectListPage />} />
            <Route path="/admin/projects/new" element={<AdminProjectNewPage />} />
            <Route path="/admin/projects/:id/edit" element={<AdminProjectEditPage />} />
            {/* Admin - Case Management */}
            <Route path="/admin/cases" element={<CaseListPage />} />
            <Route path="/admin/cases/kanban" element={<CaseKanbanPage />} />
            <Route path="/admin/cases/import" element={<CaseImportPage />} />
            {/* Agent - Case List */}
            <Route path="/agent/cases" element={<AgentCaseListPage />} />
            {/* Admin - Case Detail */}
            <Route path="/admin/cases/:id" element={<AdminCaseDetailPage />} />
            {/* Agent - Case Detail / Workstation */}
            <Route path="/agent/cases/:id" element={<AgentWorkstationPage />} />
            {/* Call Detail */}
            <Route path="/calls/:id" element={<CallDetailPage />} />
            {/* Agent Live Workstation — 直接带 call_id 进入（兼容旧链接 / 通话记录跳转） */}
            <Route path="/agent/workstation/:call_id" element={<AgentLiveWorkstationPage />} />
            {/* Agent — 工作台入口（4 列布局 + 5s 轮询 active-call 实现 App→PC 同步） */}
            <Route path="/agent/workstation" element={<AgentWorkstationIndexPage />} />
            {/* Agent — 通话记录 */}
            <Route path="/agent/call-history" element={<AgentCallHistoryPage />} />
            {/* Agent — 个人信息 */}
            <Route path="/agent/profile" element={<AgentProfilePage />} />
            {/* Admin Observer Workstation */}
            <Route path="/admin/workstation/:call_id" element={<AdminLiveWorkstationPage />} />
            {/* Supervisor Alerts */}
            <Route path="/supervisor/alerts" element={<SupervisorAlertsPage />} />
            {/* Admin - Risk Keywords */}
            <Route path="/admin/risk-keywords" element={<RiskKeywordListPage />} />
            <Route path="/admin/risk-keywords/new" element={<RiskKeywordCreatePage />} />
            <Route path="/admin/risk-keywords/:id/edit" element={<RiskKeywordEditPage />} />
            {/* Admin - Script Library */}
            <Route path="/admin/scripts" element={<ScriptListPage />} />
            <Route path="/admin/scripts/effectiveness" element={<ScriptEffectivenessPage />} />
            <Route path="/admin/scripts/:id/versions" element={<ScriptVersionsPage />} />
            {/* Admin - Public Pool Management */}
            <Route path="/admin/pool" element={<AdminPoolPage />} />
            {/* Admin - Settlement Management */}
            <Route path="/admin/settlements" element={<AdminSettlementListPage />} />
            <Route path="/admin/settlements/:id" element={<AdminSettlementDetailPage />} />
            <Route path="/admin/audit-logs" element={<AdminAuditLogPage />} />
            {/* v2.1 — Admin/Supervisor: 坐席设备能力（哪些机器系统级录音不支持→实时 AI 不可用） */}
            <Route path="/admin/agent-devices" element={<AdminAgentDevicesPage />} />
            {/* Admin - Service Provider Cooperation (Sprint 8.1) */}
            <Route path="/admin/providers" element={<AdminProvidersPage />} />
            <Route path="/admin/providers/:id" element={<AdminProviderDetailPage />} />
            {/* Admin - Data Reports (Sprint 8.3) */}
            <Route path="/admin/reports" element={<AdminReportsPage />} />
            {/* Admin - Compliance Monthly Report (Sprint 8.4) */}
            <Route path="/admin/compliance" element={<ComplianceListPage />} />
            <Route path="/admin/compliance/:yearMonth" element={<ComplianceDetailPage />} />
            {/* Sprint 16.1 — Legal conversion channel (PRD §20.4) */}
            <Route path="/admin/legal-conversion" element={<AdminLegalConversionListPage />} />
            <Route path="/admin/legal-conversion/:id" element={<AdminLegalConversionDetailPage />} />
            {/* v1.6.8 — 法务转化两步审批 inbox（supervisor + admin 共用同一组件，后端按 role 过滤）*/}
            <Route path="/supervisor/legal-conversion-approvals" element={<SupervisorLegalConversionApprovalsPage />} />
            <Route path="/admin/legal-conversion-approvals" element={<SupervisorLegalConversionApprovalsPage />} />
            {/* Admin - System Settings (Sprint 8.5) */}
            <Route path="/admin/settings" element={<AdminSettingsPage />} />
            {/* Supervisor - Script Labels */}
            <Route path="/supervisor/script-labels" element={<SupervisorScriptLabelsPage />} />
            {/* v1.5 — Supervisor projects 落地页 */}
            <Route path="/supervisor/projects" element={<SupervisorProjectsPage />} />
            {/* Supervisor - Reviews */}
            <Route path="/supervisor/reviews" element={<SupervisorReviewsPage />} />
            <Route path="/supervisor/reviews/:call_id" element={<SupervisorReviewDetailPage />} />
            {/* Sprint 9.4 / 9.5 */}
            <Route path="/supervisor/live-wall" element={<SupervisorLiveWallPage />} />
            <Route path="/supervisor/risk-events" element={<SupervisorRiskEventsPage />} />
            <Route path="/supervisor/team-performance" element={<SupervisorTeamPerformancePage />} />
            <Route path="/supervisor/workspace" element={<SupervisorWorkspacePage />} />
            <Route path="/supervisor/escalated" element={<SupervisorEscalatedPage />} />
            <Route path="/supervisor/stats" element={<SupervisorStatsPage />} />
            <Route path="/supervisor/cases" element={<SupervisorCasesPage />} />
            <Route path="/supervisor/cases/:id" element={<SupervisorCaseDetailPage />} />
            <Route path="/supervisor/my-kpi" element={<SupervisorMyKpiPage />} />
            <Route path="/supervisor/promises" element={<SupervisorPromisesPage />} />
            <Route path="/supervisor/case-alerts" element={<SupervisorCaseAlertsPage />} />
            <Route path="/supervisor/shifts" element={<SupervisorShiftsPage />} />
            <Route path="/supervisor/training" element={<SupervisorTrainingPage />} />
            {/* Sprint 10 ops + super */}
            <Route path="/ops/settlements" element={<OpsSettlementsOverviewPage />} />
            {/* Sprint 16.2 — Law firm pool + legal workstation (PRD §20.4) */}
            <Route path="/ops/law-firms" element={<OpsLawFirmsPage />} />
            <Route path="/ops/legal-packages" element={<OpsLegalPackagesPage />} />
            <Route path="/ops/legal-workstation" element={<OpsLegalWorkstationPage />} />
            <Route path="/ops/announcements" element={<OpsAnnouncementsPage />} />
            <Route path="/ops/audit-logs" element={<OpsMyAuditLogsPage />} />
            <Route path="/super/llm-prompts" element={<SuperLlmPromptsPage />} />
            <Route path="/super/blockchain-config" element={<SuperBlockchainConfigPage />} />
            <Route path="/super/sms-config" element={<SuperSmsConfigPage />} />
            <Route path="/ops/customer-followups" element={<OpsCustomerFollowupsPage />} />
            <Route path="/provider/team-performance" element={<ProviderTeamPerformancePage />} />
            <Route path="/provider/team/:user_id/commission" element={<ProviderMemberCommissionPage />} />
            {/* Legal - Cases */}
            <Route path="/legal/cases" element={<LegalCaseListPage />} />
            <Route path="/legal/cases/:id" element={<LegalCaseDetailPage />} />
            <Route path="/legal/internal-orders" element={<LegalInternalOrdersPage />} />
            <Route path="/legal/internal-orders/:id" element={<LegalInternalOrderDetailPage />} />
            <Route path="/legal/pending-finalize" element={<LegalPendingFinalizePage />} />
            <Route path="/admin/partner-law-firms" element={<AdminPartnerLawFirmsPage />} />
            <Route path="/admin/internal-letter-templates" element={<AdminInternalLetterTemplatesPage />} />
            {/* v1.5.7 — 法务转化订单三视图 */}
            <Route path="/legal/orders" element={<TenantLegalOrdersPage />} />
            <Route path="/legal/orders/:id" element={<TenantLegalOrderDetailPage />} />
            <Route path="/lawfirm/orders" element={<LawFirmOrdersPage />} />
            <Route path="/lawfirm/orders/:id" element={<LawFirmOrderDetailPage />} />
            <Route path="/lawyer/orders" element={<LawyerOrdersPage />} />
            <Route path="/lawyer/orders/:id" element={<LawyerOrderDetailPage />} />
            {/* v1.5.7 — 协商打折 / 减免审批 */}
            <Route path="/supervisor/discount-approvals" element={<SupervisorDiscountApprovalsPage />} />
            <Route path="/supervisor/discount-approvals/:id" element={<SupervisorDiscountApprovalDetailPage />} />
            <Route path="/admin/discount-approvals" element={<AdminDiscountApprovalsPage />} />
            <Route path="/admin/discount-approvals/:id" element={<AdminDiscountApprovalDetailPage />} />
            {/* Workorder - Orders */}
            <Route path="/workorder/orders" element={<WorkOrderListPage />} />
            <Route path="/workorder/orders/new" element={<WorkOrderNewPage />} />
            <Route path="/workorder/orders/:id" element={<WorkOrderDetailPage />} />
            {/* Project Manager - Dashboard */}
            <Route path="/pm/dashboard" element={<PMDashboardPage />} />
            {/* Provider Admin — Service Provider Workstation (Sprint 14) */}
            <Route path="/provider/dashboard" element={<ProviderDashboardPage />} />
            <Route path="/provider/tenants" element={<ProviderTenantsPage />} />
            <Route path="/provider/team" element={<ProviderTeamPage />} />
            <Route path="/provider/scripts" element={<ProviderScriptListPage />} />
            <Route path="/provider/settlements" element={<ProviderSettlementListPage />} />
            <Route path="/provider/settlements/:id" element={<ProviderSettlementDetailPage />} />
            <Route path="/provider/historical-reports" element={<ProviderHistoricalReportsPage />} />
            <Route path="/provider/projects" element={<ProviderProjectsPage />} />
            {/* §9 — 服务商法务 (provider legal) */}
            <Route path="/provider/legal/cases" element={<ProviderLegalCasesPage />} />
            <Route path="/provider/legal/cases/:id" element={<ProviderLegalCaseDetailPage />} />
            <Route path="/provider/legal/requests" element={<ProviderLegalRequestsPage />} />
            <Route path="/provider/legal/requests/:id" element={<ProviderLegalRequestDetailPage />} />
            {/* Sprint 15 — superadmin system management */}
            <Route path="/super/health" element={<SuperHealthPage />} />
            <Route path="/super/audit" element={<SuperAuditPage />} />
            <Route path="/super/cost" element={<SuperCostPage />} />
            <Route path="/super/plans" element={<SuperPlansPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
