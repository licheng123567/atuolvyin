import { Authenticated, Refine } from "@refinedev/core";
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
import { authProvider } from "./providers/auth-provider";
import { dataProvider } from "./providers";

function App() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        routerProvider={routerBindings}
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
                <AppLayout>
                  <Outlet />
                </AppLayout>
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
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
