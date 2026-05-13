package com.autoluyin.demo.screens.realtime

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsBottomHeight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.autoluyin.demo.realtime.AudioStreamClient
import com.autoluyin.demo.realtime.RiskEvent
import com.autoluyin.demo.realtime.TranscriptSegment
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * v2.0 Task 6 — Screen 3 通话中（重写为 Compose）。
 *
 * 视觉规格映射 ui/app-agent.html line 1081-1151 + line 338-503：
 *  - 全屏深蓝 #0F172A
 *  - 顶部 status bar：时间 + 绿色 "通话中" badge + 电池
 *  - 风控 L1 橙色提示条（仅当 activeRisk 非空显示）
 *  - 业主名 24sp + 时长 20sp 绿 + 网络 12sp 绿
 *  - 实时转写卡（深底，agent 行白色，owner 行半透明白）
 *  - 7 根脉动绿条波形（仅 NORMAL 状态显示）
 *  - AI 建议浮卡（白底圆角，slide-up 动画）
 *  - 底部 4 列控制按钮（挂断红底）
 *  - L3 强制 modal（用 AlertDialog 替代旧 RiskBlockingModal）
 */

// ---- 颜色 token（仅本屏使用的深色系，没在 design-system.css 内）----
private val IncallBg = Color(0xFF0F172A)              // slate-900
private val IncallSurface = Color(0xFF1E293B)         // slate-800
private val IncallControlBg = Color(0xFF1E293B)
private val IncallControlBgAlpha = Color(0xFFFFFFFF).copy(alpha = 0.10f)
private val IncallBorder = Color(0xFF334155)          // slate-700
private val IncallSubtle = Color(0xFF94A3B8)          // slate-400
private val WaveformGreen = Color(0xFF22C55E)
private val HangupRed = Color(0xFFEF4444)
private val HangupTextRed = Color(0xFFF87171)
private val L1OrangeBg = Color(0xFFD97706)
private val L1OrangeBtnBg = Color(0xFFFFFFFF).copy(alpha = 0.20f)
private val SuggestionAccent = Color(0xFF1A56DB)
private val SuggestionText = Color(0xFF374151)
private val SuggestionDismissBorder = Color(0xFFD1D5DB)
private val SuggestionDismissText = Color(0xFF6B7280)

/** Composable 接收的 immutable 状态快照。Activity 把多个 StateFlow 合并塞进来。 */
data class RealtimeCallState(
    val transcript: List<TranscriptSegment>,
    val suggestion: Pair<String, String>?,
    val connectionState: AudioStreamClient.State,
    val activeRisk: RiskEvent?,
    val blockingRisk: RiskEvent?,
    val durationSec: Int,
)

