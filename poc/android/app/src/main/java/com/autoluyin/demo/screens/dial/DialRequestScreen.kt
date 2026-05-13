package com.autoluyin.demo.screens.dial

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Canvas
import com.autoluyin.demo.ui.theme.AppTheme
import com.autoluyin.demo.ui.theme.Primary
import kotlinx.coroutines.delay
import kotlin.math.ceil
import kotlin.math.max
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * v2.0 Task 5 — Screen 2 全屏拨号请求。
 *
 * 视觉规格：见 ui/app-agent.html line 196-335 (#dial-request-screen 系列)。
 * 设计 token 已在 ui.theme 中翻译；这里只用 MaterialTheme + 显式白色透明度
 * （半透明白没法走 colorScheme，所以直接用 Color.White.copy(alpha)）。
 *
 * 行为：
 *  - 倒计时基于 expiresAtMs - now，每秒 tick；归 0 调用 onTimeout 一次。
 *  - 倒计时环用 Canvas drawArc，配合 animateFloatAsState 让缩进可见。
 *  - "立即拨打" 调用 onAccept(phoneToDial)；"稍后处理" 调用 onDefer。
 */
@Composable
fun DialRequestScreen(
    payload: DialRequestPayload,
    onAccept: (phoneToDial: String) -> Unit,
    onDefer: () -> Unit,
    onTimeout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // ---- 倒计时窗口 ----
    val totalSec = remember(payload.expiresAtMs) {
        max(1, ceil((payload.expiresAtMs - System.currentTimeMillis()) / 1000.0).toInt())
    }
    var remainSec by remember { mutableStateOf(totalSec) }
    var timedOut by remember { mutableStateOf(false) }

    LaunchedEffect(payload.expiresAtMs) {
        while (true) {
            val left = ceil((payload.expiresAtMs - System.currentTimeMillis()) / 1000.0)
                .toInt()
                .coerceAtLeast(0)
            remainSec = left
            if (left <= 0) {
                if (!timedOut) {
                    timedOut = true
                    onTimeout()
                }
                break
            }
            delay(1000L)
        }
    }

    // ---- 实时时钟（HH:mm:ss） ----
    var clockText by remember { mutableStateOf(formatClock(System.currentTimeMillis())) }
    LaunchedEffect(Unit) {
        while (true) {
            clockText = formatClock(System.currentTimeMillis())
            delay(1000L)
        }
    }

    // ---- 倒计时环动画 ----
    val targetProgress = remainSec.toFloat() / totalSec.toFloat()
    val progress by animateFloatAsState(
        targetValue = targetProgress.coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 1000, easing = LinearEasing),
        label = "countdown-ring",
    )

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                brush = Brush.verticalGradient(
                    colors = listOf(Color(0xFF1E3A5F), Primary),
                ),
            )
            .systemBarsPadding(),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 0.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // -------- 顶栏 --------
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "📲 主管发来外呼请求",
                    color = Color.White.copy(alpha = 0.75f),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = clockText,
                    color = Color.White.copy(alpha = 0.75f),
                    fontSize = 12.sp,
                )
            }

            // -------- 头像 --------
            Spacer(Modifier.height(28.dp))
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.20f))
                    .border(3.dp, Color.White.copy(alpha = 0.50f), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = payload.avatarChar,
                    color = Color.White,
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                )
            }

            // -------- 姓名 --------
            Spacer(Modifier.height(14.dp))
            Text(
                text = payload.ownerName.ifBlank { "—" },
                color = Color.White,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
            )

            // -------- 房号 pill --------
            Spacer(Modifier.height(8.dp))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.White.copy(alpha = 0.15f))
                    .padding(horizontal = 12.dp, vertical = 3.dp),
            ) {
                Text(
                    text = payload.roomLabel,
                    color = Color.White.copy(alpha = 0.75f),
                    fontSize = 13.sp,
                )
            }

            // -------- 欠费卡 --------
            Spacer(Modifier.height(18.dp))
            DebtCard(payload)

            // -------- 倒计时环 + 数字 --------
            Spacer(Modifier.height(20.dp))
            CountdownRing(
                progress = progress,
                remainSec = remainSec,
            )

            // -------- 倒计时下文案 --------
            Spacer(Modifier.height(6.dp))
            Text(
                text = "${remainSec}秒后自动取消",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 12.sp,
            )

            // -------- 按钮区（底部）--------
            Spacer(Modifier.weight(1f))
            ActionButtons(
                onAccept = { onAccept(payload.phoneToDial) },
                onDefer = onDefer,
            )
            Spacer(Modifier.height(32.dp))
        }
    }
}

