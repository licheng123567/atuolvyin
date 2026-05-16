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
    // v2.2 — onPageStarted 注入 __JWT__ 与 React mount 之间可能有 1-2 帧滞后；
    // 先 poll 300ms 兜底再跳 login（否则 WebView 永远白屏跳 PC login）。
    let cancelled = false;
    const tryAuth = (attempt: number) => {
      if (cancelled) return;
      const jwt = Bridge.getJwt();
      if (jwt) return;
      if (attempt >= 6) {
        navigate("/login", { replace: true });
        return;
      }
      setTimeout(() => tryAuth(attempt + 1), 50);
    };
    tryAuth(0);
    return () => {
      cancelled = true;
    };
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