@Composable
fun RealtimeCallScreen(
    ownerName: String,
    @Suppress("UNUSED_PARAMETER") ownerPhoneMasked: String,
    state: RealtimeCallState,
    onAdopt: (String) -> Unit,
    onIgnore: () -> Unit,
    onHangup: () -> Unit,
    onMuteToggle: () -> Unit,
    onAddNote: () -> Unit,
    onSendCode: () -> Unit,
    onDismissBannerRisk: () -> Unit,
    onDismissBlockingRisk: (continueCall: Boolean) -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(IncallBg),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .systemBarsPadding(),
        ) {
            IncallStatusBar(durationSec = state.durationSec)

            if (state.activeRisk != null) {
                RiskStripL1(
                    risk = state.activeRisk,
                    onDismiss = onDismissBannerRisk,
                )
            }

            IncallHeader(
                ownerName = ownerName,
                durationSec = state.durationSec,
                connectionState = state.connectionState,
            )

            TranscriptStream(
                transcript = state.transcript,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp),
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                if (state.connectionState == AudioStreamClient.State.NORMAL) {
                    WaveformIndicator()
                }
            }

            // 给底部控制条留位 — 控制条是 align(BottomCenter) 浮在 Box，但 Column
            // 的最后元素需要消费一定的空间避免被遮，给个保底高度。
            Spacer(modifier = Modifier.height(96.dp))
        }

        // ---- AI 建议浮卡：slide-up 动画 ----
        AnimatedVisibility(
            visible = state.suggestion != null,
            enter = slideInVertically(initialOffsetY = { it }),
            exit = slideOutVertically(targetOffsetY = { it }),
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(start = 12.dp, end = 12.dp, bottom = 96.dp),
        ) {
            state.suggestion?.let { (id, text) ->
                AiSuggestionPopup(
                    text = text,
                    onAdopt = { onAdopt(id) },
                    onIgnore = onIgnore,
                )
            }
        }

        // ---- 底部 4 列控制 ----
        IncallControls(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .systemBarsPadding(),
            onMute = onMuteToggle,
            onHangup = onHangup,
            onNote = onAddNote,
            onSendCode = onSendCode,
        )

        // ---- L3 强制挂断 modal ----
        state.blockingRisk?.let { risk ->
            RiskBlockingDialog(
                risk = risk,
                onContinue = { onDismissBlockingRisk(true) },
                onEndCall = { onDismissBlockingRisk(false); onHangup() },
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-composables
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun IncallStatusBar(durationSec: Int) {
    val nowText by produceState(initialValue = currentClock()) {
        while (true) {
            value = currentClock()
            delay(15_000L)
        }
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(32.dp)
            .padding(horizontal = 20.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = nowText,
            color = Color.White,
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Box(
            modifier = Modifier
                .background(WaveformGreen, RoundedCornerShape(10.dp))
                .padding(horizontal = 8.dp, vertical = 2.dp),
        ) {
            Text(
                text = "通话中 ${formatDuration(durationSec)}",
                color = Color.White,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        Text(
            text = "🔋",
            color = Color.White,
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun RiskStripL1(risk: RiskEvent, onDismiss: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(L1OrangeBg)
            .padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "⚠️ AI 检测到${risk.displayCategory}",
            color = Color.White,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f),
        )
        Box(
            modifier = Modifier
                .background(L1OrangeBtnBg, RoundedCornerShape(4.dp))
                .padding(horizontal = 8.dp, vertical = 2.dp),
        ) {
            TextButton(
                onClick = onDismiss,
                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
            ) {
                Text(
                    text = "查看建议",
                    color = Color.White,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}

@Composable
private fun IncallHeader(
    ownerName: String,
    durationSec: Int,
    connectionState: AudioStreamClient.State,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 20.dp, end = 20.dp, top = 16.dp, bottom = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = ownerName,
            color = Color.White,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = formatDuration(durationSec),
            color = WaveformGreen,
            fontSize = 20.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = connectionLabel(connectionState),
            color = connectionColor(connectionState),
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun TranscriptStream(
    transcript: List<TranscriptSegment>,
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()

    // transcript 末尾追加时自动滚到底
    LaunchedEffect(transcript.size) {
        if (transcript.isNotEmpty()) {
            listState.animateScrollToItem(transcript.size - 1)
        }
    }

    Column(
        modifier = modifier
            .background(IncallSurface, RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = "实时转写",
            color = Color.White.copy(alpha = 0.55f),
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(5.dp))
        // 限制高度避免吃掉整屏；超出滚动
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxWidth()
                .height(120.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            items(transcript, key = { it.seq }) { seg ->
                TranscriptLine(seg)
            }
        }
    }
}

@Composable
private fun TranscriptLine(seg: TranscriptSegment) {
    val isAgent = seg.speaker == "agent"
    val prefix = if (isAgent) "[催收员]" else "[业主]"
    val color = if (isAgent) Color.White.copy(alpha = 0.95f) else Color.White.copy(alpha = 0.7f)
    Text(
        text = "$prefix ${seg.text}",
        color = color,
        fontSize = 12.sp,
    )
}

@Composable
private fun AiSuggestionPopup(
    text: String,
    onAdopt: () -> Unit,
    onIgnore: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White, RoundedCornerShape(12.dp))
            .border(
                width = 0.dp,
                color = Color.Transparent,
                shape = RoundedCornerShape(12.dp),
            )
            // 仿设计稿 border-left: 4px solid #1A56DB —— 用左侧色块替代
            .padding(start = 4.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.White, RoundedCornerShape(12.dp))
                .padding(horizontal = 16.dp, vertical = 14.dp),
        ) {
            Column {
                Text(
                    text = "💡 AI 建议",
                    color = SuggestionAccent,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = text,
                    color = SuggestionText,
                    fontSize = 12.sp,
                )
                Spacer(modifier = Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onAdopt,
                        colors = ButtonDefaults.buttonColors(containerColor = SuggestionAccent),
                        shape = RoundedCornerShape(6.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 14.dp, vertical = 5.dp,
                        ),
                    ) {
                        Text(text = "采纳", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                    OutlinedButton(
                        onClick = onIgnore,
                        shape = RoundedCornerShape(6.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 14.dp, vertical = 5.dp,
                        ),
                    ) {
                        Text(text = "忽略", color = SuggestionDismissText, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun IncallControls(
    modifier: Modifier = Modifier,
    onMute: () -> Unit,
    onHangup: () -> Unit,
    onNote: () -> Unit,
    onSendCode: () -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(IncallControlBg)
            .padding(top = 1.dp), // 顶边一像素分隔
    ) {
        // 顶部细分隔线（border-top: 1px solid #334155）
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(IncallBorder),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CtrlButton(emoji = "🔇", label = "静音", onClick = onMute)
            CtrlButton(emoji = "📵", label = "挂断", onClick = onHangup, isHangup = true)
            CtrlButton(emoji = "📝", label = "备注", onClick = onNote)
            CtrlButton(emoji = "🔗", label = "发码", onClick = onSendCode)
        }
        // 系统手势区让位
        Spacer(modifier = Modifier.windowInsetsBottomHeight(WindowInsets.systemBars))
    }
}

@Composable
private fun CtrlButton(
    emoji: String,
    label: String,
    onClick: () -> Unit,
    isHangup: Boolean = false,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(52.dp)
                .background(
                    color = if (isHangup) HangupRed else IncallControlBgAlpha,
                    shape = CircleShape,
                )
                .padding(0.dp),
            contentAlignment = Alignment.Center,
        ) {
            // 通过 TextButton 包一层取得 ripple，但用 Box.clickable 更轻：用 Button 简化
            TextButton(
                onClick = onClick,
                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
                modifier = Modifier.size(52.dp),
            ) {
                Text(text = emoji, fontSize = 22.sp)
            }
        }
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = label,
            color = if (isHangup) HangupTextRed else IncallSubtle,
            fontSize = 11.sp,
        )
    }
}

@Composable
private fun RiskBlockingDialog(
    risk: RiskEvent,
    onContinue: () -> Unit,
    onEndCall: () -> Unit,
) {
    val kwHint = if (risk.matchedKeywords.isNotEmpty()) {
        "\n关键词：「${risk.matchedKeywords.take(2).joinToString("、")}」"
    } else ""
    val message = "⚠ 检测到${risk.displayCategory}（置信度 ${(risk.llmConfidence * 100).toInt()}%）\n\n" +
        "「${risk.textSnippet}」$kwHint\n\n请确认是否继续通话？"
    AlertDialog(
        onDismissRequest = { /* 强制：禁止点空白 dismiss */ },
        title = {
            Text(
                text = "风控提示",
                fontWeight = FontWeight.Bold,
            )
        },
        text = { Text(text = message) },
        confirmButton = {
            TextButton(onClick = onContinue) { Text(text = "继续通话") }
        },
        dismissButton = {
            TextButton(onClick = onEndCall) { Text(text = "结束通话", color = HangupRed) }
        },
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

internal fun formatDuration(totalSec: Int): String {
    val m = totalSec / 60
    val s = totalSec % 60
    return "%02d:%02d".format(m, s)
}

private fun currentClock(): String =
    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())

private fun connectionLabel(state: AudioStreamClient.State): String = when (state) {
    AudioStreamClient.State.NORMAL -> "● 网络良好 · 实时"
    AudioStreamClient.State.DEGRADED -> "● 网络较差 · 弱网"
    AudioStreamClient.State.FALLBACK_LOCAL -> "● 本地录音 · 待上传"
}

private fun connectionColor(state: AudioStreamClient.State): Color = when (state) {
    AudioStreamClient.State.NORMAL -> WaveformGreen
    AudioStreamClient.State.DEGRADED -> Color(0xFFFBBF24)        // amber
    AudioStreamClient.State.FALLBACK_LOCAL -> Color(0xFF60A5FA)  // blue-400
}
