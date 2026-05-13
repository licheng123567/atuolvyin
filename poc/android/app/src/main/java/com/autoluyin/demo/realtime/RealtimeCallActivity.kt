package com.autoluyin.demo.realtime

import android.Manifest
import android.app.KeyguardManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.fragment.app.FragmentActivity
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.screens.postcall.CallEndMarkActivity
import com.autoluyin.demo.screens.realtime.RealtimeCallScreen
import com.autoluyin.demo.screens.realtime.RealtimeCallState
import com.autoluyin.demo.screens.realtime.RealtimeCallViewModel
import com.autoluyin.demo.ui.theme.AppTheme
import kotlinx.coroutines.delay
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

/**
 * v2.0 Task 6 — Compose 全屏 Screen 3 (通话中)。
 *
 * 重写要点：
 *  - 改 [androidx.fragment.app.FragmentActivity] 子类（保留 supportFragmentManager 兼容性）
 *  - 不再 setContentView XML；UI 全部由 [RealtimeCallScreen] 渲染
 *  - 状态来自 [RealtimeCallViewModel]，旋转 / 进程恢复保留 transcript
 *  - 锁屏唤起 + 沉浸式与 [com.autoluyin.demo.screens.dial.DialRequestActivity] 一致
 *  - 旧 TranscriptAdapter / SuggestionCardView / RiskBannerView 不再被引用，但保留作过渡
 *  - v2.0 Task 7 起，挂机 / tagPayload 就绪改为 startActivity(CallEndMarkActivity)；
 *    [com.autoluyin.demo.realtime.PostCallTagDialog] 文件保留作过渡，二期清理
 */
class RealtimeCallActivity : FragmentActivity() {

    companion object {
        const val EXTRA_CALL_ID = "call_id"
        const val EXTRA_CASE_ID = "case_id"
        const val EXTRA_OWNER_NAME = "owner_name"
        const val EXTRA_OWNER_PHONE_MASKED = "owner_phone_masked"
        private const val REQ_PERMS = 4711
    }

    private val viewModel: RealtimeCallViewModel by viewModels()

    private var callId: Long = -1L
    private var caseId: Long = -1L
    private var ownerName: String = "未知业主"
    private var ownerPhoneMasked: String = ""

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
        // ---- 沉浸式 ----
        WindowCompat.setDecorFitsSystemWindows(window, false)

        // ---- intent extras ----
        callId = intent.getLongExtra(EXTRA_CALL_ID, -1L)
        caseId = intent.getLongExtra(EXTRA_CASE_ID, -1L)
        if (callId <= 0L || caseId <= 0L) {
            finish()
            return
        }
        ownerName = intent.getStringExtra(EXTRA_OWNER_NAME) ?: "未知业主"
        ownerPhoneMasked = intent.getStringExtra(EXTRA_OWNER_PHONE_MASKED) ?: ""

        ApiClient.appContext = applicationContext
        ensurePermissionsThenStart()

