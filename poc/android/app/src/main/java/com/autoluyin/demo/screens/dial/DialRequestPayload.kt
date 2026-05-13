package com.autoluyin.demo.screens.dial

import android.content.Intent
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * v2.0 Task 5 — Push payload → Compose Activity 之间的数据载体。
 *
 * 关键字段：
 *  - callId / caseId 必需，缺其一返回 null
 *  - ownerPhone：明文（agent 角色有权看），如果 push 没给则 null；
 *    UI 拨号时优先用 ownerPhone，否则降级用 ownerPhoneMasked（拨不通但保住流程）。
 *    TODO(后端): push 应补 owner_phone（参考 OwnerInfo schema），目前 dial-info token
 *    没办法在 push 阶段拿到。
 *  - expiresAtMs：绝对毫秒；解析自 push payload `expires_at`（ISO8601 / epoch s|ms）；
 *    缺省 = 进入 Activity 时刻 + 15s。
 */
data class DialRequestPayload(
    val callId: Long,
    val caseId: Long,
    val ownerName: String,
    val ownerPhone: String?,
    val ownerPhoneMasked: String,
    val building: String?,
    val room: String?,
    val amountOwed: String?,
    val monthsOverdue: Int?,
    val lastContactAt: String?,
    val lastOutcome: String?,
    val expiresAtMs: Long,
) {
    /** 拨号时用的电话号码：优先明文，回退到打码号（拨不通但 UI 流程可继续）。 */
    val phoneToDial: String
        get() = ownerPhone?.takeIf { it.isNotBlank() }
            ?: ownerPhoneMasked.takeIf { it.isNotBlank() }
            ?: ""

    /** "3栋1单元1201室" or "—"。building / room 缺其一就显示已知部分。 */
    val roomLabel: String
        get() {
            val b = building?.takeIf { it.isNotBlank() }
            val r = room?.takeIf { it.isNotBlank() }
            return when {
                b != null && r != null -> "$b $r"
                b != null -> b
                r != null -> r
                else -> "—"
            }
        }

    /** 业主头像首字（去掉空白后第一个字符）。空名 → "?"。 */
    val avatarChar: String
        get() = ownerName.trim().firstOrNull()?.toString() ?: "?"

    /** "上次联系：3天前 · 推托" 形式；缺数据则 null（UI 不渲染该行）。 */
    fun formatLastContactLine(): String? {
        val at = lastContactAt?.takeIf { it.isNotBlank() }
        val outcome = lastOutcome?.takeIf { it.isNotBlank() }
        if (at == null && outcome == null) return null
        val left = at ?: "—"
        val right = outcome ?: "—"
        return "上次联系：$left  ·  $right"
    }

    companion object {
        const val EXTRA_CALL_ID = "call_id"
        const val EXTRA_CASE_ID = "case_id"
        const val EXTRA_OWNER_NAME = "owner_name"
        const val EXTRA_OWNER_PHONE = "owner_phone"
        const val EXTRA_OWNER_PHONE_MASKED = "owner_phone_masked"
        const val EXTRA_BUILDING = "building"
        const val EXTRA_ROOM = "room"
        const val EXTRA_AMOUNT_OWED = "amount_owed"
        const val EXTRA_MONTHS_OVERDUE = "months_overdue"
        const val EXTRA_LAST_CONTACT_AT = "last_contact_at"
        const val EXTRA_LAST_OUTCOME = "last_outcome"
        const val EXTRA_EXPIRES_AT = "expires_at"

        /** Activity 倒计时缺省窗口（ms）。 */
        private const val DEFAULT_TTL_MS = 15_000L

        fun fromIntent(intent: Intent): DialRequestPayload? {
            val callId = intent.getLongExtra(EXTRA_CALL_ID, -1L).takeIf { it > 0 } ?: return null
            val caseId = intent.getLongExtra(EXTRA_CASE_ID, -1L).takeIf { it > 0 } ?: return null

            val rawExpires = intent.getStringExtra(EXTRA_EXPIRES_AT)
            val expiresAtMs = parseExpiresAt(rawExpires)
                ?: (System.currentTimeMillis() + DEFAULT_TTL_MS)

            return DialRequestPayload(
                callId = callId,
                caseId = caseId,
                ownerName = intent.getStringExtra(EXTRA_OWNER_NAME).orEmpty(),
                ownerPhone = intent.getStringExtra(EXTRA_OWNER_PHONE),
                ownerPhoneMasked = intent.getStringExtra(EXTRA_OWNER_PHONE_MASKED).orEmpty(),
                building = intent.getStringExtra(EXTRA_BUILDING),
                room = intent.getStringExtra(EXTRA_ROOM),
                amountOwed = intent.getStringExtra(EXTRA_AMOUNT_OWED),
                monthsOverdue = intent.getIntExtra(EXTRA_MONTHS_OVERDUE, -1)
                    .takeIf { it > 0 },
                lastContactAt = intent.getStringExtra(EXTRA_LAST_CONTACT_AT),
                lastOutcome = intent.getStringExtra(EXTRA_LAST_OUTCOME),
                expiresAtMs = expiresAtMs,
            )
        }

        /**
         * 接受三种格式：
         *  - ISO8601 "2026-05-12T14:32:20Z" / "...+08:00"
         *  - epoch 秒（10 位数字）
         *  - epoch 毫秒（13 位数字）
         * 解析失败返回 null（调用方走 DEFAULT_TTL_MS fallback）。
         */
        private fun parseExpiresAt(raw: String?): Long? {
            if (raw.isNullOrBlank()) return null
            // 数字 → epoch
            raw.toLongOrNull()?.let { v ->
                return if (v < 10_000_000_000L) v * 1000L else v
            }
            // ISO8601 — 用 SimpleDateFormat 兼容到 API 23（minSdk）
            val patterns = listOf(
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ssXXX",
                "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
                "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
            )
            for (p in patterns) {
                runCatching {
                    val sdf = SimpleDateFormat(p, Locale.US)
                    if (p.endsWith("'Z'")) sdf.timeZone = TimeZone.getTimeZone("UTC")
                    return sdf.parse(raw)?.time
                }
            }
            return null
        }
    }
}
