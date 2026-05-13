package com.autoluyin.demo.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * v2.0 Task 1 — Design Token (Shape)
 *
 * 翻译自 design-system.css 的 --radius-* 变量。
 *
 *   small      4dp  ← --radius-sm
 *   medium     8dp  ← --radius-lg
 *   large     12dp  ← --radius-xl
 *   extraLarge 16dp ← --radius-2xl
 *
 * 注：Material 3 默认没有 6dp 档（--radius-md），调用方需要时用 RoundedCornerShape(6.dp) 即可。
 */
val AppShapes = Shapes(
    small = RoundedCornerShape(4.dp),
    medium = RoundedCornerShape(8.dp),
    large = RoundedCornerShape(12.dp),
    extraLarge = RoundedCornerShape(16.dp),
)

/** 来电屏专用大圆角（spec 要求额外暴露）。 */
val Shape20 = RoundedCornerShape(20.dp)
