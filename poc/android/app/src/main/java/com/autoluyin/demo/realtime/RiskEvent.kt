package com.autoluyin.demo.realtime

import org.json.JSONObject

data class RiskEvent(
    val riskId: String,
    val callId: Long,
    val level: String,
    val category: String,
    val trigger: String,
    val llmConfidence: Double,
    val matchedKeywords: List<String>,
    val textSnippet: String,
    val speaker: String,
) {
    val dedupKey: String get() = riskId

    companion object {
        fun fromJson(obj: JSONObject): RiskEvent? {
            if (obj.optString("type") != "risk.event") return null
            val riskId = obj.optString("risk_id").ifEmpty { obj.optString("id") }
            val keywords = obj.optJSONArray("matched_keywords")
            val kwList = if (keywords != null) {
                (0 until keywords.length()).map { keywords.getString(it) }
            } else {
                val single = obj.optString("matched_keyword")
                if (single.isNotEmpty()) listOf(single) else emptyList()
            }
            val textSnippet = obj.optString("text_snippet").ifEmpty {
                obj.optString("transcript_text")
            }
            return RiskEvent(
                riskId = riskId,
                callId = obj.optLong("call_id"),
                level = obj.optString("level"),
                category = obj.optString("category"),
                trigger = obj.optString("trigger"),
                llmConfidence = obj.optDouble("llm_confidence", 0.0),
                matchedKeywords = kwList,
                textSnippet = textSnippet,
                speaker = obj.optString("speaker"),
            )
        }
    }
}
