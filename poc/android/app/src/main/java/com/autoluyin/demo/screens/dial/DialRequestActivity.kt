package com.autoluyin.demo.screens.dial

import android.app.KeyguardManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.ui.theme.AppTheme

/**
 * v2.0 Task 5 — Screen 2 拨号请求 Activity（push 触发）。
 *
 * 入口：
 *  - DialRequestHandler.handle(ctx, payload) → startActivity(this)
 *  - extras 走 [DialRequestPayload.fromIntent] 解析；缺 call_id/case_id 直接 finish。
 *
 * 锁屏唤起策略（避免 onCreate 太早卡 Compose）：
 *  - API 26+：setShowWhenLocked / setTurnScreenOn / requestDismissKeyguard
 *  - API < 26：FLAG_SHOW_WHEN_LOCKED | FLAG_TURN_SCREEN_ON | FLAG_KEEP_SCREEN_ON
 *
 * 沉浸式：
 *  - WindowCompat.setDecorFitsSystemWindows(window, false) 让蓝渐变铺满 status bar；
 *    Compose 内用 systemBarsPadding() 避让。
 *
 * 不在此 Activity 内调 dial-start API：
 *  - push 来的请求 call_id 已经存在；用户点"立即拨打"直接 ACTION_CALL 即可。
 *  - dial-start 是 PC 主控时才需要（Sprint 13.x），由后端在创建 push 前完成。
 */
class DialRequestActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // ---- 锁屏唤起 ----
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            getSystemService(KeyguardManager::class.java)
                ?.requestDismissKeyguard(this, null)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
            )
        }

        // ---- 沉浸式（蓝渐变贴到 status bar）----
        WindowCompat.setDecorFitsSystemWindows(window, false)

        // ---- ApiClient context（后续 dial-info / defer 调用需要） ----
        ApiClient.appContext = applicationContext

        // ---- 解析 payload ----
        val payload = DialRequestPayload.fromIntent(intent)
        if (payload == null) {
            Log.w(TAG, "missing call_id / case_id in intent extras; finishing")
            finish()
            return
        }

        setContent {
            AppTheme {
                DialRequestScreen(
                    payload = payload,
                    onAccept = ::handleAccept,
                    onDefer = ::handleDefer,
                    onTimeout = ::handleTimeout,
                )
            }
        }
    }

    private fun handleAccept(phoneToDial: String) {
        if (phoneToDial.isBlank()) {
            Log.w(TAG, "phone is blank; cannot dial")
            Toast.makeText(this, "未拿到电话号码，拨号取消", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        // TODO(后端): 当 phoneToDial 是打码格式（含 *）时拨不通；
        //   等 push 补 owner_phone 字段后再做明文/打码区分。
        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$phoneToDial")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        runCatching {
            startActivity(intent)
        }.onFailure { err ->
            Log.e(TAG, "ACTION_CALL failed", err)
            // 没有 CALL_PHONE 权限或厂商拦截会 SecurityException；MainActivity 已申请过权限，
            // 这里不再二次申请，仅提示用户。
            Toast.makeText(
                this,
                "拨号失败，请到系统设置授予拨号权限",
                Toast.LENGTH_LONG,
            ).show()
        }
        finish()
    }

    private fun handleDefer() {
        // TODO(Task 6+): 调后端 defer endpoint 标记延后；当前仅本地 log + finish。
        Log.i(TAG, "user deferred")
        finish()
    }

    private fun handleTimeout() {
        // TODO(Task 6+): 上报 expired 状态以便主管看到"未应答"。
        Log.i(TAG, "auto-cancelled (countdown expired)")
        finish()
    }

    companion object {
        private const val TAG = "DialRequestActivity"
    }
}
