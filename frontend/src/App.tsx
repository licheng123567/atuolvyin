import { Authenticated, Refine, useGetIdentity } from "@refinedev/core";
import routerBindings from "@refinedev/react-router";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/login";
import { TenantListPage } from "./pages/ops/tenants/index";
import { TenantNewPage } from "./pages/ops/tenants/new";
import { TenantDetailPage } from "./pages/ops/tenants/[id]";
import { UserListPage } from "./pages/admin/users/index";
import { UserNewPage } from "./pages/admin/users/new";
import { CaseListPage } from "./pages/admin/cases/index";
import { CaseImportPage } from "./pages/admin/cases/import";
import { AgentCaseListPage } from "./pages/agent/cases/index";
import { AdminCaseDetailPage } from "./pages/admin/cases/detail";
import { AgentWorkstationPage } from "./pages/agent/cases/detail";
import { CallDetailPage } from "./pages/calls/detail";
import { AgentLiveWorkstationPage } from "./pages/agent/workstation/live";
import { AdminLiveWorkstationPage } from "./pages/admin/workstation/live";
import { ScriptListPage } from "./pages/admin/scripts/list";
import { ScriptVersionsPage } from "./pages/admin/scripts/versions";
import { SupervisorScriptLabelsPage } from "./pages/supervisor/script-labels";
import { authProvider, getToken } from "./providers/auth-provider";
import { dataProvider } from "./providers";
import { useSupervisorAlerts } from "./hooks/useSupervisorAlerts";
import { SupervisorAlertsPage } from "./pages/supervisor/alerts";
import { RiskKeywordListPage } from "./pages/admin/risk-keywords/list";
import { RiskKeywordCreatePage } from "./pages/admin/risk-keywords/create";
import { RiskKeywordEditPage } from "./pages/admin/risk-keywords/edit";
import type { AuthUser } from "./providers/auth-provider";

const SUPERVISOR_ROLES = new Set(["supervisor", "admin", "platform_super"]);

function AuthenticatedShell() {
  const { data: identity } = useGetIdentity<AuthUser>();
  const isSupervisor = SUPERVISOR_ROLES.has(identity?.role ?? "");
  useSupervisorAlerts(isSupervisor ? getToken() : null);
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
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
            name: "supervisor/script-labels",
            list: "/supervisor/script-labels",
            meta: { label: "话术标注" },
          },
        ]}
        options={{ syncWithLocation: true, warnWhenUnsavedChanges: false }}
      >
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

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
            <Route
              path="/"
              element={
                <div className="text-[var(--color-neutral-900)]">
                  <h1 className="text-2xl font-semibold mb-2">
                    欢迎使用有证慧催
                  </h1>
                  <p className="text-sm text-[var(--color-neutral-600)]">
                    各功能模块正在开发中。
                  </p>
                </div>
              }
            />
            {/* Ops - Tenant Management */}
            <Route path="/ops/tenants" element={<TenantListPage />} />
            <Route path="/ops/tenants/new" element={<TenantNewPage />} />
            <Route path="/ops/tenants/:id" element={<TenantDetailPage />} />
            {/* Admin - User Management */}
            <Route path="/admin/users" element={<UserListPage />} />
            <Route path="/admin/users/new" element={<UserNewPage />} />
            {/* Admin - Case Management */}
            <Route path="/admin/cases" element={<CaseListPage />} />
            <Route path="/admin/cases/import" element={<CaseImportPage />} />
            {/* Agent - Case List */}
            <Route path="/agent/cases" element={<AgentCaseListPage />} />
            {/* Admin - Case Detail */}
            <Route path="/admin/cases/:id" element={<AdminCaseDetailPage />} />
            {/* Agent - Case Detail / Workstation */}
            <Route path="/agent/cases/:id" element={<AgentWorkstationPage />} />
            {/* Call Detail */}
            <Route path="/calls/:id" element={<CallDetailPage />} />
            {/* Agent Live Workstation */}
            <Route path="/agent/workstation/:call_id" element={<AgentLiveWorkstationPage />} />
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
            <Route path="/admin/scripts/:id/versions" element={<ScriptVersionsPage />} />
            {/* Supervisor - Script Labels */}
            <Route path="/supervisor/script-labels" element={<SupervisorScriptLabelsPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
