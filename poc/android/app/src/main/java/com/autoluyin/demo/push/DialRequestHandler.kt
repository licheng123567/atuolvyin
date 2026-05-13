package com.autoluyin.demo.push

import android.content.Context
import android.content.Intent
import android.util.Log
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.PushRegPatchRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

object DialRequestHandler {

    // Extra key constants — mirrors RealtimeCallActivity.EXTRA_* to avoid circular dependency
    private const val EXTRA_CALL_ID = "call_id"
    private const val EXTRA_CASE_ID = "case_id"
    private const val EXTRA_OWNER_NAME = "owner_name"
    private const val EXTRA_OWNER_PHONE_MASKED = "owner_phone_masked"
    private const val REALTIME_ACTIVITY_CLASS = "com.autoluyin.demo.realtime.RealtimeCallActivity"

    fun handle(ctx: Context, payload: JSONObject) {
        val callId = payload.optLong("call_id", -1L).takeIf { it > 0 } ?: return
        val caseId = payload.optLong("case_id", -1L).takeIf { it > 0 } ?: return
        val ownerName = payload.optString("owner_name", "")
        val ownerPhoneMasked = payload.optString("owner_phone_masked", "")

        val activityClass = try {
            Class.forName(REALTIME_ACTIVITY_CLASS)
        } catch (_: ClassNotFoundException) { return }

        val intent = Intent(ctx, activityClass).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(EXTRA_CALL_ID, callId)
            putExtra(EXTRA_CASE_ID, caseId)
            putExtra(EXTRA_OWNER_NAME, ownerName)
            putExtra(EXTRA_OWNER_PHONE_MASKED, ownerPhoneMasked)
        }
        ctx.startActivity(intent)
    }

    /**
     * v1.6 — push 通道 reg id 上报，仅 patch push_reg_id/push_provider，
     * 不再走 register 主路径：避免 push 回调在用户未登录时（无 device row）
     * 自动创建设备绑定，或在跨账号设备上覆盖 brand/model 等字段。
     *
     * device row 的创建由 MainActivity 登录后的 ensureDeviceRegistered() 负责。
     * 后端在 device 不存在时返回 404 ERR_DEVICE_NOT_REGISTERED；这里仅 log，
     * 等下次 self-check 触发主注册后 push 会被重新上报（MiPush 会重发 regId）。
     */
    fun uploadRegId(ctx: Context, regId: String) {
        val token = AppConfig.token(ctx) ?: return
        val deviceId = AppConfig.deviceId(ctx) ?: return
        ApiClient.appContext = ctx.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                ApiClient.service.patchPushReg(
                    authHeader = "Bearer $token",
                    body = PushRegPatchRequest(
                        device_id = deviceId,
                        push_reg_id = regId,
                        push_provider = "xiaomi",
                    ),
                )
            }.onFailure {
                Log.w("DialRequestHandler", "patchPushReg failed (will retry on next regId): ${it.message}")
            }
        }
    }
}
