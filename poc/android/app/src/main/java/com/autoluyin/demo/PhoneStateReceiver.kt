package com.autoluyin.demo

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import android.util.Log

/**
 * 静态注册在 manifest，不依赖服务存活。
 * OFFHOOK 时记录开始时间；IDLE 时唤醒服务做扫描上传。
 * 服务通过 SharedPreferences 与此 Receiver 共享状态。
 */
class PhoneStateReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "PhoneStateReceiver"
        const val PREFS = "call_watch_state"
        const val KEY_TASK_ID   = "task_id"
        const val KEY_CALLEE    = "callee"
        const val KEY_STARTED   = "started_at"
        const val KEY_ENDED     = "ended_at"
        const val KEY_OBSERVED  = "observed"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return
        val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE) ?: return
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        Log.d(TAG, "state=$state observed=${prefs.getBoolean(KEY_OBSERVED, false)}")

        when (state) {
            TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                // 只有 CallWatcherService 已经写入 task_id 才处理（避免非任务通话触发）
                if (prefs.getLong(KEY_TASK_ID, 0) > 0 && !prefs.getBoolean(KEY_OBSERVED, false)) {
                    prefs.edit()
                        .putLong(KEY_STARTED, System.currentTimeMillis())
                        .putBoolean(KEY_OBSERVED, true)
                        .apply()
                    Log.i(TAG, "OFFHOOK recorded")
                }
            }
            TelephonyManager.EXTRA_STATE_IDLE -> {
                if (prefs.getBoolean(KEY_OBSERVED, false) && prefs.getLong(KEY_ENDED, 0) == 0L) {
                    prefs.edit()
                        .putLong(KEY_ENDED, System.currentTimeMillis())
                        .apply()
                    Log.i(TAG, "IDLE → waking CallWatcherService for scan")
                    val i = Intent(context, CallWatcherService::class.java)
                        .putExtra(CallWatcherService.EXTRA_RESUME, true)
                    // v1.9.9 — API 26 才有 startForegroundService；Android 6/7 退回 startService
                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                        context.startForegroundService(i)
                    } else {
                        context.startService(i)
                    }
                }
            }
        }
    }
}
