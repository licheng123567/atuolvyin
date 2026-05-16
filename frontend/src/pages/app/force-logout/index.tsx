// v2.4 Module C3 — 强制登出页 /app/force-logout
// 1:1 对齐 ui/app-agent.html#app-force-logout
//
// 触发场景：账号在另一台设备登录 → 后端 401 → fetch interceptor 检测到
//   → navigate("/app/force-logout")。当前 React 没有全局 401 拦截器；
//   这里先把页面做出来，保证 deeplink 进入时显示一致。
//   后续可在 refine-mobile-stub useFetcher 里加 401 → navigate hook。

import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { LockKeyhole } from "lucide-react"
import { Bridge } from "../../../lib/jsBridge"

const TOKEN_KEY = "autoluyin_token"
const USER_KEY = "autoluyin_user"

export function MobileForceLogoutPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [busy, setBusy] = useState(false)

  // 可选 query：?ts=14:35&device=Android%20%E5%B0%8F%E7%B1%B312
  const ts = params.get("ts") ?? ""
  const device = params.get("device") ?? "其他设备"

  const relogin = () => {
    setBusy(true)
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    } catch {
      /* localStorage 可能在 WebView 禁用 */
    }
    Bridge.notifyAuthError()
    // v2.4 — 退 fullscreen overlay 让 native 走 ForceLogoutActivity 标准流程
    if (Bridge.isAndroid()) {
      Bridge.exitOverlay()
    } else {
      navigate("/login", { replace: true })
    }
  }

  return (
    <div className="force-logout-screen">
      <div className="force-logout-icon-wrap">
        <LockKeyhole size={40} strokeWidth={1.5} />
      </div>
      <div className="force-logout-title">账号已在其他设备登录</div>
      <div className="force-logout-desc">
        您的账号
        {ts && ` 于 ${ts} `}
        在 {device} 上登录，
        <br />
        本设备已自动退出。
      </div>
      <div className="force-logout-time">
        如非您本人操作，请立即修改密码以保护账号安全。
      </div>
      <button
        type="button"
        className="force-logout-relogin"
        onClick={relogin}
        disabled={busy}
      >
        {busy ? "..." : "重新登录"}
      </button>
      <button type="button" className="force-logout-contact" onClick={relogin}>
        联系管理员
      </button>
    </div>
  )
}

export default MobileForceLogoutPage
