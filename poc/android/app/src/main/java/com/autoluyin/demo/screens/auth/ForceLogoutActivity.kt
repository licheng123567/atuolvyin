package com.autoluyin.demo.screens.auth

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.MainActivity
import com.autoluyin.demo.auth.AuthEventBus
import com.autoluyin.demo.auth.ForceLogoutReason
import com.autoluyin.demo.ui.theme.AppTheme

/**
 * v2.0 Task 8 — 强制退出 Activity (Screen 9)。
 *
 * 入口：[com.autoluyin.demo.HomeActivity] / 其它前台 Activity 监听 [AuthEventBus.forceLogout]
 *      后通过 [createIntent] + startActivity 跳转。
 *
 * 进入即清账户态：
 *  1. 清 SharedPreferences 中的 JWT
 *  2. 重置 ApiClient（新连接不会再带旧 token）
 *  3. AuthEventBus.reset() 清 replay 缓存（防止后续 Activity 监听到陈旧事件再跳一次）
 *
 * 拦截返回键：避免用户按返回退回到刚因 401 失败的 Activity。
 */
class ForceLogoutActivity : ComponentActivity() {

    companion object {
        const val EXTRA_CODE = "code"
        const val EXTRA_MESSAGE = "message"

        fun createIntent(ctx: Context, reason: ForceLogoutReason): Intent =
            Intent(ctx, ForceLogoutActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                putExtra(EXTRA_CODE, reason.code)
                putExtra(EXTRA_MESSAGE, reason.message)
            }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        val reason = ForceLogoutReason(
            code = intent.getStringExtra(EXTRA_CODE) ?: "UNKNOWN",
            message = intent.getStringExtra(EXTRA_MESSAGE),
        )

        // 进入此页面 = 已确定要登出。先把 token 清掉，避免后续残余请求又触发 401。
        AppConfig.clearJwtToken(this)
        ApiClient.invalidate()
        // 清 replay 缓存：防止屏幕旋转 / Activity 重建时 LaunchedEffect 再次收到事件重复跳转。
        AuthEventBus.reset()

        // 拦截返回键，强制走"重新登录"或保持本页
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // no-op：禁止返回到鉴权失败的源 Activity
            }
        })

        setContent {
            AppTheme {
                ForceLogoutScreen(
                    reason = reason,
                    onRelogin = ::handleRelogin,
                    onContactAdmin = ::handleContactAdmin,
                )
            }
        }
    }

    private fun handleRelogin() {
        // 跳回 MainActivity；其 ensureBackendUrlThen 检测到 jwtToken == null → 自动弹登录 dialog。
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        }
        startActivity(intent)
        finish()
    }

    private fun handleContactAdmin() {
        Toast.makeText(
            this,
            "请联系您的物业管理员（PoC 暂未集成客服入口）",
            Toast.LENGTH_LONG,
        ).show()
    }
}
