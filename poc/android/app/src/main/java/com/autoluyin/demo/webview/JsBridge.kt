package com.autoluyin.demo.webview

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.JavascriptInterface
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.CallWatcherService
import com.autoluyin.demo.auth.AppEventBus
import com.autoluyin.demo.auth.AuthEventBus
import com.autoluyin.demo.webview.WebNavigationBus
import org.json.JSONObject

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

    /**
     * v0.5.2 — React 登录成功后把 JWT 推给 native（让 CallWatcherService /
     * ApiClient 等原生组件也能拿到 token）。
     * 这是统一登录到 React WebView 路径的关键 — Compose AlertDialog 登录被废弃。
     */
    @JavascriptInterface
    fun saveJwt(token: String) {
        Log.i(tag, "saveJwt(...${token.takeLast(8)}) called from WebView")
        if (token.isBlank()) {
            AppConfig.clearJwtToken(ctx)
        } else {
            AppConfig.saveJwtToken(ctx, token)
        }
        com.autoluyin.demo.ApiClient.invalidate()
    }

    @JavascriptInterface
    fun getBackendUrl(): String = AppConfig.backendUrl(ctx).orEmpty()

    /**
     * v2.1 Task 6 — 暴露设备录音能力给 WebView。
     *
     * 返回 JSON string：{capability, guidance, rom, checkedAtMs}
     *   - capability: "realtime" / "post_upload" / "incompatible" / "unknown"
     *   - guidance:   人类可读的提示（来自 DeviceCapabilityProbe）
     *   - rom:        设备识别 (e.g. "MIUI 14 (Android 13)")
     *   - checkedAtMs: 上次检测时间 epoch ms；0 表示从未检测
     */
    @JavascriptInterface
    fun getCapability(): String {
        val state = AppConfig.getCapability(ctx)
        val json = JSONObject()
        json.put("capability", state?.capability ?: "unknown")
        json.put("guidance", state?.guidance ?: "")
        json.put("rom", state?.rom ?: "")
        json.put("checkedAtMs", state?.checkedAtMs ?: 0L)
        return json.toString()
    }

    /**
     * v2.3.1 — 真实拨号实现（之前是 TODO stub，所以 WebView 拨号无反应）。
     * 流程：
     *   1. 解析 {case_id, phone, owner_name}
     *   2. 校验：phone 非空且不含 '*'（masked 号码不能拨）+ CALL_PHONE 权限
     *   3. 启动 CallWatcherService（后台监听挂机 → 触发录音扫描 + 上传）
     *   4. startActivity ACTION_CALL — 系统直接拨号
     * 注意：JS 调用线程 ≠ 主线程，startActivity 必须 post 回主线程。
     */
    @JavascriptInterface
    fun dialCase(caseIdJson: String) {
        Log.i(tag, "dialCase($caseIdJson)")
        val (caseId, phone) = try {
            val obj = JSONObject(caseIdJson)
            obj.getLong("case_id") to obj.getString("phone")
        } catch (t: Throwable) {
            Log.e(tag, "dialCase: bad payload: ${t.message}")
            mainThreadToast("拨号参数解析失败")
            return
        }
        if (phone.isBlank() || phone.contains('*')) {
            mainThreadToast("拨号号码无效（需完整号码，无法处理脱敏 $phone）")
            return
        }
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            mainThreadToast("尚未授予「拨打电话」权限，请到设置授权后重试")
            return
        }
        Handler(Looper.getMainLooper()).post {
            runCatching {
                CallWatcherService.start(ctx, caseId, phone)
            }.onFailure { Log.w(tag, "CallWatcherService.start failed: ${it.message}") }
            val callIntent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone"))
            callIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            runCatching { ctx.startActivity(callIntent) }
                .onFailure {
                    Log.e(tag, "ACTION_CALL failed: ${it.message}")
                    mainThreadToast("拨号失败：${it.message}")
                }
        }
    }

    private fun mainThreadToast(msg: String) {
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(ctx, msg, Toast.LENGTH_SHORT).show()
        }
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

    /**
     * v2.3 Module 2 — 让 Profile 页打开 SAF 文件夹选择器修改录音文件夹。
     * 实际 launch 在 HomeActivity（必须由 ComponentActivity 持有 ActivityResultLauncher）。
     */
    @JavascriptInterface
    fun openRecordingDirPicker() {
        Log.i(tag, "openRecordingDirPicker() requested from WebView")
        AppEventBus.fireOpenRecordingDirPicker()
    }

    /**
     * v2.3 Module 2 — 返回当前持久化的录音文件夹 URI（content://...）。
     * 前端把它转成 friendly path 显示。空串表示未设置。
     */
    @JavascriptInterface
    fun getRecordingDirUri(): String = AppConfig.getUserRecordingDirUri(ctx).orEmpty()

    /**
     * v0.5.2 — 让 Profile 页拿到根据当前 ROM 推荐的候选录音目录的 friendly path（首条）。
     * UI 用它告诉用户「常见目录」是什么，引导更准。空串表示扫描器没命中候选。
     */
    @JavascriptInterface
    fun getSuggestedRecordingDir(): String {
        val scan = com.autoluyin.demo.RecordingScanner.listDirsExistingDetailed(ctx)
        // 命中的目录：直接返回第一个
        scan.existingDirs.firstOrNull()?.let { return it }
        // 未命中但有权限：返回此 ROM 最可能的候选（取候选列表第一个，至少给个起点）
        if (scan.permissionGranted) {
            return AppConfig.runtime.candidateDirs.firstOrNull().orEmpty()
        }
        return ""
    }

    /**
     * v2.4 Module D — React in-call 红色挂断按钮点击。
     *
     * 真机现实（Android 6 / MIUI 10 目标平台）：
     *   - TelecomManager.endCall 是 API 28 引入；本目标低于此版本，直接 no-op
     *   - 反射 TelephonyManager.endCall 需 MODIFY_PHONE_STATE（system signature）
     *   - 高 API 设备（28+）可尝试 endCall，但对应 ANSWER_PHONE_CALLS 危险权限
     *
     * 兜底策略：无论 native 是否成功结束通话，都通知 React 跳到 /app/call-end/{id}
     * 让坐席至少能完成标记。真实挂断由用户在系统拨号 UI 按红键完成；
     * PhoneStateReceiver 仍会捕到 IDLE 并触发 CallWatcherService 上传 + 二次跳 call-end
     * （重复跳同 URL 是幂等的）。
     */
    @JavascriptInterface
    fun endCall(callId: Long) {
        Log.i(tag, "endCall(call=$callId)")
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            try {
                if (ContextCompat.checkSelfPermission(
                        ctx,
                        Manifest.permission.ANSWER_PHONE_CALLS,
                    ) == PackageManager.PERMISSION_GRANTED
                ) {
                    val tm = ctx.getSystemService(android.telecom.TelecomManager::class.java)
                    @Suppress("MissingPermission")
                    tm?.endCall()
                    Log.i(tag, "endCall: TelecomManager.endCall() invoked")
                } else {
                    Log.i(tag, "endCall: ANSWER_PHONE_CALLS not granted, skip native end")
                }
            } catch (t: Throwable) {
                Log.w(tag, "endCall failed: ${t.message}")
            }
        } else {
            Log.i(tag, "endCall: API ${android.os.Build.VERSION.SDK_INT} < 28, no programmatic end; please hang up via system dialer")
        }
        // 无论 native 是否成功结束通话，都让 React 切到 call-end 标记页
        if (callId > 0) {
            WebNavigationBus.navigateTo("/app/call-end/$callId")
        }
    }

    /**
     * v2.4 — React /app/call-end 提交完成或跳过后，通知 native 关闭 fullscreen overlay
     * 回到 4-tab 主屏。/app/in-call、/app/force-logout 也可调用。
     */
    @JavascriptInterface
    fun exitOverlay() {
        Log.i(tag, "exitOverlay() — closing fullscreen WebView overlay")
        WebNavigationBus.exitOverlay()
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
