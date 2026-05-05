package com.autoluyin.demo.realtime

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

class RealtimeCallActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_CALL_ID = "call_id"
        const val EXTRA_CASE_ID = "case_id"
        const val EXTRA_OWNER_NAME = "owner_name"
        const val EXTRA_OWNER_PHONE_MASKED = "owner_phone_masked"
        private const val REQ_PERMS = 4711
    }

    private lateinit var transcriptAdapter: TranscriptAdapter
    private lateinit var suggestionCard: SuggestionCardView
    private lateinit var riskBanner: RiskBannerView
    private lateinit var riskAlertController: RiskAlertController
    private lateinit var connectionBadge: TextView
    private lateinit var timerView: TextView
    private lateinit var streamClient: AudioStreamClient

    private var callId: Long = -1
    private var caseId: Long = -1
    private val mainHandler = Handler(Looper.getMainLooper())
    private var startedAtMs: Long = 0
    private val tickRunnable = object : Runnable {
        override fun run() {
            val secs = (System.currentTimeMillis() - startedAtMs) / 1000
            timerView.text = "%02d:%02d".format(secs / 60, secs % 60)
            mainHandler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_realtime_call)

        callId = intent.getLongExtra(EXTRA_CALL_ID, -1L)
        caseId = intent.getLongExtra(EXTRA_CASE_ID, -1L)
        if (callId <= 0 || caseId <= 0) { finish(); return }

        findViewById<TextView>(R.id.ownerName).text =
            intent.getStringExtra(EXTRA_OWNER_NAME) ?: "未知业主"
        findViewById<TextView>(R.id.ownerRoom).text =
            intent.getStringExtra(EXTRA_OWNER_PHONE_MASKED) ?: ""

        connectionBadge = findViewById(R.id.connectionBadge)
        timerView = findViewById(R.id.timer)
        suggestionCard = findViewById(R.id.suggestionCard)
        riskBanner = findViewById(R.id.riskBanner)
        riskAlertController = RiskAlertController(object : RiskAlertController.AlertListener {
            override fun showToast(message: String) {
                mainHandler.post {
                    android.widget.Toast.makeText(this@RealtimeCallActivity, message, android.widget.Toast.LENGTH_SHORT).show()
                }
            }
            override fun showBanner(event: RiskEvent) {
                mainHandler.post { riskBanner.showForEvent(event) }
            }
            override fun showBlockingModal(event: RiskEvent) {
                mainHandler.post {
                    streamClient.pauseRecording()
                    RiskBlockingModal(
                        context = this@RealtimeCallActivity,
                        event = event,
                        onConfirmContinue = {
                            if (!isFinishing && !isDestroyed) streamClient.resumeRecording()
                        },
                        onEndCall = {
                            if (!isFinishing && !isDestroyed) {
                                streamClient.resumeRecording()
                                hangUp()
                            }
                        },
                    ).show()
                }
            }
        })

        val list = findViewById<RecyclerView>(R.id.transcriptList)
        list.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        transcriptAdapter = TranscriptAdapter()
        list.adapter = transcriptAdapter

        findViewById<Button>(R.id.btnHangup).setOnClickListener { hangUp() }

        ensurePermissionsThenStart()
    }

    private fun ensurePermissionsThenStart() {
        val perms = arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CALL_PHONE)
        val missing = perms.filter {
            ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) startCall()
        else ActivityCompat.requestPermissions(this, missing.toTypedArray(), REQ_PERMS)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (requestCode == REQ_PERMS && results.all { it == PackageManager.PERMISSION_GRANTED }) {
            startCall()
        } else {
            finish()
        }
    }

    private fun startCall() {
        startedAtMs = System.currentTimeMillis()
        mainHandler.post(tickRunnable)

        val token = AppConfig.token(this) ?: run { finish(); return }
        // Ensure ApiClient has application context for service accessor
        ApiClient.appContext = applicationContext

        streamClient = AudioStreamClient(
            callId = callId,
            token = token,
            context = applicationContext,
            onTranscript = { seg -> mainHandler.post {
                transcriptAdapter.append(seg)
                findViewById<RecyclerView>(R.id.transcriptList)
                    .smoothScrollToPosition(transcriptAdapter.itemCount - 1)
            }},
            onSuggestion = { id, text -> mainHandler.post { suggestionCard.show(id, text) } },
            onTagReady = { tag -> mainHandler.post { showTagDialog(tag) } },
            onStateChange = { state -> mainHandler.post { renderState(state) } },
            onRisk = { event -> mainHandler.post { riskAlertController.onRiskEvent(event) } },
        )
        suggestionCard.onAdopt = { id -> postFeedback(id, "adopt") }
        suggestionCard.onIgnore = { id -> suggestionCard.hide(); postFeedback(id, "ignore") }
        streamClient.start()
    }

    private fun renderState(state: AudioStreamClient.State) {
        connectionBadge.text = when (state) {
            AudioStreamClient.State.NORMAL -> "🟢 实时"
            AudioStreamClient.State.DEGRADED -> "🟡 弱网"
            AudioStreamClient.State.FALLBACK_LOCAL -> "🔵 本地录音"
        }
    }

    private fun postFeedback(suggestionId: String, action: String) {
        val token = AppConfig.token(this) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                ApiClient.service.postSuggestionFeedback(
                    authHeader = "Bearer $token",
                    callId = callId,
                    suggestionId = suggestionId,
                    body = mapOf("action" to action),
                )
            }
        }
    }

    private fun showTagDialog(tag: AudioStreamClient.TagPayload) {
        PostCallTagDialog.newInstance(callId, tag).show(supportFragmentManager, "tag")
    }

    private fun hangUp() {
        val wav = streamClient.stopAndCollectWav()
        if (wav != null) {
            // FALLBACK_LOCAL — upload via Sprint 3a endpoint
            uploadFallback(wav)
        }
        // Show tag dialog if server never sent tag.ready (fallback or early hangup)
        if (!streamClient.hadServerTag()) {
            showTagDialog(AudioStreamClient.TagPayload(null, null, null, null))
        }
    }

    private fun uploadFallback(wav: File) {
        val token = AppConfig.token(this) ?: return
        val deviceId = AppConfig.deviceId(this) ?: return
        val durationSec = ((System.currentTimeMillis() - startedAtMs) / 1000).toString()
        // TODO: Sprint 4 cleanup — relax callee_phone/started_at/ended_at for
        // FALLBACK_LOCAL uploads where DIAL_REQUEST didn't persist these fields.
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                val requestBody = okhttp3.MultipartBody.Builder()
                    .setType(okhttp3.MultipartBody.FORM)
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
                val baseUrl = AppConfig.backendUrl(this@RealtimeCallActivity) ?: return@runCatching
                OkHttpClient().newCall(
                    Request.Builder()
                        .url("$baseUrl/api/v1/calls/upload")
                        .header("Authorization", "Bearer $token")
                        .post(requestBody)
                        .build()
                ).execute().close()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacks(tickRunnable)
        if (::streamClient.isInitialized) streamClient.stop()
    }
}
