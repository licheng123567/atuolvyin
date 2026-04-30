package com.autoluyin.demo

import android.app.*
import android.content.*
import android.os.*
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class CallWatcherService : Service() {

    companion object {
        const val EXTRA_CASE_ID = "case_id"
        const val EXTRA_CALLEE  = "callee_phone"
        const val EXTRA_RESUME  = "resume_scan"
        private const val NOTIF_ID = 1001
        private const val CHANNEL  = "autoluyin_call_watch"
        private const val TAG      = "CallWatcher"

        fun start(ctx: Context, caseId: Long, callee: String) {
            val i = Intent(ctx, CallWatcherService::class.java).apply {
                putExtra(EXTRA_CASE_ID, caseId)
                putExtra(EXTRA_CALLEE, callee)
            }
            ctx.startForegroundService(i)
        }
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
        startForeground(NOTIF_ID, buildNotification("待机中"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val resume = intent?.getBooleanExtra(EXTRA_RESUME, false) ?: false

        if (resume) {
            Log.i(TAG, "resumed by PhoneStateReceiver, starting scan")
            updateNotif("挂机，匹配录音…")
            scope.launch { matchAndUpload() }
        } else {
            val caseId = intent?.getLongExtra(EXTRA_CASE_ID, 0) ?: 0
            val callee = intent?.getStringExtra(EXTRA_CALLEE).orEmpty()
            saveState(caseId = caseId, callee = callee, startedAt = 0, endedAt = 0, observed = false)
            updateNotif("等待呼叫 ${maskPhone(callee)}…")
        }
        return START_NOT_STICKY
    }

    private suspend fun matchAndUpload() {
        val prefs     = getSharedPreferences(PhoneStateReceiver.PREFS, Context.MODE_PRIVATE)
        val caseId    = prefs.getLong(PhoneStateReceiver.KEY_TASK_ID, 0)
        val callee    = prefs.getString(PhoneStateReceiver.KEY_CALLEE, "").orEmpty()
        val startedAt = prefs.getLong(PhoneStateReceiver.KEY_STARTED, 0)
        val endedAt   = prefs.getLong(PhoneStateReceiver.KEY_ENDED, System.currentTimeMillis())

        if (startedAt == 0L || callee.isEmpty()) {
            Log.w(TAG, "matchAndUpload: missing state startedAt=$startedAt callee=$callee")
            updateNotif("状态丢失，无法上传")
            clearState(); stopSelfDelayed(); return
        }

        val timeoutMs = AppConfig.runtime.scanTimeoutSec * 1000L
        val deadline  = System.currentTimeMillis() + timeoutMs
        var hit: RecordingScanner.MatchResult? = null
        while (System.currentTimeMillis() < deadline) {
            hit = RecordingScanner.findRecording(RecordingScanner.MatchInput(callee, startedAt, endedAt))
            if (hit != null) break
            delay(1500)
        }

        if (hit == null) {
            Log.w(TAG, "no recording matched callee=$callee")
            updateNotif("未找到录音，请手动补传")
            clearState(); stopSelfDelayed(); return
        }

        val durSec = ((endedAt - startedAt) / 1000).toInt().coerceAtLeast(1)
        Log.i(TAG, "matched ${hit.file.absolutePath} via ${hit.method}")

        try {
            val resp = ApiClient.get(this@CallWatcherService).uploadRecording(
                caseId      = ApiClient.textPart(caseId.toString()),
                deviceId    = ApiClient.textPart(DeviceId.get(this@CallWatcherService)),
                calleePhone = ApiClient.textPart(callee),
                startedAt   = ApiClient.textPart(iso(startedAt)),
                endedAt     = ApiClient.textPart(iso(endedAt)),
                durationSec = ApiClient.textPart(durSec.toString()),
                file        = ApiClient.filePart("file", hit.file, mimeOf(hit.file)),
            )
            Log.i(TAG, "uploaded call=${resp.call_id}")
            updateNotif("上传完成 #${resp.call_id}")
            sendBroadcast(Intent("com.autoluyin.demo.UPLOAD_DONE")
                .setPackage(packageName)
                .putExtra("call_id", resp.call_id)
                .putExtra("case_id", caseId))
        } catch (t: Throwable) {
            Log.e(TAG, "upload failed", t)
            updateNotif("上传失败：${t.message}")
        }
        clearState()
        stopSelfDelayed()
    }

    private fun saveState(caseId: Long, callee: String, startedAt: Long, endedAt: Long, observed: Boolean) {
        getSharedPreferences(PhoneStateReceiver.PREFS, Context.MODE_PRIVATE).edit()
            .putLong(PhoneStateReceiver.KEY_TASK_ID, caseId)
            .putString(PhoneStateReceiver.KEY_CALLEE, callee)
            .putLong(PhoneStateReceiver.KEY_STARTED, startedAt)
            .putLong(PhoneStateReceiver.KEY_ENDED, endedAt)
            .putBoolean(PhoneStateReceiver.KEY_OBSERVED, observed)
            .apply()
    }

    private fun clearState() {
        getSharedPreferences(PhoneStateReceiver.PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }

    private fun stopSelfDelayed() {
        scope.launch { delay(3000); stopSelf() }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun ensureChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, "通话采集", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle("autoluyin 录音采集")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_phone_call)
            .setOngoing(true)
            .build()

    private fun updateNotif(text: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIF_ID, buildNotification(text))
    }

    private fun maskPhone(p: String) =
        if (p.length >= 7) p.substring(0, 3) + "****" + p.takeLast(4) else p

    private fun iso(ms: Long): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = java.util.TimeZone.getTimeZone("UTC")
        }.format(Date(ms))

    private fun mimeOf(f: File) = when (f.extension.lowercase()) {
        "m4a", "aac" -> "audio/mp4"
        "mp3"        -> "audio/mpeg"
        "amr"        -> "audio/amr"
        "wav"        -> "audio/wav"
        else         -> "application/octet-stream"
    }
}

object DeviceId {
    @SuppressWarnings("HardwareIds")
    fun get(ctx: Context): String =
        android.provider.Settings.Secure.getString(
            ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID
        ) ?: "unknown"
}
