package com.autoluyin.demo.screens.realtime

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.realtime.AudioStreamClient
import com.autoluyin.demo.realtime.RiskAlertController
import com.autoluyin.demo.realtime.RiskEvent
import com.autoluyin.demo.realtime.TranscriptSegment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

/**
 * v2.0 Task 6 — Compose ViewModel for Screen 3 (通话中).
 *
 * 把 [AudioStreamClient] 的 callback 接口转成 StateFlow，让 Compose 通过
 * collectAsState() 订阅；ViewModel 在 onCleared() 时 stop 流式客户端。
 *
 * 风控逻辑保留 [RiskAlertController]：listener 把 toast/banner/blocking-modal
 * 转发到对应的 SharedFlow / StateFlow，由 UI 层渲染（toast 走 Toast，banner / modal
 * 走 Composable）。
 *
 * 旋转屏幕 / 进程恢复时 ViewModel 会保留 transcript & state — 这是与旧 Activity
 * 持久成员的本质差异。
 */
class RealtimeCallViewModel(
    private val app: Application,
) : AndroidViewModel(app) {

    private val _transcript = MutableStateFlow<List<TranscriptSegment>>(emptyList())
    val transcript: StateFlow<List<TranscriptSegment>> = _transcript.asStateFlow()

    private val _suggestion = MutableStateFlow<Pair<String, String>?>(null)
    val suggestion: StateFlow<Pair<String, String>?> = _suggestion.asStateFlow()

    private val _connectionState = MutableStateFlow(AudioStreamClient.State.NORMAL)
    val connectionState: StateFlow<AudioStreamClient.State> = _connectionState.asStateFlow()

    private val _activeBannerRisk = MutableStateFlow<RiskEvent?>(null)
    val activeBannerRisk: StateFlow<RiskEvent?> = _activeBannerRisk.asStateFlow()

    private val _blockingRisk = MutableStateFlow<RiskEvent?>(null)
    val blockingRisk: StateFlow<RiskEvent?> = _blockingRisk.asStateFlow()

    private val _tagPayload = MutableStateFlow<AudioStreamClient.TagPayload?>(null)
    val tagPayload: StateFlow<AudioStreamClient.TagPayload?> = _tagPayload.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast.asSharedFlow()

    private var streamClient: AudioStreamClient? = null
    private var callId: Long = -1L
    private var caseId: Long = -1L
    private var startedAtMs: Long = 0L
    private var started: Boolean = false

    /** RiskAlertController 转发器 — 把三个 callback 灌进 StateFlow / SharedFlow。 */
    private val riskController = RiskAlertController(object : RiskAlertController.AlertListener {
        override fun showToast(message: String) {
            _toast.tryEmit(message)
        }

        override fun showBanner(event: RiskEvent) {
            _activeBannerRisk.value = event
        }

        override fun showBlockingModal(event: RiskEvent) {
            // 业务逻辑：弹 modal 期间暂停录音，dismiss 时由 dismissBlockingRisk 决定 resume / hangup。
            streamClient?.pauseRecording()
            _blockingRisk.value = event
        }
    })

    fun start(callId: Long, caseId: Long) {
        if (started) return
        this.callId = callId
        this.caseId = caseId
        startedAtMs = System.currentTimeMillis()
        val token = AppConfig.token(app) ?: run {
            _toast.tryEmit("未登录，无法开始流式录音")
            return
        }
        ApiClient.appContext = app
        streamClient = AudioStreamClient(
            callId = callId,
            token = token,
            context = app,
            onTranscript = { seg -> _transcript.update { it + seg } },
            onSuggestion = { id, text -> _suggestion.value = id to text },
            onTagReady = { tag -> _tagPayload.value = tag },
            onStateChange = { state -> _connectionState.value = state },
            onRisk = { event -> riskController.onRiskEvent(event) },
        ).also { it.start() }
        started = true
    }

    fun adopt(id: String) {
        postFeedback(id, "adopt")
        _suggestion.value = null
    }

    fun ignore(id: String) {
        postFeedback(id, "ignore")
        _suggestion.value = null
    }

    /** L1 banner 用户点 "查看建议" / 自然消失：清掉。 */
    fun dismissBannerRisk() {
        _activeBannerRisk.value = null
    }

    /**
     * L3 强制 modal 的两个出口：
     *  - continueCall=true：恢复录音，清掉 modal，留在通话页。
     *  - continueCall=false：调用方负责 hangup；这里只 resume（确保 stop 时录音线程已恢复，
     *    避免 stopAndCollectWav 漏帧）+ 清 modal。
     */
    fun dismissBlockingRisk(continueCall: Boolean) {
        if (continueCall) streamClient?.resumeRecording() else streamClient?.resumeRecording()
        _blockingRisk.value = null
    }

    fun consumeTagPayload(): AudioStreamClient.TagPayload? {
        val cur = _tagPayload.value
        _tagPayload.value = null
        return cur
    }

    fun stopAndCollect(): File? = streamClient?.stopAndCollectWav()

    fun hadServerTag(): Boolean = streamClient?.hadServerTag() ?: false

    fun startedAt(): Long = startedAtMs

    fun callId(): Long = callId

    fun caseId(): Long = caseId

    private fun postFeedback(suggestionId: String, action: String) {
        val token = AppConfig.token(app) ?: return
        viewModelScope.launch(Dispatchers.IO) {
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

    override fun onCleared() {
        streamClient?.stop()
        streamClient = null
        super.onCleared()
    }
}
