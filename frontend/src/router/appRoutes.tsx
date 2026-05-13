// v2.0 Task 3 — /app/* 移动路由集中注册
// 在 App.tsx 顶层挂为 <Route path="/app/*" element={<AppMobileRoutes />} />
// 不走 PC 的 AppLayout（不显示侧边栏 / 顶栏）。
import { Navigate, Route, Routes } from "react-router-dom";
import MobileLayout from "../pages/app/_layout";
import MobileHomePage from "../pages/app/home";
import MobileProfilePage from "../pages/app/profile";

export function AppMobileRoutes() {
  return (
    <Routes>
      <Route element={<MobileLayout />}>
        <Route index element={<Navigate to="home" replace />} />
        <Route path="home" element={<MobileHomePage />} />
        <Route path="profile" element={<MobileProfilePage />} />
        {/* TODO Task 4: cases / cases/:id / call-history */}
        <Route path="*" element={<Navigate to="home" replace />} />
      </Route>
    </Routes>
  );
}

export default AppMobileRoutes;
