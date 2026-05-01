package com.autoluyin.demo.realtime

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.R

data class TranscriptSegment(
    val seq: Long,
    val speaker: String,  // "agent" / "customer"
    val text: String,
)

class TranscriptAdapter : RecyclerView.Adapter<TranscriptAdapter.VH>() {
    private val items = mutableListOf<TranscriptSegment>()

    fun append(seg: TranscriptSegment) {
        items += seg
        notifyItemInserted(items.size - 1)
    }

    fun snapshot(): List<TranscriptSegment> = items.toList()

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val label: TextView = view.findViewById(R.id.speakerLabel)
        val text: TextView = view.findViewById(R.id.segmentText)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_transcript_segment, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val seg = items[position]
        holder.label.text = if (seg.speaker == "agent") "[我]" else "[客户]"
        holder.text.text = seg.text
    }

    override fun getItemCount(): Int = items.size
}