// ---------------------------------------------------------------------------
// 子组件
// ---------------------------------------------------------------------------

@Composable
private fun DebtCard(payload: DialRequestPayload) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Color.White.copy(alpha = 0.15f))
            .padding(horizontal = 18.dp, vertical = 14.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = payload.amountOwed?.takeIf { it.isNotBlank() } ?: "—",
            color = Color(0xFFFBBF24),
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = payload.monthsOverdue?.let { "${it}个月欠费" } ?: "—",
            color = Color.White.copy(alpha = 0.75f),
            fontSize = 12.5f.sp,
            modifier = Modifier.padding(top = 4.dp),
        )
        payload.formatLastContactLine()?.let { line ->
            // 用一个高 1dp 的细分隔线模拟 border-top（仅在有 lastContact 时绘制）
            Spacer(
                Modifier
                    .padding(top = 8.dp)
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(Color.White.copy(alpha = 0.15f)),
            )
            Text(
                text = line,
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 12.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

@Composable
private fun CountdownRing(progress: Float, remainSec: Int) {
    Box(
        modifier = Modifier.size(110.dp),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = 4.dp.toPx()
            // 半径减去 strokeWidth/2 以避免被裁剪
            val side = size.minDimension - strokeWidth
            val topLeft = Offset(strokeWidth / 2f, strokeWidth / 2f)
            val arcSize = Size(side, side)

            // 背景环
            drawArc(
                color = Color.White.copy(alpha = 0.20f),
                startAngle = 0f,
                sweepAngle = 360f,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = strokeWidth),
            )
            // 前景进度环（从 12 点开始顺时针缩进）
            drawArc(
                color = Color.White,
                startAngle = -90f,
                sweepAngle = 360f * progress,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(
                    width = strokeWidth,
                    cap = androidx.compose.ui.graphics.StrokeCap.Round,
                ),
            )
        }
        Text(
            text = remainSec.toString(),
            color = Color.White,
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun ActionButtons(
    onAccept: () -> Unit,
    onDefer: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(
            onClick = onAccept,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFF16A34A),
                contentColor = Color.White,
            ),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.Phone,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.size(10.dp))
            Text(
                text = "立即拨打",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
            )
        }

        OutlinedButton(
            onClick = onDefer,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            shape = RoundedCornerShape(14.dp),
            border = androidx.compose.foundation.BorderStroke(
                2.dp,
                Color.White.copy(alpha = 0.4f),
            ),
            colors = ButtonDefaults.outlinedButtonColors(
                containerColor = Color.Transparent,
                contentColor = Color.White.copy(alpha = 0.85f),
            ),
        ) {
            Text(
                text = "稍后处理",
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                color = Color.White.copy(alpha = 0.85f),
            )
        }
    }
}

private fun formatClock(ts: Long): String {
    return SimpleDateFormat("HH:mm:ss", Locale.US).format(Date(ts))
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------
@Preview(showBackground = true, widthDp = 360, heightDp = 760)
@Composable
private fun DialRequestScreenPreview() {
    AppTheme {
        DialRequestScreen(
            payload = DialRequestPayload(
                callId = 1001,
                caseId = 2002,
                ownerName = "张大伟",
                ownerPhone = null,
                ownerPhoneMasked = "138****1234",
                building = "3栋1单元",
                room = "1201室",
                amountOwed = "¥8,420",
                monthsOverdue = 7,
                lastContactAt = "3天前",
                lastOutcome = "推托",
                expiresAtMs = System.currentTimeMillis() + 15_000L,
            ),
            onAccept = {},
            onDefer = {},
            onTimeout = {},
        )
    }
}
