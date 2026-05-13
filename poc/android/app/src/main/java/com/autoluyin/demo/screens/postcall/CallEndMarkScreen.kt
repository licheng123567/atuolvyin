package com.autoluyin.demo.screens.postcall

import android.app.DatePickerDialog
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.autoluyin.demo.ui.theme.DebtRed
import com.autoluyin.demo.ui.theme.DebtRedLight
import com.autoluyin.demo.ui.theme.Neutral100
import com.autoluyin.demo.ui.theme.Neutral200
import com.autoluyin.demo.ui.theme.Neutral300
import com.autoluyin.demo.ui.theme.Neutral400
import com.autoluyin.demo.ui.theme.Neutral600
import com.autoluyin.demo.ui.theme.Neutral700
import com.autoluyin.demo.ui.theme.Neutral900
import com.autoluyin.demo.ui.theme.Primary
import com.autoluyin.demo.ui.theme.PrimaryLight
import com.autoluyin.demo.ui.theme.Surface
import java.util.Calendar

/**
 * v2.0 Task 7 — Screen 4 通话结束标记 (Compose, 全屏 Activity)。
 *
 * 视觉规格 ui/app-agent.html line 1153-1205 + CSS line 505-598：
 *  - 顶部白卡：标题 + 时长/时间 meta + AI 分析框 + AI 摘要框
 *  - 通话结果标记 5 个 tag (含 danger 样式)
 *  - 仅 selectedTag == promise_pay 时显示 [PromiseDateBox]
 *  - 跟进备注 textarea (默认从 AI summary 预填，可改)
 *  - sticky 底部按钮：跳过 / 保存并进入下一通
 *
 * 状态：完全本地 (remember)，提交统一走 [onSubmit]。
 */
private val AiAnalysisBoxBg = Color(0xFFF0F9FF)
private val AiAnalysisLabelColor = Color(0xFF0369A1)
private val AiAnalysisIntentColor = Color(0xFF1E40AF)
private val AiSummaryBoxBg = Color(0xFFEBF5FF)

private data class TagOption(
    val key: String,
    val label: String,
    val icon: String,
    val danger: Boolean = false,
)

private val TAGS: List<TagOption> = listOf(
    TagOption("promise_pay", "承诺缴费", "✅"),
    TagOption("refuse", "拒绝缴费", "❌", danger = true),
    TagOption("workorder", "需要工单", "🔧"),
    TagOption("followup", "再次跟进", "🔄"),
    TagOption("no_answer", "无人接听", "📵"),
)

@Composable
fun CallEndMarkScreen(
    callId: Long,
    ownerName: String,
    durationSec: Int,
    startedAtMs: Long,
    aiIntent: String?,
    aiPromiseDate: String?,
    aiPromiseAmount: Double?,
    aiSummary: String?,
    onSubmit: (SubmitPayload) -> Unit,
    onSkip: () -> Unit,
) {
    // 不直接 mutate 入参；本地 state 受 AI 字段驱动，用户随后可改。
    var selectedTag: String by remember(aiIntent) { mutableStateOf(aiIntent ?: "") }
    var promiseDate: String by remember(aiPromiseDate) { mutableStateOf(aiPromiseDate ?: "") }
    var notes: String by remember(aiSummary) { mutableStateOf(aiSummary ?: "") }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Neutral100)
            .systemBarsPadding(),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp), // 给 sticky 底部按钮腾位
        ) {
            AfterCallHeader(
                ownerName = ownerName,
                durationSec = durationSec,
                startedAtMs = startedAtMs,
                aiIntent = aiIntent,
                aiSummary = aiSummary,
            )
            TagSection(
                selectedTag = selectedTag,
                onSelect = { selectedTag = it },
            )
            if (selectedTag == "promise_pay") {
                PromiseDateBox(
                    date = promiseDate,
                    amount = aiPromiseAmount,
                    onDateChange = { promiseDate = it },
                )
            }
            NotesBox(
                value = notes,
                onChange = { notes = it },
            )
        }

        BottomActions(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .background(Neutral100)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            onSkip = onSkip,
            onSave = {
                if (selectedTag.isBlank()) {
                    // 默认按 followup 提交，避免空 intent；UI 没有强校验文案。
                    onSubmit(
                        SubmitPayload(
                            intent = "followup",
                            promiseDate = promiseDate.ifBlank { null },
                            promiseAmount = aiPromiseAmount,
                            notes = notes.ifBlank { null },
                        ),
                    )
                } else {
                    onSubmit(
                        SubmitPayload(
                            intent = selectedTag,
                            promiseDate = if (selectedTag == "promise_pay") promiseDate.ifBlank { null } else null,
                            promiseAmount = if (selectedTag == "promise_pay") aiPromiseAmount else null,
                            notes = notes.ifBlank { null },
                        ),
                    )
                }
            },
        )
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件
// ──────────────────────────────────────────────────────────────────────────────

