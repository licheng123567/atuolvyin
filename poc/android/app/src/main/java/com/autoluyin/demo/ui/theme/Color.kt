package com.autoluyin.demo.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * v2.0 Task 1 — Design Token (Color)
 *
 * 翻译自 ui/assets/design-system.css 的 :root 变量。
 * 此文件是 Compose 端的唯一颜色来源，禁止在 UI 代码里硬编码 Color(0xFF...)。
 */

// ---- Brand ----
val Primary = Color(0xFF1A56DB)        // --color-primary
val PrimaryHover = Color(0xFF1E429F)   // --color-primary-hover
val PrimaryLight = Color(0xFFEBF5FF)   // --color-primary-light

// ---- Semantic ----
val DebtRed = Color(0xFFE02424)        // --color-danger
val DebtRedLight = Color(0xFFFDF2F2)   // --color-danger-light
val Warning = Color(0xFFD97706)        // --color-warning
val WarningLight = Color(0xFFFFFBEB)   // --color-warning-light
val Success = Color(0xFF057A55)        // --color-success
val SuccessLight = Color(0xFFF0FDF4)   // --color-success-light
val Purple = Color(0xFF7E3AF2)         // --color-purple
val PurpleLight = Color(0xFFF5F3FF)    // --color-purple-light

// ---- Neutrals (9 档) ----
val Neutral900 = Color(0xFF111827)
val Neutral700 = Color(0xFF374151)
val Neutral600 = Color(0xFF4B5563)
val Neutral400 = Color(0xFF9CA3AF)
val Neutral300 = Color(0xFFD1D5DB)
val Neutral200 = Color(0xFFE5E7EB)
val Neutral100 = Color(0xFFF3F4F6)
val Neutral50 = Color(0xFFF9FAFB)

// ---- Surface ----
val Surface = Color(0xFFFFFFFF)        // --color-surface

// ---- Chat bubbles ----
val AgentBubble = Color(0xFFDBEAFE)    // --color-agent-bubble
val OwnerBubble = Color(0xFFF3F4F6)    // --color-owner-bubble
