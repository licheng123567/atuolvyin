package com.autoluyin.demo.realtime

class RiskAlertController(private val listener: AlertListener) {

    private val seenRiskIds = mutableSetOf<String>()

    interface AlertListener {
        fun showToast(message: String)
        fun showBanner(event: RiskEvent)
        fun showBlockingModal(event: RiskEvent)
    }

    enum class AlertType { TOAST, BANNER, BLOCKING_MODAL }

    fun onRiskEvent(event: RiskEvent) {
        if (!seenRiskIds.add(event.dedupKey)) return
        when (decide(event)) {
            AlertType.TOAST -> listener.showToast(buildToastMessage(event))
            AlertType.BANNER -> listener.showBanner(event)
            AlertType.BLOCKING_MODAL -> listener.showBlockingModal(event)
        }
    }

    fun decide(event: RiskEvent): AlertType {
        val isDoubleConfirmed = event.trigger == "keyword+llm" && event.llmConfidence > 0.85
        return when {
            event.level == "L2" && isDoubleConfirmed -> AlertType.BLOCKING_MODAL
            event.level == "L2" -> AlertType.BANNER
            else -> AlertType.TOAST
        }
    }

    private fun buildToastMessage(event: RiskEvent): String {
        val catLabel = categoryLabel(event.category)
        val kwHint = if (event.matchedKeywords.isNotEmpty())
            "（关键词：${event.matchedKeywords.take(2).joinToString("、")}）"
        else ""
        return "⚠ 风控提示：$catLabel$kwHint"
    }

    private fun categoryLabel(category: String): String = when (category) {
        "owner_abuse" -> "业主辱骂"
        "owner_threat" -> "业主威胁"
        "agent_violation" -> "催收员违规"
        "agent_minor_misconduct" -> "催收员轻微不当"
        else -> category
    }
}