@Composable
private fun AfterCallHeader(
    ownerName: String,
    durationSec: Int,
    startedAtMs: Long,
    aiIntent: String?,
    aiSummary: String?,
) {
    Column(
        modifier = Modifier
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(12.dp))
            .padding(16.dp),
    ) {
        Text(
            text = "通话结束 — $ownerName",
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            color = Neutral900,
        )
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            MetaItem(label = "时长", value = formatDuration(durationSec))
            MetaItem(label = "时间", value = formatStartedAt(startedAtMs))
        }
        Spacer(Modifier.height(12.dp))

        // AI 分析框 (浅蓝底 + 左 4dp 蓝边)
        AiAnalysisBox(aiIntent = aiIntent, aiSummary = aiSummary)
        Spacer(Modifier.height(10.dp))
        // AI 摘要框
        AiSummaryBox(aiSummary = aiSummary)
    }
}

@Composable
private fun MetaItem(label: String, value: String) {
    Row {
        Text(text = "$label: ", fontSize = 13.sp, color = Neutral600)
        Text(
            text = value,
            fontSize = 13.sp,
            color = Neutral900,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun AiAnalysisBox(aiIntent: String?, aiSummary: String?) {
    // 设计稿要求左 4dp 蓝边；用 border 模拟左侧 inset
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AiAnalysisBoxBg, RoundedCornerShape(8.dp))
            .border(
                width = 0.dp, // 上下右无边
                color = Color.Transparent,
                shape = RoundedCornerShape(8.dp),
            )
            .leftAccent(width = 4.dp, color = Primary)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = "🤖 AI 分析结果",
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = AiAnalysisLabelColor,
        )
        Spacer(Modifier.height(4.dp))
        // 后端目前没下发 confidence；hardcode 87%（设计稿展示文案）。
        // TODO(后端): TagPayload 加 confidence 字段后改为 {(confidence*100).toInt()}%
        val intentText = if (!aiIntent.isNullOrBlank()) intentLabel(aiIntent) else "—"
        Row {
            Text(text = "意图：", fontSize = 13.sp, color = AiAnalysisIntentColor)
            Text(
                text = intentText,
                fontSize = 13.sp,
                color = AiAnalysisIntentColor,
                fontWeight = FontWeight.Bold,
            )
            if (!aiIntent.isNullOrBlank()) {
                Text(text = " · 置信度 87%", fontSize = 13.sp, color = AiAnalysisIntentColor)
            }
        }
        // 描述：后端没有 analysis_text 字段，先用 summary 兜底。
        // TODO(后端): TagPayload 加 analysis_text 字段后切换。
        if (!aiSummary.isNullOrBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(text = aiSummary, fontSize = 12.sp, color = Neutral600)
        }
    }
}

@Composable
private fun AiSummaryBox(aiSummary: String?) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AiSummaryBoxBg, RoundedCornerShape(8.dp))
            .leftAccent(width = 4.dp, color = Primary)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = "🤖 AI 通话摘要",
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = Primary,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            text = aiSummary?.takeIf { it.isNotBlank() } ?: "暂无摘要（AI 处理中或未生成）",
            fontSize = 12.sp,
            color = Neutral700,
            lineHeight = 18.sp,
        )
    }
}

@Composable
private fun TagSection(selectedTag: String, onSelect: (String) -> Unit) {
    Column(modifier = Modifier.padding(horizontal = 16.dp)) {
        Text(
            text = "通话结果标记",
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            color = Neutral900,
        )
        Spacer(Modifier.height(10.dp))
        TagFlowRow(selectedTag = selectedTag, onSelect = onSelect)
    }
}

/**
 * 横向 wrap 布局，5 个 tag 自动按宽度折行。
 * FlowRow 来自 androidx.compose.foundation.layout（compose-foundation 1.6+，已在 BOM 内）。
 */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun TagFlowRow(selectedTag: String, onSelect: (String) -> Unit) {
    androidx.compose.foundation.layout.FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        for (tag in TAGS) {
            TagButton(
                tag = tag,
                selected = tag.key == selectedTag,
                onClick = { onSelect(tag.key) },
            )
        }
    }
}

