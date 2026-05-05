package com.autoluyin.demo.realtime

import android.app.Dialog
import android.content.Context
import android.widget.Button
import android.widget.TextView
import com.autoluyin.demo.R

class RiskBlockingModal(
    context: Context,
    private val event: RiskEvent,
    private val onConfirmContinue: () -> Unit,
    private val onEndCall: () -> Unit,
) : Dialog(context) {

    init {
        setContentView(R.layout.dialog_risk_blocking)
        setCancelable(false)

        val msgView = findViewById<TextView>(R.id.riskModalMsg)
        val catLabel = when (event.category) {
            "owner_threat" -> "业主威胁"
            "agent_violation" -> "催收员违规"
            else -> event.category
        }
        val kwHint = if (event.matchedKeywords.isNotEmpty())
            "\n关键词：「${event.matchedKeywords.take(2).joinToString("、")}」" else ""
        msgView.text = "⚠ 检测到${catLabel}（置信度 ${(event.llmConfidence * 100).toInt()}%）\n\n「${event.textSnippet}」$kwHint\n\n请确认是否继续通话？"

        findViewById<Button>(R.id.riskModalContinue).setOnClickListener {
            dismiss()
            onConfirmContinue()
        }
        findViewById<Button>(R.id.riskModalEndCall).setOnClickListener {
            dismiss()
            onEndCall()
        }
    }
}
