package com.autoluyin.demo

import android.content.Context
import android.content.SharedPreferences

/**
 * 三层配置：
 *   L1 [backendUrl]      —— 后端地址；首次启动用户输入或扫码注入，存 SharedPreferences。
 *   L2 [runtime]         —— 运行时业务配置（候选录音目录、扫描超时、prompt 版本等），
 *                            自检后从 /api/devices/{id}/config 拉取。
 *   L3 第三方 API key    —— 仅在服务端 .env，APK 永远不持有。
 */
object AppConfig {
    private const val PREFS = "autoluyin_cfg"
    private const val KEY_BACKEND_URL = "backend_url"
    private const val KEY_RUNTIME_JSON = "runtime_json"

    @Volatile private var cached: SharedPreferences? = null
    private fun prefs(ctx: Context): SharedPreferences =
        cached ?: ctx.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .also { cached = it }

    // -------- L1：后端地址 --------
    fun backendUrl(ctx: Context): String? {
        val v = prefs(ctx).getString(KEY_BACKEND_URL, null)
        return v?.takeIf { it.isNotBlank() }
    }

    fun saveBackendUrl(ctx: Context, url: String) {
        val normalized = url.trim().trimEnd('/')
        prefs(ctx).edit().putString(KEY_BACKEND_URL, normalized).apply()
        ApiClient.invalidate()
    }

    fun clearBackendUrl(ctx: Context) {
        prefs(ctx).edit().remove(KEY_BACKEND_URL).apply()
        ApiClient.invalidate()
    }

    // -------- JWT Token --------
    fun jwtToken(ctx: Context): String? =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("jwt_token", null)

    fun saveJwtToken(ctx: Context, token: String) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("jwt_token", token).apply()
    }

    fun clearJwtToken(ctx: Context) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .remove("jwt_token").apply()
    }

    /** Alias for jwtToken — used by realtime call stack. */
    fun token(ctx: Context): String? = jwtToken(ctx)

    // -------- 设备 ID --------
    /** Returns the stable device ID (ANDROID_ID). Convenience alias for DeviceId.get(). */
    fun deviceId(ctx: Context): String? =
        android.provider.Settings.Secure.getString(
            ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID
        )?.takeIf { it.isNotBlank() }

    // -------- MiPush 注册 ID --------
    private const val KEY_PUSH_REG_ID = "push_reg_id"

    fun pushRegId(ctx: Context): String? =
        prefs(ctx).getString(KEY_PUSH_REG_ID, null)

    fun savePushRegId(ctx: Context, regId: String) {
        prefs(ctx).edit().putString(KEY_PUSH_REG_ID, regId).apply()
    }

    // -------- L2：运行时业务配置 --------
    @Volatile var runtime: Runtime = Runtime()

    data class Runtime(
        val scanTimeoutSec: Int = 30,
        val uploadMaxSizeMb: Int = 50,
        val selfCheckIntervalMin: Int = 60,
        val promptVersion: String = "v1",
        val candidateDirs: List<String> = RecordingScanner.defaultCandidateDirs,
    )

    fun applyRuntime(ctx: Context, raw: Map<String, Any?>) {
        @Suppress("UNCHECKED_CAST")
        val dirs = (raw["candidate_dirs"] as? List<String>)
            ?: RecordingScanner.defaultCandidateDirs
        runtime = Runtime(
            scanTimeoutSec = (raw["scan_timeout_sec"] as? Number)?.toInt() ?: 30,
            uploadMaxSizeMb = (raw["upload_max_size_mb"] as? Number)?.toInt() ?: 50,
            selfCheckIntervalMin = (raw["self_check_interval_min"] as? Number)?.toInt() ?: 60,
            promptVersion = raw["prompt_version"] as? String ?: "v1",
            candidateDirs = dirs,
        )
        prefs(ctx).edit()
            .putString(KEY_RUNTIME_JSON, runtime.toString())
            .apply()
    }

    // -------- v2.1 — Capability 持久化 --------
    private const val KEY_CAPABILITY = "capability"          // realtime / post_upload / incompatible
    private const val KEY_CAPABILITY_GUIDANCE = "capability_guidance"
    private const val KEY_CAPABILITY_ROM = "capability_rom"
    private const val KEY_CAPABILITY_CHECKED_AT = "capability_checked_at"  // epoch ms
    private const val KEY_LAST_RECORDING_SCAN_FAILED = "last_recording_scan_failed"

    data class CapabilityState(
        val capability: String,    // realtime / post_upload / incompatible
        val guidance: String,
        val rom: String,
        val checkedAtMs: Long,
    )

    fun saveCapability(ctx: Context, capability: String, guidance: String, rom: String) {
        prefs(ctx).edit()
            .putString(KEY_CAPABILITY, capability)
            .putString(KEY_CAPABILITY_GUIDANCE, guidance)
            .putString(KEY_CAPABILITY_ROM, rom)
            .putLong(KEY_CAPABILITY_CHECKED_AT, System.currentTimeMillis())
            .apply()
    }

    fun getCapability(ctx: Context): CapabilityState? {
        val cap = prefs(ctx).getString(KEY_CAPABILITY, null) ?: return null
        return CapabilityState(
            capability = cap,
            guidance = prefs(ctx).getString(KEY_CAPABILITY_GUIDANCE, "") ?: "",
            rom = prefs(ctx).getString(KEY_CAPABILITY_ROM, "") ?: "",
            checkedAtMs = prefs(ctx).getLong(KEY_CAPABILITY_CHECKED_AT, 0L),
        )
    }

    fun markRecordingScanFailed(ctx: Context, failed: Boolean) {
        prefs(ctx).edit().putBoolean(KEY_LAST_RECORDING_SCAN_FAILED, failed).apply()
    }

    fun getLastRecordingScanFailed(ctx: Context): Boolean? {
        if (!prefs(ctx).contains(KEY_LAST_RECORDING_SCAN_FAILED)) return null  // 从未设置过
        return prefs(ctx).getBoolean(KEY_LAST_RECORDING_SCAN_FAILED, false)
    }

    // -------- v2.1 Task 5 — Onboarding Wizard 完成标志 --------
    private const val KEY_ONBOARDING_DONE = "onboarding_done"

    fun isOnboardingDone(ctx: Context): Boolean =
        prefs(ctx).getBoolean(KEY_ONBOARDING_DONE, false)

    fun markOnboardingDone(ctx: Context) {
        prefs(ctx).edit().putBoolean(KEY_ONBOARDING_DONE, true).apply()
    }

    // -------- v2.2 Module A — 用户手选录音目录（SAF 持久化 URI） --------
    // 当静态候选目录扫描失败时，用户可通过 SAF (Storage Access Framework)
    // 手动定位录音目录；持久化 URI 后 self-check / 录音匹配优先使用此目录。
    private const val KEY_USER_RECORDING_DIR_URI = "user_recording_dir_uri"

    fun saveUserRecordingDirUri(context: Context, uri: String) {
        prefs(context).edit().putString(KEY_USER_RECORDING_DIR_URI, uri).apply()
    }

    fun getUserRecordingDirUri(context: Context): String? =
        prefs(context).getString(KEY_USER_RECORDING_DIR_URI, null)?.takeIf { it.isNotBlank() }

    fun clearUserRecordingDirUri(context: Context) {
        prefs(context).edit().remove(KEY_USER_RECORDING_DIR_URI).apply()
    }
}