        setContent {
            AppTheme {
                val transcript by viewModel.transcript.collectAsState()
                val suggestion by viewModel.suggestion.collectAsState()
                val connState by viewModel.connectionState.collectAsState()
                val activeRisk by viewModel.activeBannerRisk.collectAsState()
                val blockingRisk by viewModel.blockingRisk.collectAsState()
                val tagPayload by viewModel.tagPayload.collectAsState()

                // ---- 计时器 ----
                var durationSec by remember { mutableIntStateOf(0) }
                LaunchedEffect(Unit) {
                    while (true) {
                        val started = viewModel.startedAt()
                        durationSec = if (started > 0L) {
                            ((System.currentTimeMillis() - started) / 1000L).toInt()
                        } else 0
                        delay(1000L)
                    }
                }

                // ---- tag 全屏 Activity 触发 (v2.0 Task 7) ----
                LaunchedEffect(tagPayload) {
                    val payload = tagPayload ?: return@LaunchedEffect
                    viewModel.consumeTagPayload()
                    launchCallEndMark(payload)
                }

                // ---- toast (RiskAlertController L1 toast) ----
                LaunchedEffect(Unit) {
                    viewModel.toast.collect { msg ->
                        Toast.makeText(this@RealtimeCallActivity, msg, Toast.LENGTH_SHORT).show()
                    }
                }

                RealtimeCallScreen(
                    ownerName = ownerName,
                    ownerPhoneMasked = ownerPhoneMasked,
                    state = RealtimeCallState(
                        transcript = transcript,
                        suggestion = suggestion,
                        connectionState = connState,
                        activeRisk = activeRisk,
                        blockingRisk = blockingRisk,
                        durationSec = durationSec,
                    ),
                    onAdopt = viewModel::adopt,
                    onIgnore = {
                        viewModel.suggestion.value?.first?.let(viewModel::ignore)
                    },
                    onHangup = ::hangUp,
                    onMuteToggle = { /* TODO Task 7+ */ },
                    onAddNote = { /* TODO Task 7+ */ },
                    onSendCode = { /* TODO 后端 send-payment-link endpoint 接入后再实现 */ },
                    onDismissBannerRisk = viewModel::dismissBannerRisk,
                    onDismissBlockingRisk = viewModel::dismissBlockingRisk,
                )
            }
        }
    }

    private fun ensurePermissionsThenStart() {
        val perms = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CALL_PHONE,
        )
        val missing = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            viewModel.start(callId, caseId)
        } else {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), REQ_PERMS)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQ_PERMS) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            viewModel.start(callId, caseId)
        } else {
            finish()
        }
    }

    private fun hangUp() {
        val wav = viewModel.stopAndCollect()
        if (wav != null) {
            uploadFallback(wav)
        }
        // 服务端没下发 tag.ready 时强制弹标记页让用户人工填写 (v2.0 Task 7)
        if (!viewModel.hadServerTag()) {
            launchCallEndMark(AudioStreamClient.TagPayload(null, null, null, null))
        }
    }

    /**
     * v2.0 Task 7 — 启动 [CallEndMarkActivity] 全屏标记页，并 finish 当前通话页。
     * AI 字段 (intent / promise_date / promise_amount / summary) 通过 extras 预填。
     */
    private fun launchCallEndMark(payload: AudioStreamClient.TagPayload) {
        val started = viewModel.startedAt()
        val durationSec = if (started > 0L) {
            ((System.currentTimeMillis() - started) / 1000L).toInt()
        } else {
            0
        }
        val markIntent = Intent(this, CallEndMarkActivity::class.java).apply {
            putExtra(CallEndMarkActivity.EXTRA_CALL_ID, callId)
            putExtra(CallEndMarkActivity.EXTRA_OWNER_NAME, ownerName)
            putExtra(CallEndMarkActivity.EXTRA_DURATION_SEC, durationSec)
            putExtra(CallEndMarkActivity.EXTRA_STARTED_AT_MS, started)
            payload.intent?.let { putExtra(CallEndMarkActivity.EXTRA_AI_INTENT, it) }
            payload.promiseDate?.let { putExtra(CallEndMarkActivity.EXTRA_AI_PROMISE_DATE, it) }
            payload.promiseAmount?.let { putExtra(CallEndMarkActivity.EXTRA_AI_PROMISE_AMOUNT, it) }
            payload.summary?.let { putExtra(CallEndMarkActivity.EXTRA_AI_SUMMARY, it) }
        }
        runCatching { startActivity(markIntent) }
            .onFailure {
                Toast.makeText(this, "无法打开标记页：${it.message}", Toast.LENGTH_LONG).show()
            }
        finish()
    }

    private fun uploadFallback(wav: File) {
        val token = AppConfig.token(this) ?: return
        val deviceId = AppConfig.deviceId(this) ?: return
        val durationSec = ((System.currentTimeMillis() - viewModel.startedAt()) / 1000L).toString()
        // TODO: Sprint 4 cleanup — relax callee_phone/started_at/ended_at for FALLBACK_LOCAL uploads.
        Thread {
            runCatching {
                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("device_id", deviceId)
                    .addFormDataPart("case_id", caseId.toString())
                    .addFormDataPart("callee_phone", "")
                    .addFormDataPart("started_at", "")
                    .addFormDataPart("ended_at", "")
                    .addFormDataPart("duration_sec", durationSec)
                    .addFormDataPart(
                        "file", wav.name,
                        wav.asRequestBody("audio/wav".toMediaTypeOrNull()),
                    )
                    .build()
                val baseUrl = AppConfig.backendUrl(this) ?: return@runCatching
                OkHttpClient().newCall(
                    Request.Builder()
                        .url("$baseUrl/api/v1/calls/upload")
                        .header("Authorization", "Bearer $token")
                        .post(requestBody)
                        .build(),
                ).execute().close()
            }
        }.start()
    }
}
