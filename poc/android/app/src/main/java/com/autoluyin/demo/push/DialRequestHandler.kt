package com.autoluyin.demo.push

import android.content.Context
import android.content.Intent
import android.util.Log
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.PushRegPatchRequest
import com.autoluyin.demo.screens.dial.DialRequestPayload
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

object DialRequestHandler {

    /**
     * v2.0 Task 5 — 改为路由到 DialRequestActivity（Screen 2 全屏蓝渐变请求页）。
     *
     * 之前直接拉 RealtimeCallActivity 的旧路径已被替换；通话中页面将由
     * DialRequestActivity → ACTION_CALL → PhoneStateReceiver/CallWatcher 接管。
     *
     * Activity 类名用反射加载，避免 push 模块编译期硬依赖 screens/ 模块；
     * 即便后续把 screens/ 抽成子模块也不破坏。
     */
    private const val DIAL_REQUEST_ACTIVITY_CLASS =
        "com.autoluyin.demo.screens.dial.DialRequestActivity"

    fun handle(ctx: Context, payload: JSONObject) {
        val callId = payload.optLong("call_id", -1L).takeIf { it > 0 } ?: return
        val caseId = payload.optLong("case_id", -1L).takeIf { it > 0 } ?: return

        val ownerName = payload.optString("owner_name", "")
        val ownerPhoneMasked = payload.optString("owner_phone_masked", "")
        // owner_phone：明文（agent 角色有权看），后端待补；不存在时取 null
        val ownerPhone = payload.optString("owner_phone").takeIf { it.isNotBlank() }
        val building = payload.optString("building").takeIf { it.isNotBlank() }
        val room = payload.optString("room").takeIf { it.isNotBlank() }
        val amountOwed = payload.optString("amount_owed").takeIf { it.isNotBlank() }
        val monthsOverdue = payload.optInt("months_overdue", -1).takeIf { it > 0 }
        val lastContactAt = payload.optString("last_contact_at").takeIf { it.isNotBlank() }
        val lastOutcome = payload.optString("last_outcome").takeIf { it.isNotBlank() }
        val expiresAt = payload.optString("expires_at").takeIf { it.isNotBlank() }

        val activityClass = try {
            Class.forName(DIAL_REQUEST_ACTIVITY_CLASS)
        } catch (e: ClassNotFoundException) {
            Log.e("DialRequestHandler", "DialRequestActivity not found on classpath", e)
            return
        }

        val intent = Intent(ctx, activityClass).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(DialRequestPayload.EXTRA_CALL_ID, callId)
            putExtra(DialRequestPayload.EXTRA_CASE_ID, caseId)
            putExtra(DialRequestPayload.EXTRA_OWNER_NAME, ownerName)
            putExtra(DialRequestPayload.EXTRA_OWNER_PHONE_MASKED, ownerPhoneMasked)
            ownerPhone?.let { putExtra(DialRequestPayload.EXTRA_OWNER_PHONE, it) }
            building?.let { putExtra(DialRequestPayload.EXTRA_BUILDING, it) }
            room?.let { putExtra(DialRequestPayload.EXTRA_ROOM, it) }
            amountOwed?.let { putExtra(DialRequestPayload.EXTRA_AMOUNT_OWED, it) }
            monthsOverdue?.let { putExtra(DialRequestPayload.EXTRA_MONTHS_OVERDUE, it) }
            lastContactAt?.let { putExtra(DialRequestPayload.EXTRA_LAST_CONTACT_AT, it) }
            lastOutcome?.let { putExtra(DialRequestPayload.EXTRA_LAST_OUTCOME, it) }
            expiresAt?.let { putExtra(DialRequestPayload.EXTRA_EXPIRES_AT, it) }
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
