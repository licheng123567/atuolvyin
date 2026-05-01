package com.autoluyin.demo.realtime

import android.content.Context
import android.util.AttributeSet
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.cardview.widget.CardView

class SuggestionCardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : CardView(context, attrs) {

    private val titleView: TextView
    private val textView: TextView
    private val adoptBtn: Button
    private val ignoreBtn: Button

    var onAdopt: ((suggestionId: String) -> Unit)? = null
    var onIgnore: ((suggestionId: String) -> Unit)? = null

    private var currentSuggestionId: String? = null

    init {
        radius = 16f
        setContentPadding(16, 16, 16, 16)
        useCompatPadding = true

        // Build a simple layout in code to avoid an extra layout file
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
        }
        titleView = TextView(context).apply { text = "💡 AI 建议"; textSize = 14f }
        textView = TextView(context).apply { textSize = 16f }
        val btnRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        adoptBtn = Button(context).apply { text = "采用" }
        ignoreBtn = Button(context).apply { text = "忽略" }
        btnRow.addView(adoptBtn)
        btnRow.addView(ignoreBtn)
        container.addView(titleView)
        container.addView(textView)
        container.addView(btnRow)
        addView(container)

        adoptBtn.setOnClickListener {
            currentSuggestionId?.let { id -> onAdopt?.invoke(id) }
        }
        ignoreBtn.setOnClickListener {
            currentSuggestionId?.let { id -> onIgnore?.invoke(id) }
        }
        visibility = GONE
    }

    fun show(suggestionId: String, text: String) {
        currentSuggestionId = suggestionId
        textView.text = text
        visibility = VISIBLE
    }

    fun hide() {
        currentSuggestionId = null
        visibility = GONE
    }
}
