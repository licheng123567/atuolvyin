package com.autoluyin.demo.push

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.autoluyin.demo.AppConfig
import org.json.JSONObject

/**
 * MiPush message receiver stub.
 *
 * TODO: Sprint 4 MiPush — replace this stub with the real PushMessageReceiver subclass
 * once the MiPushClient AAR is provisioned from the Xiaomi developer console.
 * When the AAR is available:
 *   1. Change superclass to com.xiaomi.mipush.sdk.PushMessageReceiver
 *   2. Uncomment the MiPushClient import and COMMAND_REGISTER check in onCommandResult
 *   3. Remove this BroadcastReceiver stub
 */
class MiPushService : BroadcastReceiver() {

    override fun onReceive(ctx: Context, intent: Intent) {
        // Stub — real MiPush callbacks come via PushMessageReceiver overrides.
        // This BroadcastReceiver registers the intent-filters in the Manifest
        // so the app slot is reserved for when the AAR is added.
        val content = intent.getStringExtra("content") ?: return
        handleIncoming(ctx, content)
    }

    private fun handleIncoming(ctx: Context, content: String) {
        if (content.isBlank()) return
        val payload = try { JSONObject(content) } catch (_: Exception) { return }
        if (payload.optString("type") == "DIAL_REQUEST") {
            DialRequestHandler.handle(ctx, payload)
        }
    }

    // ── Called by real PushMessageReceiver.onCommandResult when AAR is present ──

    fun onRegisterSuccess(ctx: Context, regId: String) {
        AppConfig.savePushRegId(ctx, regId)
        DialRequestHandler.uploadRegId(ctx, regId)
    }
}
