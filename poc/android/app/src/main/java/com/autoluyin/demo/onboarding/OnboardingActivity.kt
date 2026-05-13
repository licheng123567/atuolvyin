package com.autoluyin.demo.onboarding

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.MainActivity
import com.autoluyin.demo.ui.theme.AppTheme
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * v2.1 Task 5 — 首次安装 Onboarding Wizard。
 *
 * 4 步全屏 Compose 流程：
 *  1. 权限授予
 *  2. 后端地址
 *  3. 录音设置确认（核心）
 *  4. 准备完成
 *
 * 不在 onboarding 内做：
 *  - 登录（仍在 MainActivity 的 AlertDialog）
 *  - self-check（需要 token，登录后 MainActivity 会触发）
 *
 * 完成 → markOnboardingDone + finish + 跳回 MainActivity（会触发原 preflight：
 * 已配后端 URL → 直接弹 login dialog → self-check）。
 */
class OnboardingActivity : ComponentActivity() {

    private val permissionsResultFlow = MutableSharedFlow<Boolean>(
        replay = 0,
        extraBufferCapacity = 1,
    )

    private val permLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        // 任一权限 deny 也视为继续推进；用户可在系统设置补回。
        // 这里只通知"申请完成"，是否全授予由 Compose 端判定。
        permissionsResultFlow.tryEmit(result.values.all { it })
    }

    fun observePermissionResult(): SharedFlow<Boolean> = permissionsResultFlow.asSharedFlow()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        ApiClient.appContext = applicationContext

        setContent {
            AppTheme {
                OnboardingScreen(
                    permissionsResult = observePermissionResult(),
                    onComplete = ::handleComplete,
                    onRequestPermissions = ::handleRequestPermissions,
                    onOpenSystemSettings = ::handleOpenSystemSettings,
                    onSaveBackendUrl = ::handleSaveBackendUrl,
                    arePermissionsGranted = ::arePermissionsGranted,
                )
            }
        }
    }

    private fun handleRequestPermissions() {
        val needed = mutableListOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            needed += Manifest.permission.READ_MEDIA_AUDIO
            needed += Manifest.permission.POST_NOTIFICATIONS
        } else {
            needed += Manifest.permission.READ_EXTERNAL_STORAGE
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            permissionsResultFlow.tryEmit(true)
        } else {
            permLauncher.launch(missing.toTypedArray())
        }
    }

    private fun arePermissionsGranted(): Boolean {
        val needed = mutableListOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            needed += Manifest.permission.READ_MEDIA_AUDIO
            needed += Manifest.permission.POST_NOTIFICATIONS
        } else {
            needed += Manifest.permission.READ_EXTERNAL_STORAGE
        }
        return needed.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun handleOpenSystemSettings() {
        // 厂商私有"通话设置 → 通话自动录音" intent 不一致（MIUI / EMUI / OneUI 各异），
        // 用通用 Settings.ACTION_SETTINGS 兜底，让用户自己进入对应菜单。
        runCatching {
            startActivity(
                Intent(Settings.ACTION_SETTINGS).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                },
            )
        }
    }

    private fun handleSaveBackendUrl(url: String): Boolean {
        val v = url.trim()
        if (v.isBlank() || !(v.startsWith("http://") || v.startsWith("https://"))) {
            return false
        }
        AppConfig.saveBackendUrl(this, v)
        return true
    }

    private fun handleComplete() {
        AppConfig.markOnboardingDone(this)
        startActivity(
            Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            },
        )
        finish()
    }

    companion object {
        fun start(ctx: Context) {
            ctx.startActivity(
                Intent(ctx, OnboardingActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                },
            )
        }
    }
}
