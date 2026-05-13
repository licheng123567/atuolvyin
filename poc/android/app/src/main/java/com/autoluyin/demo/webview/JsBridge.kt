package com.autoluyin.demo.webview

import android.content.Context
import android.util.Log
import android.webkit.JavascriptInterface
import com.autoluyin.demo.AppConfig

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
        Log.i(tag, "notifyAuthError() — TODO Task 8 ForceLogoutDialog")
    }
}
