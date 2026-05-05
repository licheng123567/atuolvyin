package com.autoluyin.demo.realtime

import io.mockk.mockk
import io.mockk.verify
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class RiskAlertControllerTest {

    private lateinit var controller: RiskAlertController
    private lateinit var listener: RiskAlertController.AlertListener

    @BeforeEach
    fun setUp() {
        listener = mockk(relaxed = true)
        controller = RiskAlertController(listener)
    }

    private fun makeEvent(
        level: String,
        category: String,
        trigger: String,
        confidence: Double = 0.91,
        riskId: String = "r-test-001",
    ) = RiskEvent(
        riskId = riskId,
        callId = 1L,
        level = level,
        category = category,
        trigger = trigger,
        llmConfidence = confidence,
        matchedKeywords = listOf("test"),
        textSnippet = "test snippet",
        speaker = "customer",
    )

    @Test
    fun `L1 owner_abuse keyword_only shows toast`() {
        val event = makeEvent("L1", "owner_abuse", "keyword_only")
        controller.onRiskEvent(event)
        verify(exactly = 1) { listener.showToast(any()) }
        verify(exactly = 0) { listener.showBanner(any()) }
        verify(exactly = 0) { listener.showBlockingModal(any()) }
    }

    @Test
    fun `L2 owner_threat keyword_only shows banner not blocking modal`() {
        val event = makeEvent("L2", "owner_threat", "keyword_only")
        controller.onRiskEvent(event)
        verify(exactly = 0) { listener.showToast(any()) }
        verify(exactly = 1) { listener.showBanner(any()) }
        verify(exactly = 0) { listener.showBlockingModal(any()) }
    }

    @Test
    fun `L2 owner_threat keyword+llm confidence 0_91 shows blocking modal`() {
        val event = makeEvent("L2", "owner_threat", "keyword+llm", confidence = 0.91)
        controller.onRiskEvent(event)
        verify(exactly = 1) { listener.showBlockingModal(any()) }
        verify(exactly = 0) { listener.showBanner(any()) }
    }

    @Test
    fun `L2 owner_threat keyword+llm confidence 0_80 shows banner not modal`() {
        val event = makeEvent("L2", "owner_threat", "keyword+llm", confidence = 0.80)
        controller.onRiskEvent(event)
        verify(exactly = 1) { listener.showBanner(any()) }
        verify(exactly = 0) { listener.showBlockingModal(any()) }
    }

    @Test
    fun `L2 agent_violation keyword+llm confidence 0_91 shows blocking modal`() {
        val event = makeEvent("L2", "agent_violation", "keyword+llm", confidence = 0.91)
        controller.onRiskEvent(event)
        verify(exactly = 1) { listener.showBlockingModal(any()) }
    }

    @Test
    fun `L1 agent_minor_misconduct shows toast`() {
        val event = makeEvent("L1", "agent_minor_misconduct", "keyword_only")
        controller.onRiskEvent(event)
        verify(exactly = 1) { listener.showToast(any()) }
    }

    @Test
    fun `duplicate risk_id within dedup window is suppressed`() {
        val event = makeEvent("L1", "owner_abuse", "keyword_only", riskId = "r-dedup-001")
        controller.onRiskEvent(event)
        controller.onRiskEvent(event)  // same riskId
        verify(exactly = 1) { listener.showToast(any()) }
    }

    @Test
    fun `different risk_ids fire separately`() {
        controller.onRiskEvent(makeEvent("L1", "owner_abuse", "keyword_only", riskId = "r-001"))
        controller.onRiskEvent(makeEvent("L1", "owner_abuse", "keyword_only", riskId = "r-002"))
        verify(exactly = 2) { listener.showToast(any()) }
    }
}
