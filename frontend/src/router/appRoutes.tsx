// v2.0 Task 3 — /app/* 移动路由集中注册
// 在 App.tsx 顶层挂为 <Route path="/app/*" element={<AppMobileRoutes />} />
// 不走 PC 的 AppLayout（不显示侧边栏 / 顶栏）。
import { Navigate, Route, Routes } from "react-router-dom";
import MobileLayout from "../pages/app/_layout";
import MobileHomePage from "../pages/app/home";
import MobileProfilePage from "../pages/app/profile";
import MobileCasesPage from "../pages/app/cases";
import MobileCaseDetailPage from "../pages/app/cases/[id]";
import MobileCallHistoryPage from "../pages/app/call-history";

export function AppMobileRoutes() {
  return (
    <Routes>
      <Route element={<MobileLayout />}>
        <Route index element={<Navigate to="home" replace />} />
        <Route path="home" element={<MobileHomePage />} />
        <Route path="cases" element={<MobileCasesPage />} />
        <Route path="cases/:id" element={<MobileCaseDetailPage />} />
        <Route path="call-history" element={<MobileCallHistoryPage />} />
        <Route path="profile" element={<MobileProfilePage />} />
        <Route path="*" element={<Navigate to="home" replace />} />
      </Route>
    </Routes>
  );
}

export default AppMobileRoutes;
