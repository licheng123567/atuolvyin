package com.autoluyin.demo

import android.Manifest
import android.content.*
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.text.InputType
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.capability.DeviceCapabilityProbe
import com.autoluyin.demo.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val adapter = CaseAdapter(::onCallClick)

    // v1.6 — self-check 闸门：失败时禁用所有呼叫入口，避免脏录音上传
    private var canCall: Boolean = false
    private var lastFailReasons: List<String> = emptyList()

    private val uploadDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, i: Intent?) {
            val callId = i?.getLongExtra("call_id", -1) ?: -1
            if (callId > 0) toast("通话已上传 #$callId")
        }
    }

    private val permLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            ensureBackendUrlThen { doSelfCheck() }
        }

    // v2.2 — Android < 11 (R) 没有 MANAGE_EXTERNAL_STORAGE，用 SAF 手选录音目录兜底
    private val pickRecordingDirLauncher =
        registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri != null) {
                runCatching {
                    contentResolver.takePersistableUriPermission(
                        uri,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION,
                    )
                    AppConfig.saveUserRecordingDirUri(this, uri.toString())
                    toast("已保存录音目录：${uri.lastPathSegment ?: uri}")
                    // 立刻重跑自检
                    doSelfCheck()
                }.onFailure { toast("保存失败：${it.message}") }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // v2.1 Task 5 — 首次安装跳转到 Onboarding Wizard。
        // 条件：onboarding 未完成 AND 未登录（避免老用户升级后误触）。
        // Onboarding 完成后会 markOnboardingDone + 重新启动 MainActivity，进入 preflight 流程。
        if (!AppConfig.isOnboardingDone(this) && AppConfig.jwtToken(this) == null) {
            com.autoluyin.demo.onboarding.OnboardingActivity.start(this)
            finish()
            return
        }

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Provide application context to ApiClient for service accessor
        ApiClient.appContext = applicationContext

        binding.tasks.layoutManager = LinearLayoutManager(this)
        binding.tasks.adapter = adapter

        binding.btnSelfCheck.setOnClickListener { ensurePermsThenCheck() }
        binding.btnRefresh.setOnClickListener { loadTasks() }
        binding.btnGrantStorage.setOnClickListener { openManageAllFiles() }
        binding.btnServerUrl.setOnClickListener { showBackendUrlDialog() }
        binding.btnScanQr.setOnClickListener {
            startActivity(Intent(this, com.autoluyin.demo.scan.QrScanActivity::class.java))
        }
        binding.btnPerf.setOnClickListener {
            startActivity(Intent(this, MyPerformanceActivity::class.java))
        }
        binding.btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        ensurePermsThenCheck()

        // MiPush registration — only when real App ID/Key are provisioned
        // TODO: Sprint 4 MiPush — enable when AAR provisioned
        val miPushAppId = BuildConfig.MIPUSH_APP_ID
        val miPushAppKey = BuildConfig.MIPUSH_APP_KEY
        if (miPushAppId.isNotBlank() && miPushAppKey.isNotBlank()) {
            // com.xiaomi.mipush.sdk.MiPushClient.registerPush(applicationContext, miPushAppId, miPushAppKey)
        }
    }

    override fun onResume() {
        super.onResume()
        ContextCompat.registerReceiver(
            this, uploadDoneReceiver,
            IntentFilter("com.autoluyin.demo.UPLOAD_DONE"),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    override fun onPause() {
        unregisterReceiver(uploadDoneReceiver)
        super.onPause()
    }

    // ---------- 后端地址 ----------
    private fun ensureBackendUrlThen(next: () -> Unit) {
        val url = AppConfig.backendUrl(this)
        if (url.isNullOrBlank()) {
            showBackendUrlDialog(onSaved = next)
        } else if (AppConfig.jwtToken(this) == null) {
            showLoginDialog()
        } else {
            renderHeader()
            next()
        }
    }

    private fun showBackendUrlDialog(onSaved: (() -> Unit)? = null) {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            hint = "例如 http://192.168.1.10:18000 或 https://api.your-domain.com"
            setText(AppConfig.backendUrl(this@MainActivity).orEmpty())
        }
        AlertDialog.Builder(this)
            .setTitle("配置后端地址")
            .setMessage("管理员告知的服务器地址；已上线后改地址不需要重装 App")
            .setView(input)
            .setPositiveButton("保存") { _, _ ->
                val v = input.text.toString().trim()
                if (v.isBlank() || !(v.startsWith("http://") || v.startsWith("https://"))) {
                    toast("地址必须以 http:// 或 https:// 开头"); return@setPositiveButton
                }
                AppConfig.saveBackendUrl(this, v)
                renderHeader()
                onSaved?.invoke() ?: doSelfCheck()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    // ---------- 登录 ----------
    // v2.2 Module C — 倒计时 job；dialog 关闭/重建时取消，避免 Activity 泄漏 + 复位
    private var otpCountdownJob: kotlinx.coroutines.Job? = null

    private fun showLoginDialog() {
        // 复位上一次的倒计时（重新进入登录页要复位）
        otpCountdownJob?.cancel()
        otpCountdownJob = null

        // 共享：手机号输入框（两个 tab 之间复用同一份 state）
        val phoneInput = android.widget.EditText(this).apply {
            hint = "手机号"
            inputType = android.text.InputType.TYPE_CLASS_PHONE
        }

        // 密码 tab 内容
        val pwdInput = android.widget.EditText(this).apply {
            hint = "密码"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                    android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val pwdPane = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(pwdInput)
        }

        // 验证码 tab 内容
        val otpInput = android.widget.EditText(this).apply {
            hint = "6 位验证码"
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
        }
        val btnSendOtp = android.widget.Button(this).apply {
            text = "获取验证码"
        }
        val otpPane = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(btnSendOtp)
            addView(otpInput)
            visibility = android.view.View.GONE
        }

        // Tab 切换按钮（用两个 Button 模拟 TabRow，AlertDialog 不便用 Compose TabRow）
        val tabPwd = android.widget.Button(this).apply { text = "密码登录" }
        val tabOtp = android.widget.Button(this).apply { text = "验证码登录" }
        val tabRow = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            val lp = android.widget.LinearLayout.LayoutParams(
                0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f
            )
            addView(tabPwd, lp)
            addView(tabOtp, lp)
        }

        // 当前 tab：0=密码，1=验证码
        var currentTab = 0
        fun applyTabStyle() {
            tabPwd.alpha = if (currentTab == 0) 1.0f else 0.5f
            tabOtp.alpha = if (currentTab == 1) 1.0f else 0.5f
            pwdPane.visibility = if (currentTab == 0) android.view.View.VISIBLE else android.view.View.GONE
            otpPane.visibility = if (currentTab == 1) android.view.View.VISIBLE else android.view.View.GONE
        }
        applyTabStyle()
        tabPwd.setOnClickListener { currentTab = 0; applyTabStyle() }
        tabOtp.setOnClickListener { currentTab = 1; applyTabStyle() }

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(48, 16, 48, 0)
            addView(tabRow)
            addView(phoneInput)
            addView(pwdPane)
            addView(otpPane)
        }

        // 倒计时：60s
        fun startOtpCountdown() {
            otpCountdownJob?.cancel()
            otpCountdownJob = lifecycleScope.launch {
                var remaining = 60
                btnSendOtp.isEnabled = false
                while (remaining > 0) {
                    btnSendOtp.text = "${remaining}s 后重发"
                    kotlinx.coroutines.delay(1000)
                    remaining--
                }
                btnSendOtp.text = "获取验证码"
                btnSendOtp.isEnabled = true
            }
        }

        // 发送验证码
        btnSendOtp.setOnClickListener {
            val phone = phoneInput.text.toString().trim()
            if (phone.length != 11) {
                toast("请填入 11 位手机号"); return@setOnClickListener
            }
            btnSendOtp.isEnabled = false
            lifecycleScope.launch {
                try {
                    val resp = ApiClient.get(this@MainActivity).sendOtp(OtpSendReq(phone = phone))
                    if (resp.isSuccessful) {
                        toast("验证码已发送，请查收（开发模式可见后端日志）")
                        startOtpCountdown()
                    } else {
                        btnSendOtp.isEnabled = true
                        val msg = parseErrorMessage(resp.errorBody()?.string())
                        toast("获取验证码失败：$msg")
                    }
                } catch (t: Throwable) {
                    btnSendOtp.isEnabled = true
                    toast("获取验证码失败：${t.message}")
                }
            }
        }

        val dialog = AlertDialog.Builder(this)
            .setTitle("登录")
            .setView(layout)
            .setPositiveButton("登录", null)  // 先 null，下面手动接管避免点击后立刻关闭
            .setNegativeButton("取消", null)
            .create()
        dialog.setOnDismissListener {
            otpCountdownJob?.cancel()
            otpCountdownJob = null
        }
        dialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            val phone = phoneInput.text.toString().trim()
            if (currentTab == 0) {
                // 密码登录
                val pwd = pwdInput.text.toString()
                lifecycleScope.launch {
                    try {
                        val resp = ApiClient.get(this@MainActivity)
                            .login(LoginReq(phone = phone, password = pwd))
                        AppConfig.saveJwtToken(this@MainActivity, resp.access_token)
                        ApiClient.invalidate()
                        dialog.dismiss()
                        doSelfCheck()
                    } catch (t: Throwable) {
                        toast("登录失败: ${t.message}")
                    }
                }
            } else {
                // 验证码登录
                val code = otpInput.text.toString().trim()
                if (phone.length != 11) {
                    toast("请填入 11 位手机号"); return@setOnClickListener
                }
                if (code.length < 4) {
                    toast("请输入验证码"); return@setOnClickListener
                }
                lifecycleScope.launch {
                    try {
                        val resp = ApiClient.get(this@MainActivity)
                            .verifyOtp(OtpVerifyReq(phone = phone, code = code))
                        if (resp.isSuccessful && resp.body() != null) {
                            AppConfig.saveJwtToken(this@MainActivity, resp.body()!!.access_token)
                            ApiClient.invalidate()
                            dialog.dismiss()
                            doSelfCheck()
                        } else {
                            val msg = parseErrorMessage(resp.errorBody()?.string())
                            toast("登录失败：$msg")
                        }
                    } catch (t: Throwable) {
                        toast("登录失败：${t.message}")
                    }
                }
            }
        }
    }

    /** 后端错误体形如 {"detail": {"code": "...", "message": "..."}}；尽力提取 message。 */
    private fun parseErrorMessage(body: String?): String {
        if (body.isNullOrBlank()) return "请求失败"
        return try {
            val root = org.json.JSONObject(body)
            val detail = root.opt("detail")
            when (detail) {
                is org.json.JSONObject -> detail.optString("message", detail.toString())
                is String -> detail
                else -> body
            }
        } catch (_: Throwable) {
            body
        }
    }

    // ---------- 权限 ----------
    private fun ensurePermsThenCheck() {
        val needed = mutableListOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            // v1.9.9 — 实时通话流式上传必需（AudioRecord）；扫码必需（相机）
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            needed += Manifest.permission.READ_MEDIA_AUDIO
            needed += Manifest.permission.POST_NOTIFICATIONS
        } else {
            needed += Manifest.permission.READ_EXTERNAL_STORAGE
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) permLauncher.launch(missing.toTypedArray())
        else ensureBackendUrlThen { doSelfCheck() }
    }

    private fun openManageAllFiles() {
        // v2.2 — 提供两种路径让用户选：
        //   1. 系统级 MANAGE_EXTERNAL_STORAGE（仅 Android 11+ / R 可用）
        //   2. SAF 手选目录（< R 唯一可用的方式，> R 也可作备选）
        // 弹一个 dialog 让用户选；如果是 Android < R 直接走 SAF（系统选项不可用）。
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            pickRecordingDirLauncher.launch(null)
            return
        }
        AlertDialog.Builder(this)
            .setTitle("授权录音文件访问")
            .setMessage("Android 11+ 推荐先授予「所有文件访问」让 App 自动扫描；如果系统不允许或自动扫描找不到，再用「手动选择目录」指定录音文件夹。")
            .setPositiveButton("授予所有文件") { _, _ ->
                startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:$packageName")))
            }
            .setNeutralButton("手动选择目录") { _, _ -> pickRecordingDirLauncher.launch(null) }
            .setNegativeButton("取消", null)
            .show()
    }

    // ---------- 自检 + 拉运行时配置 ----------
    // P1：登录后必须先 register → 才能 self-check（后端要求设备已注册否则 404）
    private suspend fun ensureDeviceRegistered() {
        val api = ApiClient.get(this@MainActivity)
        val token = AppConfig.jwtToken(this@MainActivity) ?: return
        runCatching {
            api.registerDevice(
                authHeader = "Bearer $token",
                body = RegisterDeviceRequest(
                    device_id = DeviceId.get(this@MainActivity),
                    brand = android.os.Build.BRAND,
                    model = android.os.Build.MODEL,
                    os_version = "Android ${android.os.Build.VERSION.RELEASE} (API ${android.os.Build.VERSION.SDK_INT})",
                    // MiPush stub 不可用 → push_reg_id 暂留 null；
                    // backend 上 COALESCE 保留旧值，未来 MiPush 真接入后再补上
                    push_reg_id = null,
                ),
            )
        }.onFailure {
            // 注册失败不抛断 self-check 流程；self-check 自己会 404，统一在那里报错
            android.util.Log.w("AutoluyinMain", "registerDevice failed: ${it.message}")
        }
    }

    private fun doSelfCheck() {
        renderHeader()
        val recDirs = RecordingScanner.listDirsExisting()

        // v2.2 Module A — 优先使用用户手选目录（SAF 持久化 URI）；
        // 命中即视为录音目录可用，不再依赖静态候选清单。
        val userUri = AppConfig.getUserRecordingDirUri(this)
        val userDirAccessible = if (userUri != null) {
            runCatching {
                val docFile = androidx.documentfile.provider.DocumentFile
                    .fromTreeUri(this, Uri.parse(userUri))
                docFile != null && docFile.exists() && docFile.canRead()
            }.getOrDefault(false)
        } else {
            false
        }

        val dirsExist = userDirAccessible || recDirs.isNotEmpty()
        val dirOk = dirsExist && (Build.VERSION.SDK_INT < Build.VERSION_CODES.R
                || Environment.isExternalStorageManager()
                || userDirAccessible)

        // v2.1 — 设备能力探测：采集 ROM/Android 字段 + 上次扫描失败标志
        val deviceInfo = DeviceCapabilityProbe.collect()
        val lastScanFailed = AppConfig.getLastRecordingScanFailed(this)

        lifecycleScope.launch {
            try {
                ensureDeviceRegistered()
                val api = ApiClient.get(this@MainActivity)
                val resp = api.selfCheck(SelfCheckReq(
                    device_id = DeviceId.get(this@MainActivity),
                    recording_dir_ok = dirOk,
                    recording_toggle_on = dirsExist,
                    permissions_ok = true,
                    manufacturer = deviceInfo.manufacturer.takeIf { it.isNotBlank() },
                    model = deviceInfo.model.takeIf { it.isNotBlank() },
                    android_version = deviceInfo.androidVersion.takeIf { it.isNotBlank() },
                    recording_toggle_self_reported = null,  // Task 5 onboarding 才填
                    last_recording_scan_failed = lastScanFailed,
                ))
                // 拉取后台运行时配置（候选目录、超时、prompt 版本…）
                runCatching {
                    val cfg = api.deviceConfig(DeviceId.get(this@MainActivity))
                    AppConfig.applyRuntime(this@MainActivity, cfg)
                }
                // v2.1 — 持久化能力判定（供 onboarding/拨号前展示降级提示用）
                AppConfig.saveCapability(
                    this@MainActivity,
                    capability = resp.recording_capability,
                    guidance = resp.guidance_text,
                    rom = resp.detected_rom,
                )
                renderHeader()

                canCall = resp.can_call
                lastFailReasons = resp.fail_reasons
                binding.btnRefresh.isEnabled = resp.can_call
                adapter.setCanCall(resp.can_call)
                renderHeader()
                // v2.2 — 自检失败也跳 HomeActivity（WebView 内的 home 屏会显示 capability banner，
                // 用户至少能看见正常 UI、点拨号会有"录音不可用，仍要拨吗"的 confirm）。
                // 此前 self-check 失败把用户卡在 MainActivity 看 toast，体验断裂。
                val why = resp.fail_reasons.joinToString("、") { reasonLabel(it) }
                if (!resp.can_call && why.isNotBlank()) {
                    toast("提示：$why；拨号前会再次确认")
                }
                startActivity(Intent(this@MainActivity, HomeActivity::class.java))
                finish()
            } catch (t: Throwable) {
                if (t.message?.contains("401") == true || t.message?.contains("403") == true) {
                    AppConfig.clearJwtToken(this@MainActivity)
                    ApiClient.invalidate()
                    showLoginDialog()
                } else {
                    toast("自检失败: ${t.message}")
                }
            }
        }
    }

    private fun renderHeader() {
        val recDirs = RecordingScanner.listDirsExisting()
        binding.statusText.text = buildString {
            append("后端：${AppConfig.backendUrl(this@MainActivity) ?: "未配置"}\n")
            append("设备：${RecordingScanner.deviceModel()}\n")
            append(RecordingScanner.osVersion()).append("\n")
            append("命中录音目录：${recDirs.joinToString().ifEmpty { "无（请检查系统通话录音是否开启）" }}\n")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                && !Environment.isExternalStorageManager()) {
                append("⚠️ 需要授予「所有文件访问权限」才能读 MIUI 录音目录\n")
            }
            // v1.6 — 把后端 self-check 的失败项可视化到 header
            if (canCall) {
                append("✅ 自检通过，可以呼叫\n")
            } else if (lastFailReasons.isNotEmpty()) {
                append("⛔ 自检未通过，需要修复：\n")
                lastFailReasons.forEach { append("  • ${reasonLabel(it)}\n") }
            }
        }
    }

    private fun loadTasks() {
        lifecycleScope.launch {
            try {
                val resp = ApiClient.get(this@MainActivity).myCases()
                adapter.submitCases(resp.items)
            } catch (t: Throwable) {
                if (t.message?.contains("401") == true || t.message?.contains("403") == true) {
                    AppConfig.clearJwtToken(this@MainActivity)
                    ApiClient.invalidate()
                    showLoginDialog()
                } else {
                    toast("加载案件失败: ${t.message}")
                }
            }
        }
    }

    private fun reasonLabel(code: String): String = when (code) {
        "recording_dir" -> "录音目录未命中"
        "recording_toggle" -> "系统通话录音未开启"
        "permissions" -> "必要权限未授予"
        else -> code
    }

    // ---------- 一键拨号（Sprint 11.1：拨号前预览）----------
    private fun onCallClick(c: CaseItem) {
        // v1.6 闸门：自检未通过禁止拨号；UI 已置灰，这里再兜底一道
        if (!canCall) {
            toast("自检未通过，请先重新自检")
            ensurePermsThenCheck()
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED) {
            toast("请先授予拨打电话权限"); return
        }
        if (AppConfig.backendUrl(this) == null) {
            toast("请先配置后端地址"); showBackendUrlDialog(); return
        }
        showPreDialPreview(c)
    }

    private fun showPreDialPreview(c: CaseItem) {
        val phone = c.owner.phone ?: c.owner.phone_masked
        val location = listOfNotNull(c.owner.building, c.owner.room).joinToString("")
        val tag = if (c.stage == "vote") "[投票邀请]" else "[催收]"
        val msg = buildString {
            append("$tag ${c.owner.name}\n")
            if (location.isNotBlank()) append("地址：$location\n")
            append("电话：$phone\n")
            if (c.stage != "vote") {
                append("欠款：${c.amount_owed ?: "-"}\n")
                append("逾期：${c.months_overdue ?: 0} 月\n")
            } else {
                append("阶段：${c.stage}\n")
            }
            append("\n确认要拨打吗？")
        }
        AlertDialog.Builder(this)
            .setTitle("拨号前预览")
            .setMessage(msg)
            .setPositiveButton("拨打") { _, _ ->
                CallWatcherService.start(this, c.id, phone)
                startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")))
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}

class CaseAdapter(
    private val onCall: (CaseItem) -> Unit,
) : RecyclerView.Adapter<CaseAdapter.VH>() {

    private val items = mutableListOf<CaseItem>()
    private var canCall: Boolean = false

    fun submitCases(list: List<CaseItem>) {
        items.clear(); items.addAll(list); notifyDataSetChanged()
    }
    fun findById(id: Long) = items.firstOrNull { it.id == id }

    /** v1.6 — self-check 通过前所有「呼叫」按钮置灰。 */
    fun setCanCall(enabled: Boolean) {
        if (canCall != enabled) {
            canCall = enabled
            notifyDataSetChanged()
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_task, parent, false)
        return VH(v)
    }
    override fun onBindViewHolder(h: VH, p: Int) = h.bind(items[p], canCall)
    override fun getItemCount() = items.size

    inner class VH(v: android.view.View) : RecyclerView.ViewHolder(v) {
        private val title: TextView = v.findViewById(R.id.title)
        private val sub: TextView = v.findViewById(R.id.sub)
        private val btn: android.widget.Button = v.findViewById(R.id.btnCall)
        fun bind(c: CaseItem, canCall: Boolean) {
            val tag = if (c.stage == "vote") "[投票]" else "[催收]"
            val location = listOfNotNull(c.owner.building, c.owner.room).joinToString("")
            title.text = "$tag ${c.owner.name}（$location）"
            sub.text = if (c.stage != "vote")
                "欠 ${c.amount_owed ?: "-"} / ${c.months_overdue ?: 0} 月"
            else
                "阶段：${c.stage}"
            val displayPhone = c.owner.phone ?: c.owner.phone_masked
            btn.text = if (canCall) "呼叫 $displayPhone" else "自检未通过"
            btn.isEnabled = canCall
            btn.alpha = if (canCall) 1.0f else 0.4f
            btn.setOnClickListener { if (canCall) onCall(c) }
        }
    }
}
