package com.autoluyin.demo.push

import android.content.Context
import android.content.Intent
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.RegisterDeviceRequest
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

    fun uploadRegId(ctx: Context, regId: String) {
        // Use existing Retrofit client; needs JWT, so only succeeds if user logged in
        val token = AppConfig.token(ctx) ?: return
        val deviceId = AppConfig.deviceId(ctx) ?: return
        // Ensure appContext is initialized before using ApiClient.service
        ApiClient.appContext = ctx.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                ApiClient.service.registerDevice(
                    authHeader = "Bearer $token",
                    body = RegisterDeviceRequest(
                        device_id = deviceId,
                        brand = android.os.Build.BRAND,
                        model = android.os.Build.MODEL,
                        os_version = android.os.Build.VERSION.RELEASE,
                        push_reg_id = regId,
                        push_provider = "xiaomi",
                    ),
                )
            }
        }
    }
}
