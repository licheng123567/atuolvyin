package com.autoluyin.demo.screens.realtime

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * v2.0 Task 6 — 7 根脉动绿条波形指示器。
 *
 * 设计稿映射 (ui/app-agent.html line 419-441)：
 *   bar height base：12 / 20 / 32 / 24 / 38 / 28 / 16 dp
 *   delay：0 / 100 / 200 / 300 / 100 / 250 / 150 ms
 *   动画周期 1.2s ease-in-out，scaleY 1→1.8 反复
 *
 * Compose 实现：每根 bar 用 [animateFloat] 在 [base*0.4, base] 之间反复，
 * 配合 `infiniteRepeatable(reverse)`；颜色固定 `#22C55E`（success-green）。
 *
 * 仅在 connectionState == NORMAL 时由 RealtimeCallScreen 调用渲染。
 */
@Composable
fun WaveformIndicator(modifier: Modifier = Modifier) {
    // 基础高度 & 相位偏移（dp / ms）— 与设计稿 nth-child 严格对齐
    val barSpecs = listOf(
        12 to 0,
        20 to 100,
        32 to 200,
        24 to 300,
        38 to 100,
        28 to 250,
        16 to 150,
    )
    val infiniteTransition = rememberInfiniteTransition(label = "waveform")
    val animatedHeights = barSpecs.mapIndexed { index, (base, delay) ->
        val anim by infiniteTransition.animateFloat(
            initialValue = base * 0.55f,
            targetValue = base.toFloat(),
            animationSpec = infiniteRepeatable(
                animation = tween(
                    durationMillis = 600,
                    delayMillis = delay,
                    easing = FastOutSlowInEasing,
                ),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "waveform-bar-$index",
        )
        anim
    }
    Row(
        modifier = modifier.height(40.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        animatedHeights.forEach { h ->
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .height(h.dp)
                    .background(WaveformGreen, RoundedCornerShape(2.dp)),
            )
        }
    }
}

private val WaveformGreen = Color(0xFF22C55E)
