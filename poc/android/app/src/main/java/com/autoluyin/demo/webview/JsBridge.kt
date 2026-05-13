package com.autoluyin.demo.webview

import android.content.Context
import android.util.Log
import android.webkit.JavascriptInterface
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.auth.AuthEventBus

/**
 * v2.0 Task 2 — WebView ↔ Native 桥接器骨架。
 *
 * 6 个方法都是 stub / 日志，待 Task 3-8 实装：
 *   - getJwt / getBackendUrl: Task 2 已可用（前端鉴权 & API base URL 查询）
 *   - dialCase:        Task 5 — 解析 JSON {case_id, phone, owner_name} → ApiClient.dialStart → ACTION_CALL
 *   - scanQr:          后续接入 — 直接 startActivity QrScanActivity（已存在）
 *   - openCaseDetail:  Task 4 — push 一个新 WebView 路由到 /app/cases/:id
 *   - notifyAuthError: Task 8 — 弹 ForceLogoutDialog 清 token 回登录页
 *
 * 命名约定：JavaScript 侧通过 `window.AndroidBridge.foo()` 调用。
 */
class JsBridge(private val ctx: Context) {

    private val tag = "JsBridge"

    @JavascriptInterface
    fun getJwt(): String = AppConfig.jwtToken(ctx).orEmpty()

    @JavascriptInterface
    fun getBackendUrl(): String = AppConfig.backendUrl(ctx).orEmpty()

    @JavascriptInterface
    fun dialCase(caseIdJson: String) {
        Log.i(tag, "dialCase($caseIdJson) — TODO Task 5")
        // Task 5 实现：解析 JSON {case_id, phone, owner_name} → 调 ApiClient.dialStart → ACTION_CALL
    }

    @JavascriptInterface
    fun scanQr() {
        Log.i(tag, "scanQr() — TODO 后续接入 QrScanActivity")
        // ctx.startActivity(Intent(ctx, com.autoluyin.demo.scan.QrScanActivity::class.java))
    }

    @JavascriptInterface
    fun openCaseDetail(caseId: Long) {
        Log.i(tag, "openCaseDetail($caseId) — TODO Task 4 push WebView")
    }

    @JavascriptInterface
    fun notifyAuthError() {
        // v2.0 Task 8 — 前端 fetch 收到 401 时调用本桥。
        // 前端无法精确区分 ERR_SESSION_EVICTED / ERR_INVALID_TOKEN / ERR_TOKEN_EXPIRED，
        // 默认按"会话被踢出"处理（最近最常见原因；用户即便看到也合理）。
        Log.w(tag, "notifyAuthError() called from WebView — firing force logout")
        AuthEventBus.fireForceLogout(
            code = "ERR_SESSION_EVICTED",
            message = "您的账号已在其他设备登录或登录已失效",
        )
    }
}
