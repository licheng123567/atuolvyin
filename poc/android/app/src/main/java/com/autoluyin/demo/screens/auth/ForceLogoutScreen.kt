package com.autoluyin.demo.screens.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.autoluyin.demo.auth.ForceLogoutReason
import com.autoluyin.demo.ui.theme.Neutral900
import com.autoluyin.demo.ui.theme.Primary

/**
 * v2.0 Task 8 — Screen 9 强制退出全屏页 (Compose)。
 *
 * 视觉对齐 ui/app-agent.html Screen 9 (line 1460-1473) + CSS (line 808-866)。
 * 规格摘要：
 *  - 白底全屏，padding top=60dp / bottom=40dp / horizontal=32dp，column center
 *  - 80×80 圆形图标容器 #FEF2F2 + 2px #fca5a5 边框，emoji 锁居中
 *  - 标题 18sp bold，描述 13.5sp #4b5563（line-height ≈ 23sp）
 *  - "重新登录" 主按钮 — 蓝底 #1A56DB 圆角 12dp，padding 15dp，宽 100%
 *  - "联系管理员" 文字链 — 13sp 蓝下划线
 *
 * 动态文案：
 *  - 标题随 [ForceLogoutReason.code] 变化
 *  - 描述优先用后端 message，否则按 code 给默认文案
 *
 * 图标：选 emoji 🔒（minSdk 23 字体支持稳定，避免再引依赖）。
 */
@Composable
fun ForceLogoutScreen(
    reason: ForceLogoutReason,
    onRelogin: () -> Unit,
    onContactAdmin: () -> Unit,
) {
    val title = when (reason.code) {
        "ERR_SESSION_EVICTED" -> "账号已在其他设备登录"
        "ERR_TOKEN_EXPIRED" -> "登录已过期"
        else -> "登录失效，请重新登录"
    }
    val desc = reason.message?.takeIf { it.isNotBlank() } ?: when (reason.code) {
        "ERR_SESSION_EVICTED" -> "您的账号于其他设备登录，本设备已自动退出。"
        "ERR_TOKEN_EXPIRED" -> "登录会话已超过有效期，请重新登录。"
        else -> "登录信息已失效，请重新登录。"
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
            .systemBarsPadding(),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    start = 32.dp,
                    end = 32.dp,
                    top = 60.dp,
                    bottom = 40.dp,
                ),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Top,
        ) {
            // 80×80 浅红圆形图标容器
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(Color(0xFFFEF2F2))
                    .border(2.dp, Color(0xFFFCA5A5), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(text = "🔒", fontSize = 36.sp)
            }

            Spacer(Modifier.height(24.dp))

            Text(
                text = title,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Neutral900,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(14.dp))

            Text(
                text = desc,
                fontSize = 13.5.sp,
                color = Color(0xFF4B5563),
                textAlign = TextAlign.Center,
                lineHeight = 23.sp,
            )

            Spacer(Modifier.height(10.dp))

            Text(
                text = "如非您本人操作，请立即修改密码以保护账号安全。",
                fontSize = 12.sp,
                color = Color(0xFF9CA3AF),
                textAlign = TextAlign.Center,
            )

            // 占位推按钮到下半部（与设计稿 36dp + 自然撑开一致）
            Spacer(Modifier.weight(1f))

            Button(
                onClick = onRelogin,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Primary,
                    contentColor = Color.White,
                ),
                shape = RoundedCornerShape(12.dp),
                contentPadding = PaddingValues(vertical = 15.dp),
            ) {
                Text(
                    text = "重新登录",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }

            Spacer(Modifier.height(16.dp))

            Text(
                text = "联系管理员",
                fontSize = 13.sp,
                color = Primary,
                textDecoration = TextDecoration.Underline,
                modifier = Modifier
                    .clickable { onContactAdmin() }
                    .padding(vertical = 4.dp),
            )
        }
    }
}
