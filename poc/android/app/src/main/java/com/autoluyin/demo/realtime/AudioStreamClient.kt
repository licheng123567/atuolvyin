package com.autoluyin.demo.realtime

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

class AudioStreamClient(
    private val callId: Long,
    private val token: String,
    private val onTranscript: (TranscriptSegment) -> Unit,
    private val onSuggestion: (id: String, text: String) -> Unit,
    private val onTagReady: (TagPayload) -> Unit,
    private val onStateChange: (State) -> Unit,
    private val context: Context? = null,
    private val baseUrl: String = "ws://10.0.2.2:8000",  // emulator → host loopback
) {
    enum class State { NORMAL, DEGRADED, FALLBACK_LOCAL }

    data class TagPayload(
        val intent: String?,
        val promiseDate: String?,
        val promiseAmount: Double?,
        val summary: String?,
    )

    private companion object {
        const val SAMPLE_RATE = 16000
        const val FRAME_MS = 100
        const val FRAME_BYTES = SAMPLE_RATE / 1000 * FRAME_MS * 2  // 3200
        const val QUEUE_CAPACITY = 50  // 5 seconds buffer
    }

    private val running = AtomicBoolean(false)
    private val sendQueue = LinkedBlockingQueue<ByteArray>(QUEUE_CAPACITY)
    private var ws: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var recordThread: Thread? = null
    private var senderThread: Thread? = null

    @Volatile private var state: State = State.NORMAL
    @Volatile private var tagReceived: Boolean = false

    // ── FALLBACK_LOCAL file handles ────────────────────────────
    private var fallbackFile: File? = null
    private var fallbackOutputStream: FileOutputStream? = null

    private val client by lazy {
        OkHttpClient.Builder()
            .pingInterval(30, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()
    }

    fun start() {
        if (running.getAndSet(true)) return
        connectWs()
        startRecorder()
        startSender()
    }

    fun stop() {
        if (!running.getAndSet(false)) return
        recorder?.stop()
        recorder?.release()
        recorder = null
        ws?.send(JSONObject().apply { put("type", "call.ended") }.toString())
        ws?.close(1000, "client closed")
        ws = null
        recordThread?.interrupt()
        senderThread?.interrupt()
    }

    /**
     * Stop streaming and finalize any fallback WAV file.
     * Returns the WAV file path if in FALLBACK_LOCAL state, null otherwise.
     */
    fun stopAndCollectWav(): File? {
        stop()
        return finalizeFallbackWav()
    }

    /** True if the server emitted a tag.ready event before hangup. */
    fun hadServerTag(): Boolean = tagReceived

    private fun connectWs() {
        val req = Request.Builder()
            .url("$baseUrl/ws/calls/$callId?token=$token&role=agent")
            .build()
        ws = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                transition(State.NORMAL)
                webSocket.send(JSONObject().apply { put("type", "call.started") }.toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleJson(text)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                handleFailure()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (running.get()) handleFailure()
            }
        })
    }

    private fun handleJson(text: String) {
        val obj = try { JSONObject(text) } catch (_: Exception) { return }
        when (obj.optString("type")) {
            "transcript.chunk" -> onTranscript(
                TranscriptSegment(
                    seq = obj.optLong("seq"),
                    speaker = obj.optString("speaker", "customer"),
                    text = obj.optString("text"),
                )
            )
            "suggestion.ready" -> onSuggestion(
                obj.optString("id"),
                obj.optString("text"),
            )
            "tag.ready" -> {
                tagReceived = true
                onTagReady(
                    TagPayload(
                        intent = obj.optString("intent").ifEmpty { null },
                        promiseDate = obj.optString("promise_date").ifEmpty { null },
                        promiseAmount = obj.optDouble("promise_amount").takeIf { !it.isNaN() },
                        summary = obj.optString("summary").ifEmpty { null },
                    )
                )
            }
            "pong" -> Unit  // heartbeat ack
        }
    }

    private fun handleFailure() {
        transition(State.DEGRADED)
        // Exponential backoff reconnect loop
        thread(name = "ws-reconnect") {
            var attempt = 0
            while (running.get() && attempt < 5) {
                Thread.sleep(minOf(8_000L, (1L shl attempt) * 1000L))
                if (!running.get()) return@thread
                connectWs()
                Thread.sleep(2000)
                if (state == State.NORMAL) return@thread
                attempt += 1
            }
            if (running.get()) transition(State.FALLBACK_LOCAL)
        }
    }

    private fun transition(newState: State) {
        if (state != newState) {
            state = newState
            if (newState == State.FALLBACK_LOCAL) {
                context?.let { startLocalFallback(it) }
            }
            onStateChange(newState)
        }
    }

    // ── Audio capture ──────────────────────────────────────────

    private fun startRecorder() {
        val bufSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        ).coerceAtLeast(FRAME_BYTES * 4)
        recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            bufSize,
        ).also { it.startRecording() }

        recordThread = thread(name = "audio-record") {
            val frame = ByteArray(FRAME_BYTES)
            while (running.get()) {
                val rec = recorder ?: break
                val read = rec.read(frame, 0, FRAME_BYTES)
                if (read > 0) {
                    val copy = frame.copyOf(read)
                    if (!sendQueue.offer(copy)) {
                        // queue full: drop oldest 5 frames
                        repeat(5) { sendQueue.poll() }
                        sendQueue.offer(copy)
                        if (state == State.NORMAL) transition(State.DEGRADED)
                    }
                }
            }
        }
    }

    private fun startSender() {
        senderThread = thread(name = "audio-sender") {
            while (running.get()) {
                val frame = try { sendQueue.take() } catch (_: InterruptedException) { return@thread }
                when (state) {
                    State.FALLBACK_LOCAL -> {
                        // Write PCM to local file instead of WS
                        try { fallbackOutputStream?.write(frame) } catch (_: Exception) {}
                    }
                    else -> {
                        val sock = ws ?: continue
                        val ok = sock.send(frame.toByteString(0, frame.size))
                        if (!ok && state == State.NORMAL) transition(State.DEGRADED)
                    }
                }
            }
        }
    }

    // ── FALLBACK_LOCAL helpers ─────────────────────────────────

    private fun startLocalFallback(ctx: Context) {
        val dir = ctx.getExternalFilesDir("recordings") ?: ctx.filesDir
        val f = File(dir, "call_${callId}_${System.currentTimeMillis()}.pcm")
        fallbackFile = f
        fallbackOutputStream = FileOutputStream(f)
    }

    private fun finalizeFallbackWav(): File? {
        val pcm = fallbackFile ?: return null
        fallbackOutputStream?.close()
        fallbackOutputStream = null
        if (!pcm.exists() || pcm.length() == 0L) { pcm.delete(); return null }
        val wav = File(pcm.parentFile, pcm.nameWithoutExtension + ".wav")
        writeWavHeader(wav, pcm)
        pcm.delete()
        return wav
    }

    private fun writeWavHeader(out: File, pcm: File) {
        val pcmBytes = pcm.readBytes()
        val totalLen = 36 + pcmBytes.size
        val byteRate = SAMPLE_RATE * 2  // 16-bit mono
        FileOutputStream(out).use { fos ->
            fos.write("RIFF".toByteArray())
            fos.write(intToBytesLe(totalLen))
            fos.write("WAVE".toByteArray())
            fos.write("fmt ".toByteArray())
            fos.write(intToBytesLe(16))           // PCM chunk size
            fos.write(shortToBytesLe(1))          // PCM format
            fos.write(shortToBytesLe(1))          // mono
            fos.write(intToBytesLe(SAMPLE_RATE))
            fos.write(intToBytesLe(byteRate))
            fos.write(shortToBytesLe(2))          // block align
            fos.write(shortToBytesLe(16))         // bits/sample
            fos.write("data".toByteArray())
            fos.write(intToBytesLe(pcmBytes.size))
            fos.write(pcmBytes)
        }
    }

    private fun intToBytesLe(v: Int) = byteArrayOf(
        (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
        ((v shr 16) and 0xff).toByte(), ((v shr 24) and 0xff).toByte(),
    )

    private fun shortToBytesLe(v: Int) = byteArrayOf(
        (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
    )
}
