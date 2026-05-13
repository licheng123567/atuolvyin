package com.autoluyin.demo.onboarding

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.capability.DeviceCapabilityProbe
import com.autoluyin.demo.ui.theme.Neutral100
import com.autoluyin.demo.ui.theme.Neutral200
import com.autoluyin.demo.ui.theme.Neutral400
import com.autoluyin.demo.ui.theme.Neutral600
import com.autoluyin.demo.ui.theme.Neutral700
import com.autoluyin.demo.ui.theme.Neutral900
import com.autoluyin.demo.ui.theme.Primary
import com.autoluyin.demo.ui.theme.PrimaryHover
import com.autoluyin.demo.ui.theme.PrimaryLight
import com.autoluyin.demo.ui.theme.Success
import com.autoluyin.demo.ui.theme.SuccessLight
import com.autoluyin.demo.ui.theme.Surface
import com.autoluyin.demo.ui.theme.Warning
import com.autoluyin.demo.ui.theme.WarningLight
import kotlinx.coroutines.flow.SharedFlow

/**
 * v2.1 Task 5 — Onboarding Wizard 4 步骤主屏。
 *
 * 进度条（顶部）→ 步骤内容（可滚动）→ 底部上一步/下一步导航。
 * 每步推进条件由 [OnboardingState.canGoNext] 计算；下一步按钮 disable 当条件不满足。
 */
@Composable
fun OnboardingScreen(
    permissionsResult: SharedFlow<Boolean>,
    onComplete: () -> Unit,
    onRequestPermissions: () -> Unit,
    onOpenSystemSettings: () -> Unit,
    onSaveBackendUrl: (String) -> Boolean,
    arePermissionsGranted: () -> Boolean,
) {
    val ctx = LocalContext.current

    // 静态本地能力预测（无需调后端 — 真实 self-check 在登录后由 MainActivity 触发）
    val devicePreview = remember { DeviceCapabilityProbe.collect() }
    val romHint = remember(devicePreview) { detectRomHint(devicePreview.manufacturer, devicePreview.brand) }

    var state by remember {
        mutableStateOf(
            OnboardingState(
                currentStep = Step.Permissions,
                permissionsGranted = arePermissionsGranted(),
                backendUrl = AppConfig.backendUrl(ctx).orEmpty(),
                backendUrlSaved = !AppConfig.backendUrl(ctx).isNullOrBlank(),
                recordingConfirmed = false,
                romHint = romHint,
            ),
        )
    }

    // 监听权限申请回调
    LaunchedEffect(Unit) {
        permissionsResult.collect { _ ->
            state = state.copy(permissionsGranted = arePermissionsGranted())
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Neutral100)
            .systemBarsPadding(),
    ) {
        // ── 顶部 ──
        OnboardingHeader(currentStep = state.currentStep)
        StepProgressBar(
            currentStep = state.currentStep,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 16.dp),
        )

        // ── 内容 ──
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 24.dp),
        ) {
            when (state.currentStep) {
                Step.Permissions -> StepPermissionsScreen(
                    granted = state.permissionsGranted,
                    onGrantClick = onRequestPermissions,
                )
                Step.BackendUrl -> StepBackendUrlScreen(
                    initialUrl = state.backendUrl,
                    saved = state.backendUrlSaved,
                    onSave = { url ->
                        if (onSaveBackendUrl(url)) {
                            state = state.copy(backendUrl = url, backendUrlSaved = true)
                        } else {
                            state = state.copy(backendUrlSaved = false)
                        }
                    },
                    onUrlChanged = { url ->
                        // 用户重新编辑就清掉"已保存"状态
                        state = state.copy(backendUrl = url, backendUrlSaved = false)
                    },
                )
                Step.RecordingSetup -> StepRecordingSetupScreen(
                    romHint = state.romHint,
                    confirmed = state.recordingConfirmed,
                    onOpenSettings = onOpenSystemSettings,
                    onConfirmedChange = { state = state.copy(recordingConfirmed = it) },
                )
                Step.Done -> StepDoneScreen()
            }
        }

        // ── 底部导航 ──
        BottomNav(
            currentStep = state.currentStep,
            canGoNext = state.canGoNext(),
            onPrev = {
                state.currentStep.prev()?.let {
                    state = state.copy(currentStep = it)
                }
            },
            onNext = {
                val next = state.currentStep.next()
                if (next != null) {
                    state = state.copy(currentStep = next)
                } else {
                    onComplete()
                }
            },
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────

private enum class Step(val label: String, val title: String) {
    Permissions("权限", "授予权限"),
    BackendUrl("地址", "配置后端地址"),
    RecordingSetup("录音", "配置通话录音"),
    Done("完成", "准备完成"),
}

private fun Step.next(): Step? = when (this) {
    Step.Permissions -> Step.BackendUrl
    Step.BackendUrl -> Step.RecordingSetup
    Step.RecordingSetup -> Step.Done
    Step.Done -> null
}

private fun Step.prev(): Step? = when (this) {
    Step.Permissions -> null
    Step.BackendUrl -> Step.Permissions
    Step.RecordingSetup -> Step.BackendUrl
    Step.Done -> Step.RecordingSetup
}

private data class OnboardingState(
    val currentStep: Step,
    val permissionsGranted: Boolean,
    val backendUrl: String,
    val backendUrlSaved: Boolean,
    val recordingConfirmed: Boolean,
    val romHint: String,
) {
    fun canGoNext(): Boolean = when (currentStep) {
        Step.Permissions -> permissionsGranted
        Step.BackendUrl -> backendUrlSaved && backendUrl.isNotBlank()
        Step.RecordingSetup -> recordingConfirmed
        Step.Done -> true
    }
}

/**
 * 静态本地 ROM 推断 — 仅 step 3 文案使用。
 * 真实 capability 判定在后端 services/device_capability.py 静态矩阵，
 * 由登录后 self-check 完成（MainActivity 已实现）。
 */
private fun detectRomHint(manufacturer: String, brand: String): String {
    val m = (manufacturer + " " + brand).lowercase()
    return when {
        m.contains("xiaomi") || m.contains("redmi") -> "MIUI / HyperOS"
        m.contains("huawei") -> "EMUI / HarmonyOS"
        m.contains("honor") -> "MagicOS"
        m.contains("oppo") -> "ColorOS"
        m.contains("vivo") -> "OriginOS / Funtouch"
        m.contains("oneplus") -> "OxygenOS"
        m.contains("samsung") -> "One UI"
        else -> "通用 Android"
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Header / Progress
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun OnboardingHeader(currentStep: Step) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface)
            .padding(horizontal = 24.dp, vertical = 16.dp),
    ) {
        Text(
            text = "有证慧催",
            color = Primary,
            fontWeight = FontWeight.SemiBold,
            fontSize = 16.sp,
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = "首次使用 · ${currentStep.title}",
            color = Neutral600,
            fontSize = 13.sp,
        )
    }
}

