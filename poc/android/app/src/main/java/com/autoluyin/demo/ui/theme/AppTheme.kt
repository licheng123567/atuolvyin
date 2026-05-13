package com.autoluyin.demo.ui.theme

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface as M3Surface
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

/**
 * v2.0 Task 1 — App-wide Material 3 主题。
 *
 * 把 design-system.css 翻译过来的 token 映射到 Material 3 ColorScheme。
 * 后续 Task 2-9 所有 Compose UI 都用 `AppTheme { ... }` 包裹。
 *
 * 暂不支持 Dark theme（design token 没要求；二期再加）。
 */
private val AppLightColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = Surface,
    primaryContainer = PrimaryLight,
    onPrimaryContainer = PrimaryHover,

    error = DebtRed,
    onError = Surface,
    errorContainer = DebtRedLight,
    onErrorContainer = DebtRed,

    background = Neutral100,           // 页面背景
    onBackground = Neutral900,

    surface = Surface,
    onSurface = Neutral900,
    surfaceVariant = Neutral50,
    onSurfaceVariant = Neutral700,

    outline = Neutral300,
    outlineVariant = Neutral200,
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AppLightColorScheme,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}

// ---------------------------------------------------------------------------
// Preview — 不参与生产代码，仅用于 IDE / 渲染验证主题装配是否正确。
// ---------------------------------------------------------------------------
@Preview(showBackground = true)
@Composable
private fun AppThemePreview() {
    AppTheme {
        M3Surface {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("有证慧催", style = MaterialTheme.typography.headlineMedium)
                Text("Material 3 主题装配预览", style = MaterialTheme.typography.bodyMedium)
                Text(
                    "primary / onSurface / surfaceVariant 都已挂载",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
