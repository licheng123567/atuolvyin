package com.autoluyin.demo

import android.os.Build
import android.os.Environment
import android.util.Log
import java.io.File

/**
 * 录音文件扫描器：通话挂机后在厂商录音目录里匹配文件。
 *
 * 匹配规则（多重 fallback）：
 *   1. 文件名包含通话对端号码（脱敏比对，去掉 +86 / 0 前缀）；
 *   2. 文件 mtime ∈ [挂机时间 - 5s, 挂机时间 + 30s]；
 *   3. 文件大小 > 0 且大致与通话时长匹配（≥ 0.5KB / 秒）。
 *
 * 优先级：精确名匹配 > 时间窗 + 大小匹配。
 *
 * 注意：MIUI 历代版本目录有变动，此处维护一份候选目录清单，逐一探测。
 */
object RecordingScanner {

    private const val TAG = "RecordingScanner"

    /** 默认候选目录；运行时以 AppConfig.runtime.candidateDirs 为准（可被后台下发覆盖）。*/
    val defaultCandidateDirs: List<String> = listOf(
        // 小米 / Redmi（HyperOS / MIUI）
        "MIUI/sound_recorder/call_rec",
        "MIUI/sound_recorder/call_recordings",
        "Recordings/call",
        "Recordings/Call",
        "Recordings/CallRecordings",
        // 华为 / 荣耀
        "Sounds/CallRecord",
        "record/Call",
        // OPPO / 一加
        "Recordings/Call Recordings",
        // vivo / iQOO
        "记录/通话录音",
        "Music/Recordings/Call Recordings",
        // 魅族
        "Recorder/call",
    )

    private fun candidateDirs(): List<String> = AppConfig.runtime.candidateDirs

    data class MatchInput(
        val calleePhone: String,
        val startedAtMillis: Long,
        val endedAtMillis: Long,
    )

    data class MatchResult(
        val file: File,
        val method: String,         // "name_match" | "window_match"
    )

    fun findRecording(input: MatchInput): MatchResult? {
        val root = Environment.getExternalStorageDirectory()
        val keyDigits = input.calleePhone.filter { it.isDigit() }.takeLast(11)

        val dirs = candidateDirs()
        val files = dirs
            .map { File(root, it) }
            .filter { it.exists() && it.canRead() }
            .flatMap { it.walkTopDown().asSequence().toList() }
            .filter { it.isFile && it.length() > 0 && isAudio(it.name) }

        Log.d(TAG, "scan dirs=${dirs.size}, found ${files.size} audio files")

        // 1. 文件名直接含号码
        files.firstOrNull { it.name.contains(keyDigits) && inWindow(it, input) }?.let {
            return MatchResult(it, "name_match")
        }

        // 2. 时间窗内最新一个 + 时长大致一致
        val durSec = ((input.endedAtMillis - input.startedAtMillis) / 1000).coerceAtLeast(1)
        files
            .filter { inWindow(it, input) }
            .filter { it.length() >= 512L * durSec / 2 }   // 极宽松的下限，防止半成品
            .maxByOrNull { it.lastModified() }
            ?.let { return MatchResult(it, "window_match") }

        return null
    }

    fun listDirsExisting(): List<String> {
        val root = Environment.getExternalStorageDirectory()
        return candidateDirs().filter { File(root, it).exists() }
    }

    private fun inWindow(f: File, input: MatchInput): Boolean {
        val mt = f.lastModified()
        return mt in (input.startedAtMillis - 5_000)..(input.endedAtMillis + 30_000)
    }

    private fun isAudio(name: String): Boolean {
        val lower = name.lowercase()
        return lower.endsWith(".m4a") || lower.endsWith(".mp3") ||
               lower.endsWith(".amr") || lower.endsWith(".aac") ||
               lower.endsWith(".wav") || lower.endsWith(".3gp") ||
               lower.endsWith(".ogg")
    }

    fun deviceBrand() = Build.BRAND.lowercase()
    fun deviceModel() = "${Build.MANUFACTURER} ${Build.MODEL}"
    fun osVersion() = "Android ${Build.VERSION.RELEASE} SDK${Build.VERSION.SDK_INT}"
}
