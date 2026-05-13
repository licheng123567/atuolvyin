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
    private fun showLoginDialog() {
        val phoneInput = android.widget.EditText(this).apply { hint = "手机号" }
        val pwdInput = android.widget.EditText(this).apply {
            hint = "密码"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                    android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(48, 16, 48, 0)
            addView(phoneInput)
            addView(pwdInput)
        }
        AlertDialog.Builder(this)
            .setTitle("登录")
            .setView(layout)
            .setPositiveButton("登录") { _, _ ->
                val phone = phoneInput.text.toString().trim()
                val pwd = pwdInput.text.toString()
                lifecycleScope.launch {
                    try {
                        val resp = ApiClient.get(this@MainActivity)
                            .login(LoginReq(phone = phone, password = pwd))
                        AppConfig.saveJwtToken(this@MainActivity, resp.access_token)
                        ApiClient.invalidate()
                        doSelfCheck()
                    } catch (t: Throwable) {
                        toast("登录失败: ${t.message}")
                    }
                }
            }
            .setNegativeButton("取消", null)
            .show()
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
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:$packageName")))
        }
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
        val dirOk = recDirs.isNotEmpty() && (Build.VERSION.SDK_INT < Build.VERSION_CODES.R
                || Environment.isExternalStorageManager())

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
                    recording_toggle_on = recDirs.isNotEmpty(),
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
                if (resp.can_call) {
                    // v2.0 Task 2 — happy path：跳转到 Compose Hybrid Shell。
                    // 旧 RecyclerView / loadTasks() / CaseAdapter 仍保留作为
                    // 过渡期 fallback（v2.1 后清理）。如果未来 HomeActivity 出现严重
                    // 故障，可临时把这两行注释掉、放开 loadTasks() 即可回退。
                    startActivity(Intent(this@MainActivity, HomeActivity::class.java))
                    finish()
                } else {
                    val why = resp.fail_reasons.joinToString("、") { reasonLabel(it) }
                        .ifBlank { "未知原因" }
                    toast("自检未通过（$why），呼叫已禁用")
                }
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