@Composable
private fun TagButton(tag: TagOption, selected: Boolean, onClick: () -> Unit) {
    val (bg, border, content) = when {
        selected && tag.danger -> Triple(DebtRedLight, DebtRed, DebtRed)
        selected -> Triple(PrimaryLight, Primary, Primary)
        else -> Triple(Surface, Neutral300, Neutral700)
    }
    Box(
        modifier = Modifier
            .wrapContentHeight()
            .background(bg, RoundedCornerShape(8.dp))
            .border(width = 1.dp, color = border, shape = RoundedCornerShape(8.dp))
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Text(
            text = "${tag.icon} ${tag.label}",
            fontSize = 13.sp,
            color = content,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}

@Composable
private fun PromiseDateBox(date: String, amount: Double?, onDateChange: (String) -> Unit) {
    val ctx = LocalContext.current
    val dateDialog = remember {
        val cal = Calendar.getInstance()
        DatePickerDialog(
            ctx,
            { _, y, m, d ->
                onDateChange(
                    "$y-${(m + 1).toString().padStart(2, '0')}-${d.toString().padStart(2, '0')}",
                )
            },
            cal.get(Calendar.YEAR),
            cal.get(Calendar.MONTH),
            cal.get(Calendar.DAY_OF_MONTH),
        )
    }
    Column(
        modifier = Modifier
            .padding(horizontal = 16.dp, vertical = 6.dp)
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(12.dp))
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        Text(
            text = "承诺缴费日期",
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            color = Neutral900,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = date,
            onValueChange = {},
            readOnly = true,
            placeholder = { Text("选择日期", color = Neutral400) },
            modifier = Modifier
                .fillMaxWidth()
                .clickable { dateDialog.show() },
        )
        Spacer(Modifier.height(6.dp))
        // promise_amount 暂不收集（设计稿只写"全款"），仅展示 + 随 submit 送回
        Text(
            text = if (amount != null) "承诺金额: ¥${formatAmount(amount)}（全款）" else "承诺金额: 全款（金额待用户在案件页确认）",
            fontSize = 12.sp,
            color = Neutral600,
        )
    }
}

@Composable
private fun NotesBox(value: String, onChange: (String) -> Unit) {
    Column(
        modifier = Modifier
            .padding(horizontal = 16.dp, vertical = 6.dp)
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(12.dp))
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        Text(
            text = "跟进备注",
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold,
            color = Neutral900,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = value,
            onValueChange = onChange,
            placeholder = { Text("可选：记录额外信息...", color = Neutral400) },
            minLines = 3,
            maxLines = 6,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun BottomActions(
    modifier: Modifier = Modifier,
    onSkip: () -> Unit,
    onSave: () -> Unit,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        // 顶部 1px 分割线
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(Neutral200),
        )
        Spacer(Modifier.height(8.dp))
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedButton(
                onClick = onSkip,
                shape = RoundedCornerShape(8.dp),
                contentPadding = PaddingValues(vertical = 14.dp),
                modifier = Modifier.width(96.dp),
            ) {
                Text("跳过", fontSize = 14.sp, color = Neutral700)
            }
            Button(
                onClick = onSave,
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary, contentColor = Surface),
                contentPadding = PaddingValues(vertical = 14.dp),
                modifier = Modifier
                    .fillMaxWidth(),
            ) {
                Text(
                    text = "保存并进入下一通 →",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// 工具
// ──────────────────────────────────────────────────────────────────────────────

private fun formatDuration(sec: Int): String {
    val safe = if (sec < 0) 0 else sec
    val m = safe / 60
    val s = safe % 60
    return "${m}分${s}秒"
}

private fun formatStartedAt(ms: Long): String {
    if (ms <= 0L) return "—"
    val cal = Calendar.getInstance().apply { timeInMillis = ms }
    val h = cal.get(Calendar.HOUR_OF_DAY).toString().padStart(2, '0')
    val m = cal.get(Calendar.MINUTE).toString().padStart(2, '0')
    return "$h:$m"
}

private fun formatAmount(amount: Double): String {
    // 简化：整数显示无小数，否则保留 2 位
    return if (amount % 1.0 == 0.0) amount.toInt().toString() else "%.2f".format(amount)
}

private fun intentLabel(code: String): String = when (code) {
    "promise_pay", "promise_made", "payment_confirmed" -> "承诺缴费"
    "refuse" -> "拒绝缴费"
    "workorder", "complaint", "dispute" -> "需要工单"
    "followup" -> "再次跟进"
    "no_answer" -> "无人接听"
    "wrong_number" -> "错号"
    else -> code
}

/**
 * 在 Composable 左侧画一条彩色 accent 条（默认 4dp）。
 * 用 drawBehind 实现，避免 border() 上下右一圈造成视觉冲突。
 */
private fun Modifier.leftAccent(width: Dp, color: Color): Modifier =
    this.drawBehind {
        val px = width.toPx()
        drawRect(
            color = color,
            topLeft = Offset(0f, 0f),
            size = Size(px, size.height),
        )
    }
