// v2.0 Task 3 — 移动壳布局（Android WebView / 手机浏览器调试通用）
// - 全屏 100vh, 无 PC 侧边栏 / 顶栏
// - bottom padding 0：HomeActivity 的 NavigationBar 在 WebView 外渲染
// - MobileAuthGuard：token 缺失时跳 /login（容错）
import { useEffect, type ReactNode } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Bridge } from "../../lib/jsBridge";

interface MobileAuthGuardProps {
  children: ReactNode;
}

function MobileAuthGuard({ children }: MobileAuthGuardProps) {
  const navigate = useNavigate();

  useEffect(() => {
    const jwt = Bridge.getJwt();
    if (!jwt) {
      // WebView 通常此时已被 native 注入 token；只有真正没有时才跳登录
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  return <>{children}</>;
}

export function MobileLayout() {
  return (
    <MobileAuthGuard>
      <div className="mobile-shell mobile-no-select">
        <Outlet />
      </div>
    </MobileAuthGuard>
  );
}

export default MobileLayout;
