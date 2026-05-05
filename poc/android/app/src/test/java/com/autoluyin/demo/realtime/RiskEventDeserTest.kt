package com.autoluyin.demo.realtime

import org.json.JSONObject
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull

class RiskEventDeserTest {

    private val sampleJson = """
        {
          "type": "risk.event",
          "risk_id": "r-call42-1714500000000",
          "call_id": 42,
          "level": "L2",
          "category": "owner_threat",
          "trigger": "keyword+llm",
          "llm_confidence": 0.91,
          "matched_keywords": ["威胁", "投诉"],
          "text_snippet": "我要去投诉你们",
          "speaker": "customer",
          "ts": "2026-05-01T10:00:00Z"
        }
    """.trimIndent()

    @Test
    fun `fromJson parses all fields`() {
        val event = RiskEvent.fromJson(JSONObject(sampleJson))
        assertNotNull(event)
        assertEquals("r-call42-1714500000000", event!!.riskId)
        assertEquals(42L, event.callId)
        assertEquals("L2", event.level)
        assertEquals("owner_threat", event.category)
        assertEquals("keyword+llm", event.trigger)
        assertEquals(0.91, event.llmConfidence, 0.001)
        assertEquals(listOf("威胁", "投诉"), event.matchedKeywords)
        assertEquals("我要去投诉你们", event.textSnippet)
        assertEquals("customer", event.speaker)
    }

    @Test
    fun `fromJson returns null for non-risk types`() {
        val json = JSONObject("""{"type":"transcript.chunk"}""")
        val event = RiskEvent.fromJson(json)
        assertEquals(null, event)
    }

    @Test
    fun `dedup key is riskId`() {
        val event = RiskEvent.fromJson(JSONObject(sampleJson))!!
        assertEquals("r-call42-1714500000000", event.dedupKey)
    }

    @Test
    fun `fromJson returns null if both riskId fields are missing`() {
        val json = JSONObject("""{"type":"risk.event","level":"L2"}""")
        assertNull(RiskEvent.fromJson(json))
    }

    @Test
    fun `fromJson uses transcript_text fallback when text_snippet absent`() {
        val json = JSONObject("""
            {"type":"risk.event","id":"r-1","call_id":1,"level":"L1",
             "category":"owner_abuse","trigger":"keyword","speaker":"customer",
             "transcript_text":"我没钱"}
        """.trimIndent())
        val event = RiskEvent.fromJson(json)!!
        assertEquals("我没钱", event.textSnippet)
    }

    @Test
    fun `fromJson uses single matched_keyword string when array absent`() {
        val json = JSONObject("""
            {"type":"risk.event","id":"r-2","call_id":1,"level":"L1",
             "category":"owner_abuse","trigger":"keyword","speaker":"customer",
             "matched_keyword":"骂人"}
        """.trimIndent())
        val event = RiskEvent.fromJson(json)!!
        assertEquals(listOf("骂人"), event.matchedKeywords)
    }
}
