package com.autoluyin.demo.realtime

import android.content.Context
import android.util.AttributeSet
import android.view.LayoutInflater
import android.widget.Button
import android.widget.FrameLayout
import android.widget.TextView
import com.autoluyin.demo.R

class RiskBannerView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : FrameLayout(context, attrs) {

    private val msgView: TextView
    private val closeBtn: Button

    init {
        LayoutInflater.from(context).inflate(R.layout.view_risk_banner, this, true)
        msgView = findViewById(R.id.riskBannerMsg)
        closeBtn = findViewById(R.id.riskBannerClose)
        closeBtn.setOnClickListener { dismiss() }
        visibility = GONE
    }

    fun showForEvent(event: RiskEvent) {
        val kwHint = if (event.matchedKeywords.isNotEmpty())
            " · 关键词「${event.matchedKeywords.take(2).joinToString("、")}」" else ""
        msgView.text = "⚠ ${event.displayCategory}（${event.level}$kwHint）"
        visibility = VISIBLE
    }

    fun dismiss() {
        visibility = GONE
    }
}
