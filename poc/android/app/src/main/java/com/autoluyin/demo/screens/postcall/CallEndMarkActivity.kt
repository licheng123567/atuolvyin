package com.autoluyin.demo.screens.postcall

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.ui.theme.AppTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * v2.0 Task 7 — Screen 4 通话结束标记 (全屏 Compose Activity)。
 *
 * 入口：[com.autoluyin.demo.realtime.RealtimeCallActivity] 在 hangUp / tagPayload
 *      就绪时 startActivity(this) + finish 自身。
 *
 * 与旧 [com.autoluyin.demo.realtime.PostCallTagDialog] 的差异：
 *  - 由 DialogFragment 升级为全屏 Activity；视觉对齐 ui/app-agent.html Screen 4
 *  - AI 字段 (intent / promise_date / promise_amount / summary) 由 extras 预填
 *  - 提交后 Toast 反馈成功/失败；失败不静默 finish，给用户重试机会
 *
 * 关键约束：
 *  - 沉浸式：WindowCompat.setDecorFitsSystemWindows(window, false)
 *  - 旧 PostCallTagDialog 文件不删（过渡期 fallback）
 */
class CallEndMarkActivity : ComponentActivity() {

    companion object {
        const val EXTRA_CALL_ID = "call_id"
        const val EXTRA_OWNER_NAME = "owner_name"
        const val EXTRA_DURATION_SEC = "duration_sec"
        const val EXTRA_STARTED_AT_MS = "started_at_ms"
        const val EXTRA_AI_INTENT = "ai_intent"
        const val EXTRA_AI_PROMISE_DATE = "ai_promise_date"
        const val EXTRA_AI_PROMISE_AMOUNT = "ai_promise_amount"
        const val EXTRA_AI_SUMMARY = "ai_summary"
    }

    private var callId: Long = -1L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        ApiClient.appContext = applicationContext

        callId = intent.getLongExtra(EXTRA_CALL_ID, -1L)
        if (callId <= 0L) {
            finish()
            return
        }
        val ownerName = intent.getStringExtra(EXTRA_OWNER_NAME) ?: "未知业主"
        val durationSec = intent.getIntExtra(EXTRA_DURATION_SEC, 0)
        val startedAtMs = intent.getLongExtra(EXTRA_STARTED_AT_MS, 0L)
        val aiIntent = intent.getStringExtra(EXTRA_AI_INTENT)
        val aiPromiseDate = intent.getStringExtra(EXTRA_AI_PROMISE_DATE)
        val aiPromiseAmount: Double? = if (intent.hasExtra(EXTRA_AI_PROMISE_AMOUNT)) {
            intent.getDoubleExtra(EXTRA_AI_PROMISE_AMOUNT, 0.0)
        } else {
            null
        }
        val aiSummary = intent.getStringExtra(EXTRA_AI_SUMMARY)

        setContent {
            AppTheme {
                CallEndMarkScreen(
                    callId = callId,
                    ownerName = ownerName,
                    durationSec = durationSec,
                    startedAtMs = startedAtMs,
                    aiIntent = aiIntent,
                    aiPromiseDate = aiPromiseDate,
                    aiPromiseAmount = aiPromiseAmount,
                    aiSummary = aiSummary,
                    onSubmit = ::submit,
                    onSkip = { finish() },
                )
            }
        }
    }

    private fun submit(payload: SubmitPayload) {
        val token = AppConfig.token(this)
        if (token == null) {
            Toast.makeText(this, "未登录，无法提交标签", Toast.LENGTH_LONG).show()
            return
        }
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val body = buildMap<String, Any> {
                        put("intent", payload.intent)
                        payload.promiseDate?.let { put("promise_date", it) }
                        payload.promiseAmount?.let { put("promise_amount", it) }
                        payload.notes?.let { put("notes", it) }
                    }
                    val resp = ApiClient.service.patchCallTag(
                        authHeader = "Bearer $token",
                        callId = callId,
                        body = body,
                    )
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code()}")
                    }
                }
            }
            if (result.isSuccess) {
                Toast.makeText(this@CallEndMarkActivity, "已提交", Toast.LENGTH_SHORT).show()
                finish()
            } else {
                val msg = result.exceptionOrNull()?.message ?: "未知错误"
                Toast.makeText(
                    this@CallEndMarkActivity,
                    "提交失败：$msg",
                    Toast.LENGTH_LONG,
                ).show()
            }
        }
    }
}

/**
 * 通话结束标记提交参数（Screen 内部聚合后传给 Activity）。
 *
 * @property intent 通话结果标签 key（promise_pay / refuse / workorder / followup / no_answer）
 * @property promiseDate ISO 日期字符串（仅 intent == promise_pay 时非 null）
 * @property promiseAmount AI 预填的承诺金额（UI 暂不收集，原样回传）
 * @property notes 跟进备注（可选）
 */
data class SubmitPayload(
    val intent: String,
    val promiseDate: String?,
    val promiseAmount: Double?,
    val notes: String?,
)