@Composable
private fun StepProgressBar(currentStep: Step, modifier: Modifier = Modifier) {
    val steps = Step.values()
    val currentIndex = steps.indexOf(currentStep)
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        steps.forEachIndexed { idx, _ ->
            val active = idx <= currentIndex
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(if (active) Primary else Neutral200),
            )
        }
    }
    Row(
        modifier = modifier.padding(top = 0.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        steps.forEachIndexed { idx, step ->
            val active = idx <= currentIndex
            Text(
                text = "${idx + 1}. ${step.label}",
                color = if (active) Primary else Neutral400,
                fontSize = 12.sp,
                fontWeight = if (idx == currentIndex) FontWeight.SemiBold else FontWeight.Normal,
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 — Permissions
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun StepPermissionsScreen(
    granted: Boolean,
    onGrantClick: () -> Unit,
) {
    val scroll = rememberScrollState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(top = 24.dp, bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        StepIconCircle(icon = Icons.Filled.Shield, tint = Primary, bg = PrimaryLight)
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            text = "授予 App 必要权限",
            color = Neutral900,
            fontSize = 20.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "为完成自动外呼录音，App 需要以下权限",
            color = Neutral600,
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(24.dp))
        Card {
            PermissionRow("电话与拨号", "拨打号码、读取通话状态、读取通话记录用于匹配录音")
            DividerLine()
            PermissionRow("麦克风录音", "实时通话流式上传需要采集音频流")
            DividerLine()
            PermissionRow("相机", "扫码拨号备份方案需要相机扫描二维码")
            DividerLine()
            PermissionRow("音频文件读取", "读取系统通话录音目录中的音频文件")
            DividerLine()
            PermissionRow("通知权限", "前台服务保活与拨号请求弹窗需要通知权限")
        }
        Spacer(modifier = Modifier.height(24.dp))
        Button(
            onClick = onGrantClick,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                contentColor = Surface,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text(
                text = if (granted) "权限已全部授予" else "授予权限",
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        if (granted) {
            Spacer(modifier = Modifier.height(12.dp))
            StatusBanner(
                text = "已授予所需权限，可继续下一步",
                bg = SuccessLight,
                fg = Success,
                icon = Icons.Filled.CheckCircle,
            )
        } else {
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "如有权限被拒，可在系统设置中重新开启",
                color = Neutral400,
                fontSize = 12.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — Backend URL
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun StepBackendUrlScreen(
    initialUrl: String,
    saved: Boolean,
    onSave: (String) -> Unit,
    onUrlChanged: (String) -> Unit,
) {
    var text by remember { mutableStateOf(initialUrl) }
    var saveError by remember { mutableStateOf<String?>(null) }
    val scroll = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(top = 24.dp, bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        StepIconCircle(icon = Icons.Filled.Storage, tint = Primary, bg = PrimaryLight)
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            text = "配置后端服务器地址",
            color = Neutral900,
            fontSize = 20.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "由管理员告知；上线后改地址不需要重装 App",
            color = Neutral600,
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(24.dp))

        OutlinedTextField(
            value = text,
            onValueChange = {
                text = it
                saveError = null
                onUrlChanged(it)
            },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("后端地址") },
            placeholder = { Text("http://192.168.1.10:18000") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Primary,
                unfocusedBorderColor = Neutral200,
            ),
            isError = saveError != null,
        )
        if (saveError != null) {
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = saveError ?: "",
                color = com.autoluyin.demo.ui.theme.DebtRed,
                fontSize = 12.sp,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Spacer(modifier = Modifier.height(20.dp))
        Button(
            onClick = {
                val v = text.trim()
                if (v.isBlank() || !(v.startsWith("http://") || v.startsWith("https://"))) {
                    saveError = "地址必须以 http:// 或 https:// 开头"
                } else {
                    saveError = null
                    onSave(v)
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                contentColor = Surface,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text(
                text = if (saved) "已保存（如需修改重新输入）" else "保存",
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        if (saved) {
            Spacer(modifier = Modifier.height(12.dp))
            StatusBanner(
                text = "地址已配置，可继续下一步",
                bg = SuccessLight,
                fg = Success,
                icon = Icons.Filled.CheckCircle,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 3 — Recording Setup（核心步骤）
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun StepRecordingSetupScreen(
    romHint: String,
    confirmed: Boolean,
    onOpenSettings: () -> Unit,
    onConfirmedChange: (Boolean) -> Unit,
) {
    val ctx = LocalContext.current
    val scroll = rememberScrollState()

    // v2.2 Module A — SAF 手选录音目录。
    // 静态候选目录在某些 ROM / 厂商定制版本上覆盖不到，给用户兜底入口。
    var savedDirLabel by remember {
        mutableStateOf(
            AppConfig.getUserRecordingDirUri(ctx)
                ?.let { Uri.parse(it).lastPathSegment }
                .orEmpty(),
        )
    }
    val pickDirLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree(),
    ) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                ctx.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION,
                )
                AppConfig.saveUserRecordingDirUri(ctx, uri.toString())
                savedDirLabel = uri.lastPathSegment.orEmpty()
                Toast.makeText(ctx, "已保存：${uri.lastPathSegment}", Toast.LENGTH_LONG).show()
            }.onFailure {
                Toast.makeText(ctx, "保存目录失败：${it.message}", Toast.LENGTH_LONG).show()
            }
        }
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(top = 24.dp, bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        StepIconCircle(icon = Icons.Filled.Mic, tint = Primary, bg = PrimaryLight)
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            text = "开启系统通话自动录音",
            color = Neutral900,
            fontSize = 20.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "本机：$romHint",
            color = Neutral600,
            fontSize = 14.sp,
        )
        Spacer(modifier = Modifier.height(20.dp))

        // 通用引导 banner（真实 capability 由登录后 self-check 给出）
        StatusBanner(
            text = "登录后 App 会自动检测设备录音能力；当前请先确保系统侧已开启通话录音",
            bg = WarningLight,
            fg = Warning,
            icon = null,
        )

        Spacer(modifier = Modifier.height(20.dp))
        Card {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "操作步骤",
                    color = Neutral900,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(12.dp))
                StepInstruction("1", "打开手机「系统设置」")
                Spacer(modifier = Modifier.height(8.dp))
                StepInstruction("2", "进入「应用」→「电话」→「通话设置」")
                Spacer(modifier = Modifier.height(8.dp))
                StepInstruction("3", "找到「通话自动录音」并打开开关")
                Spacer(modifier = Modifier.height(8.dp))
                StepInstruction("4", "选择「自动录音所有通话」")
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        OutlinedButton(
            onClick = onOpenSettings,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(12.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, Primary),
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = null,
                tint = Primary,
                modifier = Modifier.size(18.dp),
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "打开系统设置",
                color = Primary,
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }

        Spacer(modifier = Modifier.height(20.dp))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(Surface)
                .border(1.dp, if (confirmed) Primary else Neutral200, RoundedCornerShape(12.dp))
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(
                checked = confirmed,
                onCheckedChange = onConfirmedChange,
                colors = CheckboxDefaults.colors(checkedColor = Primary),
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = "我已开启系统通话自动录音",
                color = Neutral900,
                fontSize = 14.sp,
                modifier = Modifier.weight(1f),
            )
        }

        // v2.2 Module A — SAF 兜底入口：自动扫描找不到目录时让用户手选。
        Spacer(modifier = Modifier.height(16.dp))
        OutlinedButton(
            onClick = { pickDirLauncher.launch(null) },
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp),
            shape = RoundedCornerShape(12.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, Neutral400),
        ) {
            Icon(
                imageVector = Icons.Filled.FolderOpen,
                contentDescription = null,
                tint = Neutral700,
                modifier = Modifier.size(18.dp),
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "找不到？手动选择录音目录",
                color = Neutral700,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        if (savedDirLabel.isNotBlank()) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "已保存目录：$savedDirLabel",
                color = Success,
                fontSize = 12.sp,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 4 — Done
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun StepDoneScreen() {
    val scroll = rememberScrollState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(top = 24.dp, bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        StepIconCircle(icon = Icons.Filled.CheckCircle, tint = Success, bg = SuccessLight)
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            text = "准备完成！",
            color = Neutral900,
            fontSize = 22.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "接下来请使用您的工号登录开始使用",
            color = Neutral600,
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(24.dp))
        Card {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "已完成的初始化",
                    color = Neutral900,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(12.dp))
                ChecklistRow("权限授予")
                Spacer(modifier = Modifier.height(8.dp))
                ChecklistRow("后端地址")
                Spacer(modifier = Modifier.height(8.dp))
                ChecklistRow("系统通话录音确认")
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        StatusBanner(
            text = "登录后 App 会自动完成设备录音能力自检",
            bg = PrimaryLight,
            fg = Primary,
            icon = null,
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Bottom navigation
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun BottomNav(
    currentStep: Step,
    canGoNext: Boolean,
    onPrev: () -> Unit,
    onNext: () -> Unit,
) {
    val canGoPrev = currentStep.prev() != null
    val isLast = currentStep == Step.Done
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface)
            .padding(horizontal = 24.dp, vertical = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TextButton(
            onClick = onPrev,
            enabled = canGoPrev,
            modifier = Modifier.height(48.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.ChevronLeft,
                contentDescription = null,
                tint = if (canGoPrev) Primary else Neutral400,
                modifier = Modifier.size(20.dp),
            )
            Text(
                text = "上一步",
                color = if (canGoPrev) Primary else Neutral400,
                fontSize = 15.sp,
            )
        }
        Spacer(modifier = Modifier.weight(1f))
        Button(
            onClick = onNext,
            enabled = canGoNext,
            modifier = Modifier
                .heightIn(min = 48.dp)
                .width(160.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                contentColor = Surface,
                disabledContainerColor = Neutral200,
                disabledContentColor = Neutral400,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text(
                text = if (isLast) "完成" else "下一步",
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reusable bits
// ─────────────────────────────────────────────────────────────────────────────

@Composable
private fun StepIconCircle(icon: ImageVector, tint: Color, bg: Color) {
    Box(
        modifier = Modifier
            .size(72.dp)
            .clip(CircleShape)
            .background(bg),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(36.dp),
        )
    }
}

@Composable
private fun Card(content: @Composable () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Surface)
            .border(1.dp, Neutral200, RoundedCornerShape(12.dp)),
    ) {
        Column { content() }
    }
}

@Composable
private fun PermissionRow(title: String, desc: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Text(
            text = title,
            color = Neutral900,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = desc,
            color = Neutral600,
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun DividerLine() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(Neutral200),
    )
}

@Composable
private fun StepInstruction(num: String, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(24.dp)
                .clip(CircleShape)
                .background(PrimaryLight),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = num,
                color = Primary,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        Spacer(modifier = Modifier.width(10.dp))
        Text(
            text = text,
            color = Neutral700,
            fontSize = 14.sp,
        )
    }
}

@Composable
private fun ChecklistRow(text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            imageVector = Icons.Filled.CheckCircle,
            contentDescription = null,
            tint = Success,
            modifier = Modifier.size(18.dp),
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = text,
            color = Neutral700,
            fontSize = 14.sp,
        )
    }
}

@Composable
private fun StatusBanner(
    text: String,
    bg: Color,
    fg: Color,
    icon: ImageVector?,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = fg,
                modifier = Modifier.size(18.dp),
            )
            Spacer(modifier = Modifier.width(8.dp))
        }
        Text(
            text = text,
            color = fg,
            fontSize = 13.sp,
            modifier = Modifier.weight(1f),
        )
    }
}
